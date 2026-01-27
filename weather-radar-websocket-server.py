# Import argparse for command-line configuration.
import argparse

# Import asyncio for async event loop management.
import asyncio

# Import contextlib to suppress expected cancellation errors.
import contextlib

# Import datetime utilities for time arithmetic and alignment.
from datetime import datetime

# Import json for serializing and parsing message payloads.
import json

# Import http.server to expose a lightweight static file server.
import http.server

# Import logging for structured log output.
import logging

# Import requests for HTTP API calls.
import requests

# Import shutil for copying files in simulation mode.
import shutil

# Import signal to handle graceful shutdown signals.
import signal

# Import threading to run the optional web server in the background.
import threading

# Import time for Unix timestamp conversion.
import time

# Import Path for loading the shared configuration file.
from pathlib import Path

# Import Set typing for type annotations of subscriber collections.
from typing import Optional, Set

# Try to import magic for MIME type detection.
try:
    # Import magic to verify downloaded file types.
    import magic
except ImportError as exc:
    # Fall back when libmagic is missing.
    magic = None
    # Store the import error for later logging.
    MAGIC_IMPORT_ERROR = exc
else:
    # Record that magic loaded successfully.
    MAGIC_IMPORT_ERROR = None

# Import pytz to localize timestamps in the configured timezone.
import pytz

# Import croniter to compute cron-based schedule boundaries.
from croniter import croniter

# Import WebSocket server helpers and broadcast utility.
from websockets.asyncio.server import serve, broadcast

# Define the default path to the shared JSON configuration file.
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")

# Create a named logger for the WebSocket bus.
logger = logging.getLogger("ws-bus")

# Initialize configuration defaults so globals are always defined.
logging_config: dict = {}
log_level_name = "INFO"
log_level = logging.INFO

download_config: dict = {}
simulation_config: dict = {}
simulation_enabled = False
simulation_source_dir = Path("")
max_trys = 7
radar_api_url = None
base_url = ""
base_path = Path(".")
products = ["VMI"]
timezone_name = "Europe/Rome"
interval_expression = None
interval_minutes = None
interval_seconds = 600
retry_sleep_seconds = 60
simulation_starting_datetime = None
simulation_time_step_seconds = interval_seconds
simulation_start_time: Optional[datetime] = None

default_server_config: dict = {}
default_webserver_config: dict = {}

HOST = "0.0.0.0"
PORT = 8765
MAX_SIZE = 2**20
PING_INTERVAL = 20
PING_TIMEOUT = 20

WEBSERVER_ENABLED = False
WEBSERVER_HOST = "0.0.0.0"
WEBSERVER_PORT = 8080

# Define a placeholder for the resolved cron schedule.
download_cron = "*/10 * * * *"

# Build the argument parser for command-line options.
def build_argument_parser() -> argparse.ArgumentParser:

    # Create the argument parser with a helpful description.
    parser = argparse.ArgumentParser(
        description="Weather Radar Websocket Server",
    )

    # Add an optional config path argument with a sensible default.
    parser.add_argument(
        "--config",
        "-c",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help="Path to the JSON configuration file (default: config.json)",
    )

    # Return the configured parser to the caller.
    return parser

# Load and return the JSON configuration used by all scripts.
def load_config(config_path: Path) -> dict:

    # Open the configuration file with UTF-8 encoding.
    with config_path.open("r", encoding="utf-8") as config_file:

        # Parse the JSON payload into a dictionary.
        return json.load(config_file)

# Apply configuration values to module-level settings.
def configure_from_path(config_path: Path) -> None:

    # Declare global state that will be updated by this configuration.
    global logging_config
    global log_level_name
    global log_level
    global download_config
    global simulation_config
    global simulation_enabled
    global simulation_source_dir
    global max_trys
    global radar_api_url
    global base_url
    global base_path
    global products
    global timezone_name
    global interval_expression
    global interval_minutes
    global interval_seconds
    global retry_sleep_seconds
    global simulation_starting_datetime
    global simulation_time_step_seconds
    global simulation_start_time
    global HOST
    global PORT
    global MAX_SIZE
    global PING_INTERVAL
    global PING_TIMEOUT
    global WEBSERVER_ENABLED
    global WEBSERVER_HOST
    global WEBSERVER_PORT
    global download_cron

    # Load the shared configuration from the specified file.
    config = load_config(config_path)

    # Extract the logging configuration section.
    logging_config = config.get("logging", {})

    # Normalize the configured log level to uppercase.
    log_level_name = logging_config.get("level", "INFO").upper()

    # Resolve the log level or fall back to INFO.
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Configure logging with timestamps and levels for observability.
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )

    # Log the configuration source path for traceability.
    logger.info("Using configuration file: %s", config_path)

    # Extract the download configuration section.
    download_config = config.get("download", {})

    # Extract the simulation configuration section for local playback.
    simulation_config = download_config.get("simulation", {})

    # Determine whether simulation mode is enabled.
    simulation_enabled = bool(simulation_config.get("enabled", False))

    # Capture the configured simulation source directory.
    simulation_source_dir = Path(simulation_config.get("source_dir", ""))

    # Load the maximum retry count for downloads.
    max_trys = download_config.get("max_trys", 7)

    # Load the radar API endpoint used for downloads.
    radar_api_url = download_config.get("radar_api_url")

    # Load the base URL used to construct file URLs.
    base_url = download_config.get("base_url", "")

    # Load the base filesystem path for storing downloads.
    base_path = Path(download_config.get("base_path", "."))

    # Load the list of product types to download.
    products = download_config.get("products", ["VMI"])

    # Load the timezone name for timestamp localization.
    timezone_name = download_config.get("timezone", "Europe/Rome")

    # Load the cron-style interval string for scheduled downloads.
    interval_expression = download_config.get("interval")

    # Load the fallback interval in minutes for legacy configurations.
    interval_minutes = download_config.get("interval_minutes")

    # Load the fallback interval in seconds for legacy configurations.
    interval_seconds = int(download_config.get("interval_seconds", 600))

    # Load the retry delay in seconds between attempts.
    retry_sleep_seconds = download_config.get("retry_sleep_seconds", 60)

    # Load the configured simulation starting datetime string.
    simulation_starting_datetime = simulation_config.get("starting_datetime")

    # Load the configured simulation time step in seconds.
    simulation_time_step_seconds = int(simulation_config.get("time_step", interval_seconds))

    # Ensure the simulation time step is at least one second.
    simulation_time_step_seconds = max(1, simulation_time_step_seconds)

    # Extract the WebSocket server configuration section.
    server_config = config.get("websocket_server", {})

    # Extract the optional web server configuration section.
    webserver_config = config.get("webserver_server", {})

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

    # Determine whether the optional web server should run.
    WEBSERVER_ENABLED = bool(webserver_config.get("enabled", False))

    # Bind the web server to all interfaces by default.
    WEBSERVER_HOST = "0.0.0.0"

    # Configure the port for the optional web server.
    WEBSERVER_PORT = int(webserver_config.get("port", 8080))

    # Warn if libmagic is unavailable so users know why validation is limited.
    if MAGIC_IMPORT_ERROR:

        # Log the missing libmagic dependency with details.
        logger.warning(
            "python-magic is unavailable; falling back to TIFF header checks (%s)",
            MAGIC_IMPORT_ERROR,
        )

    # Normalize the simulation start datetime once at startup.
    simulation_start_time = parse_simulation_starting_datetime(simulation_starting_datetime)

    # Resolve the cron expression once so scheduling is consistent.
    download_cron = resolve_download_cron_expression()

    # Log the cron expression used for downloads.
    logger.info("Download cron schedule set to %s", download_cron)

    # Log simulation mode configuration for transparency.
    if simulation_enabled:

        # Inform operators that simulation mode is active.
        logger.info("Simulation mode enabled; source directory: %s", simulation_source_dir)

        # Log the starting time when it is configured.
        if simulation_start_time:

            # Share the parsed UTC starting datetime for debugging.
            logger.info("Simulation start time set to %s", simulation_start_time)

        else:

            # Warn that the start time is missing or invalid.
            logger.warning("Simulation start time not set; using current UTC time")

        # Log the configured simulation time step in seconds.
        logger.info("Simulation time step set to %s seconds", simulation_time_step_seconds)

# Parse the simulation start timestamp in ISO UTC format.
def parse_simulation_starting_datetime(value: Optional[str]) -> Optional[datetime]:

    # Return early when no starting datetime is configured.
    if not value:

        # Indicate that there is no configured simulation start time.
        return None

    try:

        # Parse the ISO UTC format like 20251223T120000Z.
        parsed = datetime.strptime(value, "%Y%m%dT%H%M%SZ")

    except ValueError:

        # Warn when the configured value cannot be parsed.
        logger.warning(
            "Invalid simulation starting_datetime %s; expected YYYYMMDDTHHMMSSZ",
            value,
        )

        # Return None so callers can fall back safely.
        return None

    # Attach UTC timezone information to the parsed timestamp.
    return parsed.replace(tzinfo=pytz.utc)

# Determine the cron expression for downloads using the most specific config.
def resolve_download_cron_expression() -> str:

    # Prefer an explicit cron interval when provided.
    if interval_expression:

        # Return the configured cron expression as-is.
        return interval_expression

    # Use the legacy minute interval if configured.
    if interval_minutes:

        # Convert the minute interval into a cron expression.
        return f"*/{int(interval_minutes)} * * * *"

    # When seconds align with whole minutes, convert to a cron expression.
    if interval_seconds % 60 == 0:

        # Translate seconds into minutes for cron syntax.
        minutes = max(1, interval_seconds // 60)

        # Return a cron expression that matches the derived minute cadence.
        return f"*/{minutes} * * * *"

    # Warn that we are falling back to a 10-minute cadence.
    logger.warning(
        "interval_seconds=%s is not divisible by 60; defaulting to */10 * * * *",
        interval_seconds,
    )

    # Default to a 10-minute schedule when configuration is ambiguous.
    return "*/10 * * * *"

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

# Build a request handler that serves files from the download base path.
def build_webserver_handler(directory: Path) -> type[http.server.SimpleHTTPRequestHandler]:

    # Define a custom handler to inject the directory and logging behavior.
    class RadarRequestHandler(http.server.SimpleHTTPRequestHandler):

        # Initialize the handler with the configured directory.
        def __init__(self, *args, **kwargs) -> None:

            # Pass the directory to the parent handler for static file serving.
            super().__init__(*args, directory=str(directory), **kwargs)

        # Route the default HTTP log output through the structured logger.
        def log_message(self, format, *args) -> None:

            # Emit a structured log line for the web server request.
            logger.info("Web server: " + format, *args)

    # Return the customized handler class for server creation.
    return RadarRequestHandler

# Start a background HTTP server that exposes the download directory.
def start_webserver() -> tuple[http.server.ThreadingHTTPServer, threading.Thread]:

    # Ensure the download base directory exists before serving it.
    base_path.mkdir(parents=True, exist_ok=True)

    # Build the request handler bound to the download directory.
    handler = build_webserver_handler(base_path)

    # Create the HTTP server bound to the configured host and port.
    httpd = http.server.ThreadingHTTPServer((WEBSERVER_HOST, WEBSERVER_PORT), handler)

    # Define the background thread that will run the server.
    thread = threading.Thread(target=httpd.serve_forever, name="webserver", daemon=True)

    # Start the web server thread so it can accept requests.
    thread.start()

    # Log the web server startup details.
    logger.info(
        "Web server enabled on %s:%d serving %s",
        WEBSERVER_HOST,
        WEBSERVER_PORT,
        base_path,
    )

    # Return the server and thread for shutdown coordination.
    return httpd, thread

# Route connections based on the request path.
async def route(ws) -> None:
    # Document the expected routes for the server.
    """
    Route connections by path:
      - /subscribe -> subscriber role
    """

    # Extract the request path from the websocket object.
    path = getattr(getattr(ws, "request", None), "path", "/")

    # Dispatch to the subscriber handler for the subscribe endpoint.
    if path == "/subscribe":

        await subscriber_handler(ws)

    else:

        # Prepare a reason for rejecting unknown paths.
        reason = f"Unknown path '{path}'. Use /subscribe"

        # Warn about the unexpected path.
        logger.warning(reason)

        # Close the connection with a policy violation status.
        await ws.close(code=1008, reason=reason)

# Build the standard headers needed for the radar API request.
def build_download_headers() -> dict:

    # Assemble the headers that mimic the browser request.
    return {
        # Set the content type for the JSON payload.
        "content-type": "application/json",
        # User agent
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'
    }

# Load and sort simulation files from the configured directory.
def load_simulation_files(source_dir: Path) -> list[Path]:

    # Warn when the simulation directory is not configured.
    if not source_dir:

        # Log that the simulation source directory is missing.
        logger.warning("Simulation mode enabled but no source_dir configured")

        # Return an empty list to signal there is nothing to process.
        return []

    # Warn when the simulation directory does not exist.
    if not source_dir.exists():

        # Log that the configured directory is unavailable.
        logger.warning("Simulation source directory %s does not exist", source_dir)

        # Return an empty list to avoid raising exceptions later.
        return []

    # Collect only file entries from the source directory.
    files = [path for path in source_dir.iterdir() if path.is_file()]

    # Sort the files alphabetically to preserve deterministic ordering.
    files.sort(key=lambda path: path.name)

    # Warn when no files are available to simulate.
    if not files:

        # Log that the directory is empty.
        logger.warning("Simulation source directory %s contains no files", source_dir)

    # Return the sorted file list for playback.
    return files

# Derive the product type from a filename or fall back to configuration.
def derive_product_type(file_path: Path) -> str:

    # Use the configured product list when available.
    default_product = products[0] if products else "VMI"

    # Split the filename stem into parts to extract the product suffix.
    parts = file_path.stem.split("_")

    # Return the last segment when it exists as a product hint.
    if parts:

        # Provide the final filename segment as the product type.
        return parts[-1]

    # Fall back to the configured product type when parsing fails.
    return default_product

# Build a destination filename for simulated data based on the target time.
def build_simulation_destination_name(
    source_file: Path,
    target_time: datetime,
    product: str,
) -> str:

    # Format the target time for filenames (e.g., 20251223Z1200).
    timestamp = target_time.strftime("%Y%m%dZ%H%M")

    # Split the filename stem to inspect known naming conventions.
    parts = source_file.stem.split("_")

    # Replace the timestamp segment when a standard naming pattern is present.
    if len(parts) >= 3:

        # Update the timestamp portion with the simulated time.
        parts[2] = timestamp

        # Rebuild the filename with the original suffix.
        return "_".join(parts) + source_file.suffix

    # Fall back to a simple timestamp + product filename when patterns differ.
    return f"{timestamp}_{product}{source_file.suffix}"

# Copy a simulation file into place and build the update payload.
def copy_simulation_file(
    source_file: Path,
    target_time: datetime,
    unix_time_ms: int,
) -> Optional[dict]:

    # Ensure the base path exists for storing the simulated file.
    base_path.mkdir(parents=True, exist_ok=True)

    # Derive the product type from the filename.
    product = derive_product_type(source_file)

    # Build a destination filename that matches the simulated timestamp.
    destination_name = build_simulation_destination_name(
        source_file,
        target_time,
        product,
    )

    # Build the destination path using the simulated filename.
    destination_file = base_path / destination_name

    try:

        # Copy the file to the destination, preserving metadata.
        shutil.copy2(source_file, destination_file)

    except OSError as exception:

        # Log the copy failure so operators can inspect the issue.
        logger.warning("Failed to copy simulation file %s: %s", source_file, exception)

        # Skip broadcasting when the file cannot be copied.
        return None

    # Build the public URL for the simulated file when configured.
    file_url = (
        f"{base_url.rstrip('/')}/{destination_file.name}" if base_url else ""
    )

    # Log the simulated file playback.
    logger.info("Simulated %s for %s", destination_file.name, target_time)

    # Build the update payload to broadcast.
    return {
        # Identify the product type in the update.
        "productType": product,
        # Provide the product timestamp in Unix milliseconds.
        "productDate": unix_time_ms,
        # Provide the local file path for the product.
        "file": str(destination_file),
        # Provide the public URL for the product.
        "url": file_url,
    }

# Detect whether a file is a TIFF image using libmagic or header checks.
def is_tiff_file(path: Path) -> bool:

    # Use libmagic when it is available for robust detection.
    if magic is not None:

        # Detect the file MIME type for verification.
        mime_type = magic.from_file(str(path), mime=True)

        # Log the MIME type for debugging.
        logger.debug("Detected MIME type %s for %s", mime_type, path)

        # Return whether the MIME type matches a TIFF image.
        return mime_type == "image/tiff"

    try:

        # Open the file in binary mode for header inspection.
        with path.open("rb") as file_handle:

            # Read the first four bytes that contain the TIFF signature.
            header = file_handle.read(4)

    except OSError as exception:

        # Warn when the file cannot be read for validation.
        logger.warning("Unable to read %s for TIFF validation: %s", path, exception)

        # Treat unreadable files as invalid.
        return False

    # TIFF files start with either little-endian or big-endian signatures.
    is_tiff = header in (b"II*\x00", b"MM\x00*")

    # Log the header validation result.
    logger.debug("TIFF header validation for %s: %s", path, is_tiff)

    # Return the header validation result.
    return is_tiff


def download_product(
    product: str,
    target_time: datetime,
    utc_time: datetime,
    unix_time_ms: int,
    headers: dict,
    stop: asyncio.Event,
) -> Optional[dict]:
    """
    Download a single radar product for the specified timestamp.

    New API behavior:
      1) POST to radar_api_url returns JSON containing a short-lived pre-signed S3 URL in field "url"
      2) Download the GeoTIFF from that URL (GET)
      3) Keep the same retry / stop / output dict semantics as the original implementation.
    """

    # Build the destination directory for the date-based folder structure.
    file_path = base_path / utc_time.strftime("%Y") / utc_time.strftime("%m") / utc_time.strftime("%d")

    # Ensure the destination directory exists before downloading files.
    if not file_path.exists():
        file_path.mkdir(parents=True)

    # Construct the filename for the current product (keep your existing naming).
    file_name = f"rdr0_d01_{utc_time.strftime('%Y%m%dZ%H%M')}_{product}.tiff"

    # Build the absolute file path for the downloaded file.
    absolute_file_path = file_path / file_name

    # Construct the public URL for this product (keep your existing public URL scheme).
    file_url = f"{base_url}/{utc_time.strftime('%Y')}/{utc_time.strftime('%m')}/{utc_time.strftime('%d')}/{file_name}"

    trys = 0
    while trys < max_trys:
        if stop.is_set():
            logger.info("Download for %s interrupted by shutdown", product)
            return None

        logger.info("Try number: %s", trys)

        # 1) Ask the API for a pre-signed download URL
        presigned_url = None
        try:

            meta_resp = requests.post(
                radar_api_url,
                json= {"productType": product, "productDate": int(unix_time_ms)},
                headers={"content-type": "application/json"},
                timeout=30,
            )

        except requests.RequestException as exception:
            logger.warning("Metadata request failed for %s: %s", product, exception)
        else:
            # Some deployments may return non-2xx with JSON body. We parse if possible anyway.
            ct = (meta_resp.headers.get("content-type") or "").lower()

            if "application/json" in ct:
                try:
                    meta = meta_resp.json()
                except ValueError:
                    meta = None
            else:
                meta = None

            if meta_resp.ok and isinstance(meta, dict) and meta.get("url"):
                presigned_url = meta["url"]
            else:
                # Provide best-effort diagnostics for logging
                if isinstance(meta, dict):
                    logger.warning(
                        "Metadata request not successful for %s (HTTP %s). Body: %s",
                        product,
                        meta_resp.status_code,
                        meta,
                    )
                else:
                    logger.warning(
                        "Metadata request not successful for %s (HTTP %s). Content-Type=%s, BodySnippet=%r",
                        product,
                        meta_resp.status_code,
                        ct,
                        (meta_resp.text or "")[:500],
                    )

        # 2) If we obtained the pre-signed URL, download the GeoTIFF
        if presigned_url and not stop.is_set():
            try:
                # Use streaming GET for large GeoTIFFs
                with requests.get(presigned_url, stream=True, timeout=60) as tif_resp:
                    # If this fails, it might be because the URL expired (expiresSeconds ~ 300)
                    tif_resp.raise_for_status()

                    # Write to disk (atomic-ish)
                    tmp_path = absolute_file_path.with_suffix(absolute_file_path.suffix + ".part")
                    with open(tmp_path, "wb") as f:
                        for chunk in tif_resp.iter_content(chunk_size=1024 * 1024):
                            if stop.is_set():
                                logger.info("Download interrupted for %s by shutdown", product)
                                f.close()
                                tmp_path.unlink(missing_ok=True)
                                return None
                            if chunk:
                                f.write(chunk)
                    tmp_path.replace(absolute_file_path)

            except requests.RequestException as exception:
                logger.warning("GeoTIFF download failed for %s: %s", product, exception)
            except OSError as exception:
                logger.warning("File write failed for %s: %s", product, exception)

        # Proceed when a valid TIFF image is downloaded.
        if is_tiff_file(absolute_file_path):
            logger.info("Downloaded %s for %s", product, target_time)
            return {
                "productType": product,
                "productDate": unix_time_ms,
                "file": str(absolute_file_path),
                "url": file_url,
            }

        # Remove invalid/incomplete file and retry
        absolute_file_path.unlink(missing_ok=True)

        logger.warning("Waiting...")

        for _ in range(int(retry_sleep_seconds)):
            if stop.is_set():
                logger.info("Retry sleep interrupted for %s due to shutdown", product)
                return None
            time.sleep(1)

        logger.warning("Retrying...")
        trys += 1

    return None



# Determine which timestamp to download based on the configured cron schedule.
def calculate_target_time(current_time: datetime) -> datetime:

    # Strip seconds for cron alignment to minute boundaries.
    rounded_time = current_time.replace(second=0, microsecond=0)

    # Build a cron iterator anchored to the rounded current time.
    iterator = croniter(download_cron, rounded_time)

    # Select the previous scheduled time to ensure data availability.
    return iterator.get_prev(datetime)

# Compute the next scheduled download time for sleeping.
def calculate_next_time(current_time: datetime) -> datetime:

    # Strip seconds for cron alignment to minute boundaries.
    rounded_time = current_time.replace(second=0, microsecond=0)

    # Build a cron iterator anchored to the rounded current time.
    iterator = croniter(download_cron, rounded_time)

    # Select the next scheduled time for the sleep boundary.
    return iterator.get_next(datetime)

# Download radar data at the configured interval and notify subscribers.
async def download_loop(stop: asyncio.Event) -> None:

    # Create a timezone object for the configured region.
    local_timezone = pytz.timezone(timezone_name)

    # Store the last processed timestamp to avoid duplicates.
    last_processed: Optional[datetime] = None

    # Cache the simulation file list for sequential playback.
    simulation_files: list[Path] = []

    # Track the current index within the simulation file list.
    simulation_index = 0

    # Build the shared headers for the download API request.
    headers = build_download_headers()

    # Initialize the simulation clock and cron iterator when enabled.
    if simulation_enabled:

        # Start from the configured simulation time or the current UTC time.
        simulation_current_time = (
            simulation_start_time
            or datetime.now(pytz.utc).replace(second=0, microsecond=0)
        )

        # Build a cron iterator anchored to the simulated timestamp.
        simulation_iterator = croniter(download_cron, simulation_current_time)

    # Continue downloading until the stop event is set.
    while not stop.is_set():

        # Determine the target timestamp and sleep cadence.
        if simulation_enabled:

            # Use the simulated clock as the target time.
            target_time = simulation_current_time

            # Advance to the next scheduled simulated timestamp.
            next_time = simulation_iterator.get_next(datetime)

            # Use the configured simulation time step for sleeping.
            sleep_seconds = max(1, simulation_time_step_seconds)

            # Log the next simulated timestamp for visibility.
            logger.info(
                "Next simulated timestamp %s (sleep %s seconds)",
                next_time,
                sleep_seconds,
            )

        else:

            # Capture the current time for interval alignment.
            current_time = datetime.now()

            # Compute the target timestamp for this cycle.
            target_time = calculate_target_time(current_time)

            # Calculate the next scheduled boundary for sleeping.
            next_time = calculate_next_time(current_time)

            # Compute seconds until the next scheduled run.
            sleep_seconds = int((next_time - current_time).total_seconds())

            # Avoid a zero or negative sleep interval.
            sleep_seconds = max(1, sleep_seconds)

            # Log the next scheduled download time.
            logger.info("Next download %s", next_time)

        try:

            # Sleep until the next interval or until a stop signal arrives.
            await asyncio.wait_for(stop.wait(), timeout=sleep_seconds)

        except asyncio.TimeoutError:

            # Continue looping after the sleep timeout.
            pass

        # Exit promptly if a shutdown signal arrives.
        if stop.is_set():
            # Log that the download loop is stopping.
            logger.info("Download loop stopping due to shutdown signal")
            # Break out of the loop to exit cleanly.
            break

        # Only process when the target timestamp changes.
        if last_processed != target_time:

            # Normalize the timestamp to UTC for naming conventions.
            if simulation_enabled:

                # Use the simulated target time directly in UTC.
                utc_time = target_time

            else:

                # Convert the local timestamp to UTC for downloads.
                utc_time = local_timezone.localize(target_time, is_dst=None).astimezone(pytz.utc)

            # Convert the timestamp to Unix milliseconds for the API payload.
            unix_time_ms = int(utc_time.timestamp() * 1000)

            # Log the UTC timestamp being processed.
            logger.info("Processing radar timestamp %s", utc_time)

            # Handle simulation mode by copying files from disk.
            if simulation_enabled:

                # Refresh the simulation file list when exhausted.
                if not simulation_files or simulation_index >= len(simulation_files):

                    # Reload and sort the files from the source directory.
                    simulation_files = load_simulation_files(simulation_source_dir)

                    # Reset the index to the start of the list.
                    simulation_index = 0

                # Only proceed when a simulation file is available.
                if simulation_files:

                    # Select the next file in alphabetical order.
                    source_file = simulation_files[simulation_index]

                    # Advance the index for the next interval.
                    simulation_index += 1

                    # Copy the file and build a broadcast payload.
                    message = copy_simulation_file(
                        source_file,
                        target_time,
                        unix_time_ms,
                    )

                    # Broadcast updates only when the copy succeeds.
                    if message:

                        # Notify all subscribers about the simulated product.
                        await broadcast_update(message)

                else:

                    # Warn when no simulation files are available.
                    logger.warning("No simulation files available for %s", simulation_source_dir)

            else:

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
                        stop,
                    )

                    # Broadcast updates only when a download succeeds.
                    if message:

                        # Notify all subscribers about the new product.
                        await broadcast_update(message)

            # Record the timestamp we just processed.
            last_processed = target_time

            # Advance the simulated clock after processing.
            if simulation_enabled:

                # Update the current simulated time to the next interval.
                simulation_current_time = next_time





# Entry point that runs the server and waits for shutdown signals.
async def run_async_server() -> None:

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

    # Track the optional web server instance for shutdown.
    webserver: Optional[http.server.ThreadingHTTPServer] = None

    # Track the optional web server thread for shutdown coordination.
    webserver_thread: Optional[threading.Thread] = None

    # Start the optional web server when enabled in configuration.
    if WEBSERVER_ENABLED:

        # Spin up the web server in a background thread.
        webserver, webserver_thread = start_webserver()

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
        logger.info("Server is running. Endpoints: /subscribe")

        # Wait until a shutdown signal is received.
        await stop.wait()

    # Cancel the background download loop on shutdown.
    download_task.cancel()

    # Await the download task to silence cancellation warnings.
    with contextlib.suppress(asyncio.CancelledError):

        # Ensure the task is fully cancelled.
        await download_task

    # Shut down the optional web server when it is running.
    if webserver:

        # Log that the web server is stopping.
        logger.info("Stopping web server")

        # Ask the web server to stop accepting new requests.
        webserver.shutdown()

        # Close the web server socket.
        webserver.server_close()

        # Wait briefly for the background thread to exit.
        if webserver_thread:

            # Join the thread with a timeout to avoid hanging shutdown.
            webserver_thread.join(timeout=5)

    # Log that the server has stopped.
    logger.info("Server stopped.")

# Run the server using command-line configuration.
def run_server() -> None:

    # Build the command-line parser for optional config arguments.
    argument_parser = build_argument_parser()

    # Parse command-line arguments for the configuration path.
    arguments = argument_parser.parse_args()

    # Apply configuration values before starting the server.
    configure_from_path(arguments.config)

    # Run the async server in the asyncio event loop.
    asyncio.run(run_async_server())

# Guard the async entry point for direct execution.
if __name__ == "__main__":

    # Execute the server when the script is called directly.
    run_server()
