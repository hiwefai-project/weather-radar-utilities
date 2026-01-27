# Import argparse for command-line configuration.
import argparse

# Import the websocket-client package for WebSocket interactions.
import websocket

# Import rel for reconnection and signal handling utilities.
import rel

# Import json for parsing incoming messages.
import json

# Import logging for structured, configurable output.
import logging

# Import Path for loading the shared configuration file.
from pathlib import Path

# Define the default path to the shared JSON configuration file.
DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.json")

# Build the argument parser for command-line options.
def build_argument_parser() -> argparse.ArgumentParser:

    # Create the argument parser with a helpful description.
    parser = argparse.ArgumentParser(
        description="Weather Radar Websocket Client",
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

# Run the WebSocket client using the provided configuration path.
def run_client(config_path: Path) -> None:

    # Load the shared configuration from the specified file.
    config = load_config(config_path)

    # Extract the logging configuration section.
    logging_config = config.get("logging", {})

    # Normalize the configured log level to uppercase.
    log_level_name = logging_config.get("level", "INFO").upper()

    # Resolve the log level or fall back to INFO.
    log_level = getattr(logging, log_level_name, logging.INFO)

    # Configure logging with a default INFO level.
    logging.basicConfig(level=log_level)

    # Create a module-level logger for this client.
    logger = logging.getLogger(__name__)

    # Extract the WebSocket client configuration section.
    client_config = config.get("websocket_client", {})

    # Define the WebSocket URL for subscribing to updates.
    url_ws = client_config.get("url", "ws://localhost:8765/subscribe")

    # Define the product type to filter on for logging.
    product_type = client_config.get("product_type", "VMI")

    # Log a startup banner so operators know the client is running.
    logger.info("Weather Radar Websocket Client")

    # Log the configuration source path for traceability.
    logger.info("Using configuration file: %s", config_path)

    # Handle incoming messages from the server.
    def on_message(ws, message):

        # Log the raw message for debugging or audit purposes.
        logger.info(message)

        # Parse the JSON payload into a Python dictionary.
        json_message = json.loads(message)

        # Check that the message contains a product type field.
        if "productType" in json_message:

            # Focus on the configured product type of interest.
            if json_message["productType"] == product_type:

                # Log the file path associated with the update.
                logger.info(json_message["file"])

                # Log the URL where the product can be fetched.
                logger.info(json_message["url"])

    # Handle errors raised by the websocket-client library.
    def on_error(wsock, error):

        # Log errors at error severity to highlight issues.
        logger.error(error)

    # Handle the close event from the server.
    def on_close(wsock, close_status_code, close_msg):

        # Use debug-level logging for close events to reduce noise.
        logger.debug("### closed ###")

    # Handle the open event when the connection is established.
    def on_open(wsock):

        # Use debug-level logging for connection establishment details.
        logger.debug("Opened connection")

    # Enable this for verbose WebSocket tracing.
    #websocket.enableTrace(True)

    # Create the WebSocketApp with handlers for each event.
    wsock = websocket.WebSocketApp(
        url_ws,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )

    # Run the event loop with auto-reconnect behavior.
    wsock.run_forever(dispatcher=rel, reconnect=5)

    # Register a signal handler to terminate on Ctrl+C.
    rel.signal(2, rel.abort)

    # Enter the dispatcher loop to process events.
    rel.dispatch()

# Run the client only when the script is executed directly.
if __name__ == "__main__":

    # Build the command-line parser for optional config arguments.
    argument_parser = build_argument_parser()

    # Parse command-line arguments for the configuration path.
    arguments = argument_parser.parse_args()

    # Execute the client using the requested configuration file.
    run_client(arguments.config)
