# Import the WebSocket client helper for synchronous connections.
from websockets.sync.client import connect
# Import logging for structured runtime messages.
import logging
# Import json to serialize the update payload.
import json
# Import time to generate a Unix timestamp.
import time
# Import Path for loading the shared configuration file.
from pathlib import Path

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

# Configure logging with the configured log level.
logging.basicConfig(level=log_level)

# Create a module-level logger for consistent log output.
logger = logging.getLogger(__name__)

# Extract the update sender configuration section.
update_config = config.get("update_sender", {})

# Define the WebSocket endpoint for update messages.
websocket_url = update_config.get("websocket_url", "ws://localhost:8765/update")

# Define the product identifier used by the update message.
product = update_config.get("product_type", "VMI")

# Point to the absolute path where the file is stored.
absolute_file_path = update_config.get("file_path", "/storage/abc.tiff")

# Provide the public URL where the file can be downloaded.
file_url = update_config.get("file_url", "http://abc.tiff")

# Capture the current Unix time to include in the update.
unix_time = int(time.time())

# Open a WebSocket connection and ensure it closes cleanly afterward.
with connect(websocket_url) as websocket:

    # Build the update payload the server expects.
    message = {
        # Identify which product type is being updated.
        "productType": product,
        # Provide the product timestamp in Unix seconds.
        "productDate": unix_time,
        # Provide the filesystem location of the product.
        "file": absolute_file_path,
        # Provide a URL for clients to download the product.
        "url": file_url,
    }

    # Send the serialized JSON payload to the server.
    websocket.send(json.dumps(message))

    # Wait for the server acknowledgment.
    ack = websocket.recv()

    # Log the acknowledgment for visibility.
    logger.info("Notified: %s", ack)
