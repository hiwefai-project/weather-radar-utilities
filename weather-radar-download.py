# Python program to illustrate Python get current time
# Import datetime utilities for time arithmetic.
from datetime import datetime, timedelta
# Import json for configuration parsing and payload serialization.
import json
# Import logging for structured runtime output.
import logging
# Import os for filesystem checks and directory creation.
import os
# Import time for Unix timestamp conversion and sleeps.
import time
# Import Path for filesystem path management.
from pathlib import Path

# Import pytz to localize timestamps in the configured timezone.
import pytz
# Import magic to verify downloaded file types.
import magic
# Import the WebSocket client helper for synchronous connections.
from websockets.sync.client import connect

# Define the path to the shared JSON configuration file.
CONFIG_PATH = Path(__file__).with_name("config.json")


# Load and return the JSON configuration used by all scripts.
def load_config() -> dict:
    # Open the configuration file with UTF-8 encoding.
    with CONFIG_PATH.open("r", encoding="utf-8") as config_file:
        # Parse the JSON payload into a dictionary.
        return json.load(config_file)


# Load the configuration once at startup.
config = load_config()
# Extract the logging configuration section.
logging_config = config.get("logging", {})
# Normalize the configured log level to uppercase.
log_level_name = logging_config.get("level", "INFO").upper()
# Resolve the log level or fall back to INFO.
log_level = getattr(logging, log_level_name, logging.INFO)
# Extract the configured log file path for downloads.
log_file = logging_config.get("download_log_file")

# Configure logging to file when a log file is provided.
if log_file:
    # Set up file-based logging with UTF-8 encoding.
    logging.basicConfig(filename=log_file, encoding="utf-8", level=log_level)
else:
    # Fall back to standard output logging.
    logging.basicConfig(level=log_level)

# Create a module-level logger for the downloader.
logger = logging.getLogger(__name__)

# Extract the download configuration block.
download_config = config.get("download", {})
# Load the maximum retry count for downloads.
max_trys = download_config.get("max_trys", 7)
# Load the WebSocket URL for update notifications.
websocket_url = download_config.get("websocket_url", "ws://localhost:8765/update")
# Load the radar API endpoint used for downloads.
url = download_config.get("radar_api_url")
# Load the base URL used to construct file URLs.
base_url = download_config.get("base_url")
# Load the base filesystem path for storing downloads.
base_path = Path(download_config.get("base_path"))
# Load the list of product types to download.
products = download_config.get("products", ["VMI"])
# Load the timezone name for timestamp localization.
timezone_name = download_config.get("timezone", "Europe/Rome")
# Load the interval in minutes for scheduled downloads.
interval_minutes = download_config.get("interval_minutes", 10)
# Load the retry delay in seconds between attempts.
retry_sleep_seconds = download_config.get("retry_sleep_seconds", 60)

# Log the startup banner for the downloader.
logger.info("Italian Civil Protection Weather Radar Smart Downloader")

# Create a timezone object for the configured region.
local = pytz.timezone(timezone_name)

# Store the current time in a variable.
current_time = datetime.now()
# Get the current minutes as an integer for interval checks.
minutes = int(current_time.strftime("%M"))

# Check if the current minute aligns with the configured interval.
if minutes % interval_minutes == 0:
    # Zero out seconds and microseconds for consistency.
    current_time = current_time.replace(second=0, microsecond=0)

    # Subtract the configured interval to fetch the previous slice.
    current_time = current_time - timedelta(minutes=interval_minutes)

    # Convert the timestamp to UTC for naming conventions.
    utc_current_time = local.localize(current_time, is_dst=None).astimezone(pytz.utc)

    # Log the UTC timestamp being processed.
    logger.info(utc_current_time)

    # Convert the timestamp to Unix milliseconds for the API payload.
    unix_time = int(1000 * time.mktime(current_time.timetuple()))

    # Build the destination directory for the date-based folder structure.
    file_path = base_path / utc_current_time.strftime("%Y") / utc_current_time.strftime("%m") / utc_current_time.strftime("%d")

    # Ensure the destination directory exists before downloading files.
    if not file_path.exists():
        # Create the directory tree as needed.
        file_path.mkdir(parents=True)

    # Prepare the shared headers for the download API request.
    headers = {
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

    # Iterate through each configured product type.
    for product in products:
        # Construct the filename for the current product.
        file_name = f"rdr0_d01_{utc_current_time.strftime('%Y%m%dZ%H%M')}_{product}.tiff"

        # Build the payload required by the API.
        payload = {
            # Identify which product type to fetch.
            "productType": product,
            # Provide the product timestamp in Unix milliseconds.
            "productDate": unix_time,
        }

        # Build the absolute file path for the downloaded file.
        absolute_file_path = file_path / file_name
        # Construct the public URL for this product.
        file_url = f"{base_url}/{utc_current_time.strftime('%Y')}/{utc_current_time.strftime('%m')}/{utc_current_time.strftime('%d')}/{file_name}"

        # Initialize the retry counter.
        trys = 0

        # Retry until the maximum attempts are exhausted.
        while trys < max_trys:
            # Log the current attempt number.
            logger.info("Try number: %s", trys)

            # Build the curl command for the API request.
            command = (
                f"curl '{url}' "
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
                logger.info("Downloaded!")
                # Open a WebSocket connection to notify subscribers.
                with connect(websocket_url) as websocket:
                    # Build the update payload for the WebSocket server.
                    message = {
                        # Identify the product type in the update.
                        "productType": product,
                        # Provide the product timestamp in Unix milliseconds.
                        "productDate": unix_time,
                        # Provide the local file path for the product.
                        "file": str(absolute_file_path),
                        # Provide the public URL for the product.
                        "url": file_url,
                    }
                    # Send the serialized update message.
                    websocket.send(json.dumps(message))
                    # Wait for an acknowledgment from the server.
                    ack = websocket.recv()
                    # Log the acknowledgment response.
                    logger.info("Notified: %s", ack)
                # Exit the retry loop after a successful download.
                break

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
