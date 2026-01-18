# Import the websocket-client package for WebSocket interactions.
import websocket
# Import rel for reconnection and signal handling utilities.
import rel
# Import json for parsing incoming messages.
import json
# Import logging for structured, configurable output.
import logging

# Define the WebSocket URL for subscribing to updates.
url_ws = "ws://localhost:8765/subscribe"

# Create a module-level logger for this client.
logger = logging.getLogger(__name__)
# Configure logging with a default INFO level.
logging.basicConfig(level=logging.INFO)

# Log a startup banner so operators know the client is running.
logger.info("Weather Radar Websocket Client")


# Handle incoming messages from the server.
def on_message(ws, message):
    # Log the raw message for debugging or audit purposes.
    logger.info(message)
    # Parse the JSON payload into a Python dictionary.
    json_message = json.loads(message)
    # Check that the message contains a product type field.
    if "productType" in json_message:
        # Focus on VMI products, which are of interest here.
        if json_message["productType"] == "VMI":
            # Log the file path associated with the update.
            logger.info(json_message["file"])
            # Log the URL where the product can be fetched.
            logger.info(json_message["url"])


# Handle errors raised by the websocket-client library.
def on_error(ws, error):
    # Log errors at error severity to highlight issues.
    logger.error(error)


# Handle the close event from the server.
def on_close(ws, close_status_code, close_msg):
    # Use debug-level logging for close events to reduce noise.
    logger.debug("### closed ###")


# Handle the open event when the connection is established.
def on_open(ws):
    # Use debug-level logging for connection establishment details.
    logger.debug("Opened connection")


# Run the client only when the script is executed directly.
if __name__ == "__main__":
    # websocket.enableTrace(True)  # Enable this for verbose WebSocket tracing.
    # Create the WebSocketApp with handlers for each event.
    ws = websocket.WebSocketApp(
        url_ws,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    # Run the event loop with auto-reconnect behavior.
    ws.run_forever(dispatcher=rel, reconnect=5)
    # Register a signal handler to terminate on Ctrl+C.
    rel.signal(2, rel.abort)
    # Enter the dispatcher loop to process events.
    rel.dispatch()
