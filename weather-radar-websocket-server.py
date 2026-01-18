#!/usr/bin/env python3
# Import asyncio for async event loop management.
import asyncio
# Import json for serializing and parsing message payloads.
import json
# Import logging for structured log output.
import logging
# Import signal to handle graceful shutdown signals.
import signal
# Import Set typing for type annotations of subscriber collections.
from typing import Set

# Import WebSocket server helpers and broadcast utility.
from websockets.asyncio.server import serve, broadcast

# Bind to all interfaces so containers or hosts can connect.
HOST = "0.0.0.0"
# Use the default port for the WebSocket server.
PORT = 8765

# Configure logging with timestamps and levels for observability.
logging.basicConfig(
    level=logging.INFO,
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

            # Determine whether any subscribers are available.
            if not SUBSCRIBERS:
                # Log that there are no subscribers to receive the update.
                logger.debug("No subscribers to broadcast to")
            else:
                # Serialize the payload for broadcast.
                text = json.dumps(payload)
                # Broadcast the message to all subscribers.
                broadcast(SUBSCRIBERS, text)
                # Log how many subscribers received the update.
                logger.info("Broadcasted to %d subscriber(s)", len(SUBSCRIBERS))

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
    # Start the server and keep it running while the stop event is unset.
    async with serve(
        route,
        HOST,
        PORT,
        # Limit maximum message size to protect the server.
        max_size=2**20,
        # Enable keepalive pings to detect dead connections.
        ping_interval=20,
        # Configure the ping timeout.
        ping_timeout=20,
        # You could add origin checks with 'origins={...}' if needed.
    ):
        # Log the available endpoints once the server is live.
        logger.info("Server is running. Endpoints: /subscribe, /update")
        # Wait until a shutdown signal is received.
        await stop.wait()
    # Log that the server has stopped.
    logger.info("Server stopped.")


# Guard the async entry point for direct execution.
if __name__ == "__main__":
    # Run the main coroutine in the asyncio event loop.
    asyncio.run(main())
