# Import asyncio for async event loop management.
import asyncio

# Import contextlib to suppress expected cancellation errors.
import contextlib

# Import datetime utilities for time arithmetic and alignment.
from datetime import datetime

# Import json for serializing and parsing message payloads.
import json

# Import logging for structured log output.
import logging

# Import os for shell command execution.
import os

# Import signal to handle graceful shutdown signals.
import signal

# Import time for Unix timestamp conversion.
import time

# Import Path for loading the shared configuration file.
from pathlib import Path

# Import Set typing for type annotations of subscriber collections.
from typing import Optional, Set

# Import magic to verify downloaded file types.
import magic

# Import pytz to localize timestamps in the configured timezone.
import pytz

# Import WebSocket server helpers and broadcast utility.
from websockets.asyncio.server import serve, broadcast

# Define the path to the shared JSON configuration file.
CONFIG_PATH = Path(__file__).with_name("config.json")

# Load and return the JSON configuration used by all scripts.
def load_config() -> dict:
    # Open the configuration file with UTF-8 encoding.
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        # Parse the JSON payload into a dictionary.
        return json.load(config_file)

# Load the shared configuration once at startup.
config = load_config()

# Extract the logging configuration section.
logging_config = config.get("logging", {})

# Normalize the configured log level to uppercase.
log_level_name = logging_config.get("level", "INFO").upper()

# Resolve the log level or fall back to INFO.
log_level = getattr(logging, log_level_name, logging.INFO)

# Extract the download configuration section.
download_config = config.get("download", {})

# Load the maximum retry count for downloads.
max_trys = download_config.get("max_trys", 7)

# Load the radar API endpoint used for downloads.
radar_api_url = download_config.get("radar_api_url")

# Load the base URL used to construct file URLs.
base_url = download_config.get("base_url")

# Load the base filesystem path for storing downloads.
base_path = Path(download_config.get("base_path", "."))

# Load the list of product types to download.
products = download_config.get("products", ["VMI"])

# Load the timezone name for timestamp localization.
timezone_name = download_config.get("timezone", "Europe/Rome")

# Load the interval in seconds for scheduled downloads.
interval_seconds = int(download_config.get("interval_seconds", 600))

# Load the retry delay in seconds between attempts.
retry_sleep_seconds = download_config.get("retry_sleep_seconds", 60)

# Extract the WebSocket server configuration section.
server_config = config.get("websocket_server", {})

# Bind to all interfaces so containers or hosts can connect.
HOST = server_config.get("host", "0.0.0.0")

# Use the configured port for the WebSocket server.
PORT = server_config.get("port", 8765)

# Configure the maximum message size.
MAX_SIZE = server_config.get("max_size", 2**20)

# Configure keepalive ping interval.
PING_INTERVAL = server_config.get("ping_interval", 20)

# Configure keepalive ping timeout.
PING_TIMEOUT = server_config.get("ping_timeout", 20)

# Configure logging with timestamps and levels for observability.
logging.basicConfig(
    level=log_level,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

# Create a named logger for the WebSocket bus.
logger = logging.getLogger("ws-bus")

# Maintain a set of active subscriber connections.
SUBSCRIBERS: Set = set()

# Register a subscriber; keep the connection open and ignore incoming messages.
async def subscriber_handler(ws) -> None:

    # Add the new subscriber to the active set.
    SUBSCRIBERS.add(ws)

    # Log the updated subscriber count.
    logger.info("Subscriber connected (%d total)", len(SUBSCRIBERS))

    try:

        # Optionally acknowledge the subscription.
        await ws.send(json.dumps({"role": "subscriber", "status": "ok"}))

        # Drain any messages (we ignore them) until the socket closes.
        async for _ in ws:

            # Explicitly do nothing with subscriber messages.
            pass

    finally:

        # Remove the subscriber when the connection ends.
        SUBSCRIBERS.discard(ws)

        # Log the updated subscriber count.
        logger.info("Subscriber disconnected (%d total)", len(SUBSCRIBERS))


# Broadcast a JSON-serializable payload to all connected subscribers.
async def broadcast_update(payload: dict) -> None:

    # Determine whether any subscribers are available.
    if not SUBSCRIBERS:

        # Log that there are no subscribers to receive the update.
        logger.debug("No subscribers to broadcast to")

        # Exit early when there is no one to notify.
        return

    # Serialize the payload for broadcast.
    text = json.dumps(payload)

    # Broadcast the message to all subscribers.
    broadcast(SUBSCRIBERS, text)

    # Log how many subscribers received the update.
    logger.info("Broadcasted to %d subscriber(s)", len(SUBSCRIBERS))


# Receive JSON messages from an updater and broadcast to subscribers.
async def updater_handler(ws) -> None:

    # Log that an updater has connected.
    logger.info("Updater connected")

    try:

        # Acknowledge the updater connection.
        await ws.send(json.dumps({"role": "updater", "status": "ok"}))

        # Iterate over messages from the updater.
        async for message in ws:

            # Ensure messages are valid JSON text.
            try:

                # Attempt to parse the incoming JSON payload.
                payload = json.loads(message)

            except json.JSONDecodeError:

                # Build an error response for invalid JSON.
                err = {"error": "invalid_json", "detail": "Message must be valid JSON text"}

                # Send the error back to the updater.
                await ws.send(json.dumps(err))

                # Warn that a malformed message was rejected.
                logger.warning("Rejected non-JSON message from updater")

                # Skip broadcasting when the payload is invalid.
                continue

            # Broadcast the payload to all subscribers.
            await broadcast_update(payload)

            # Send an acknowledgment back to the updater.
            await ws.send(json.dumps({"result": "broadcasted"}))

    finally:
        # Log that the updater disconnected.
        logger.info("Updater disconnected")

# Route connections based on the request path.
async def route(ws) -> None:
    # Document the expected routes for the server.
    """
    Route connections by path:
      - /subscribe -> subscriber role
      - /update    -> updater role
    """

    # Extract the request path from the websocket object.
    path = getattr(getattr(ws, "request", None), "path", "/")

    # Dispatch to the subscriber handler for the subscribe endpoint.
    if path == "/subscribe":

        await subscriber_handler(ws)

    # Dispatch to the updater handler for the update endpoint.
    elif path == "/update":

        await updater_handler(ws)

    else:

        # Prepare a reason for rejecting unknown paths.
        reason = f"Unknown path '{path}'. Use /subscribe or /update."

        # Warn about the unexpected path.
        logger.warning(reason)

        # Close the connection with a policy violation status.
        await ws.close(code=1008, reason=reason)

# Build the standard headers needed for the radar API request.
def build_download_headers() -> dict:

    # Assemble the headers that mimic the browser request.
    return {
        # Accept JSON responses from the API.
        "accept": "application/json, text/plain, */*",
        # Set the content type for the JSON payload.
        "content-type": "application/json",
        # Provide the origin header expected by the API.
        "origin": "https://radar.protezionecivile.it",
        # Set the priority header as seen in browser requests.
        "priority": "u=1, i",
        # Set the referer header expected by the API.
        "referer": "https://radar.protezionecivile.it/",
        # Indicate the fetch destination for CORS.
        "sec-fetch-dest": "empty",
        # Indicate the fetch mode for CORS.
        "sec-fetch-mode": "cors",
        # Indicate the fetch site for CORS.
        "sec-fetch-site": "same-site",
    }


# Download a single product for the specified timestamp.
def download_product(
    product: str,
    target_time: datetime,
    utc_time: datetime,
    unix_time_ms: int,
    headers: dict,
) -> Optional[dict]:

    # Build the destination directory for the date-based folder structure.
    file_path = base_path / utc_time.strftime("%Y") / utc_time.strftime("%m") / utc_time.strftime("%d")

    # Ensure the destination directory exists before downloading files.
    if not file_path.exists():
        # Create the directory tree as needed.
        file_path.mkdir(parents=True)

    # Construct the filename for the current product.
    file_name = f"rdr0_d01_{utc_time.strftime('%Y%m%dZ%H%M')}_{product}.tiff"

    # Build the payload required by the API.
    payload = {
        # Identify which product type to fetch.
        "productType": product,
        # Provide the product timestamp in Unix milliseconds.
        "productDate": unix_time_ms,
    }

    # Build the absolute file path for the downloaded file.
    absolute_file_path = file_path / file_name

    # Construct the public URL for this product.
    file_url = f"{base_url}/{utc_time.strftime('%Y')}/{utc_time.strftime('%m')}/{utc_time.strftime('%d')}/{file_name}"

    # Initialize the retry counter.
    trys = 0

    # Retry until the maximum attempts are exhausted.
    while trys < max_trys:
        # Log the current attempt number.
        logger.info("Try number: %s", trys)

        # Build the curl command for the API request.
        command = (
            f"curl '{radar_api_url}' "
            f"-H 'accept: {headers['accept']}' "
            f"-H 'content-type: {headers['content-type']}' "
            f"-H 'origin: {headers['origin']}' "
            f"-H 'priority: {headers['priority']}' "
            f"-H 'referer: {headers['referer']}' "
            f"-H 'sec-fetch-dest: {headers['sec-fetch-dest']}' "
            f"-H 'sec-fetch-mode: {headers['sec-fetch-mode']}' "
            f"-H 'sec-fetch-site: {headers['sec-fetch-site']}' "
            f"--data-raw '{json.dumps(payload)}' --silent --output {absolute_file_path}"
        )

        # Execute the curl command in the shell.
        os.system(command)

        # Detect the file MIME type for verification.
        mime_type = magic.from_file(str(absolute_file_path), mime=True)

        # Log the MIME type for debugging.
        logger.warning(mime_type)

        # Proceed when a valid TIFF image is downloaded.
        if mime_type == "image/tiff":
            # Log the successful download.
            logger.info("Downloaded %s for %s", product, target_time)

            # Build the update payload to broadcast.
            return {
                # Identify the product type in the update.
                "productType": product,
                # Provide the product timestamp in Unix milliseconds.
                "productDate": unix_time_ms,
                # Provide the local file path for the product.
                "file": str(absolute_file_path),
                # Provide the public URL for the product.
                "url": file_url,
            }

        # Remove the invalid or incomplete file.
        absolute_file_path.unlink(missing_ok=True)

        # Log that the retry delay is starting.
        logger.warning("Waiting...")

        # Sleep for the configured retry delay.
        time.sleep(retry_sleep_seconds)

        # Log that another attempt will start.
        logger.warning("Retrying...")

        # Increment the retry counter.
        trys = trys + 1

    # Return None when all retries are exhausted.
    return None


# Determine which timestamp to download based on the configured interval.
def calculate_target_time(current_time: datetime) -> datetime:

    # Convert the current time to an epoch integer in seconds.
    epoch_seconds = int(current_time.timestamp())

    # Align the timestamp down to the nearest interval boundary.
    aligned_epoch = epoch_seconds - (epoch_seconds % interval_seconds)

    # Choose the previous interval to ensure data availability.
    target_epoch = aligned_epoch - interval_seconds

    # Convert the epoch timestamp back to a datetime object.
    return datetime.fromtimestamp(target_epoch)


# Download radar data at the configured interval and notify subscribers.
async def download_loop(stop: asyncio.Event) -> None:

    # Create a timezone object for the configured region.
    local_timezone = pytz.timezone(timezone_name)

    # Store the last processed timestamp to avoid duplicates.
    last_processed: Optional[datetime] = None

    # Build the shared headers for the download API request.
    headers = build_download_headers()

    # Continue downloading until the stop event is set.
    while not stop.is_set():

        # Capture the current time for interval alignment.
        current_time = datetime.now()

        # Compute the target timestamp for this cycle.
        target_time = calculate_target_time(current_time)

        # Only process when the target timestamp changes.
        if last_processed != target_time:

            # Convert the timestamp to UTC for naming conventions.
            utc_time = local_timezone.localize(target_time, is_dst=None).astimezone(pytz.utc)

            # Convert the timestamp to Unix milliseconds for the API payload.
            unix_time_ms = int(1000 * time.mktime(target_time.timetuple()))

            # Log the UTC timestamp being processed.
            logger.info("Processing radar timestamp %s", utc_time)

            # Iterate through each configured product type.
            for product in products:

                # Download the product in a worker thread to avoid blocking.
                message = await asyncio.to_thread(
                    download_product,
                    product,
                    target_time,
                    utc_time,
                    unix_time_ms,
                    headers,
                )

                # Broadcast updates only when a download succeeds.
                if message:

                    # Notify all subscribers about the new product.
                    await broadcast_update(message)

            # Record the timestamp we just processed.
            last_processed = target_time

        # Calculate the next interval boundary for sleeping.
        next_epoch = int(current_time.timestamp())

        # Compute seconds until the next aligned boundary.
        sleep_seconds = interval_seconds - (next_epoch % interval_seconds)

        # Avoid a zero or negative sleep interval.
        sleep_seconds = max(1, sleep_seconds)

        try:

            # Sleep until the next interval or until a stop signal arrives.
            await asyncio.wait_for(stop.wait(), timeout=sleep_seconds)

        except asyncio.TimeoutError:

            # Continue looping after the sleep timeout.
            continue


# Entry point that runs the server and waits for shutdown signals.
async def main() -> None:

    # Create an event to coordinate graceful shutdown.
    stop = asyncio.Event()

    # Define a handler that sets the stop event.
    def _handle_sig(*_):

        # Signal the main task to stop.
        stop.set()

    # Access the current running event loop.
    loop = asyncio.get_running_loop()

    # Register handlers for standard termination signals.
    for sig in (signal.SIGINT, signal.SIGTERM):

        try:

            # Attach the signal handler to the loop.
            loop.add_signal_handler(sig, _handle_sig)

        except NotImplementedError:

            # Windows on Python <3.8 may not support signals in asyncio.
            pass

    # Log the server startup configuration.
    logger.info("Starting WebSocket server on %s:%d", HOST, PORT)

    # Start the background download loop.
    download_task = asyncio.create_task(download_loop(stop))

    # Start the server and keep it running while the stop event is unset.
    async with serve(
        route,
        HOST,
        PORT,
        # Limit maximum message size to protect the server.
        max_size=MAX_SIZE,
        # Enable keepalive pings to detect dead connections.
        ping_interval=PING_INTERVAL,
        # Configure the ping timeout.
        ping_timeout=PING_TIMEOUT,
        # You could add origin checks with 'origins={...}' if needed.
    ):

        # Log the available endpoints once the server is live.
        logger.info("Server is running. Endpoints: /subscribe, /update")

        # Wait until a shutdown signal is received.
        await stop.wait()

    # Cancel the background download loop on shutdown.
    download_task.cancel()

    # Await the download task to silence cancellation warnings.
    with contextlib.suppress(asyncio.CancelledError):

        # Ensure the task is fully cancelled.
        await download_task

    # Log that the server has stopped.
    logger.info("Server stopped.")

# Guard the async entry point for direct execution.
if __name__ == "__main__":

    # Run the main coroutine in the asyncio event loop.
    asyncio.run(main())
