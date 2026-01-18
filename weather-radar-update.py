# Import the WebSocket client helper for synchronous connections.
from websockets.sync.client import connect
# Import the logging module to emit structured runtime messages.
import logging
# Import json to serialize the update payload.
import json
# Import time to generate a Unix timestamp.
import time

# Define the WebSocket endpoint for update messages.
websocket_url = "ws://localhost:8765/update"

# Create a module-level logger for consistent log output.
logger = logging.getLogger(__name__)
# Configure logging with an INFO default level.
logging.basicConfig(level=logging.INFO)

# Define the product identifier used by the update message.
product = "VMI"
# Capture the current Unix time to include in the update.
unix_time = int(time.time())
# Point to the absolute path where the file is stored.
absolute_file_path = "/storage/abc.tiff"
# Provide the public URL where the file can be downloaded.
file_url = "http://abc.tiff"

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
