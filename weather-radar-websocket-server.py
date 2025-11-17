#!/usr/bin/env python3
import asyncio
import json
import logging
import signal
from typing import Set

from websockets.asyncio.server import serve, broadcast

HOST = "0.0.0.0"
PORT = 8765

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("ws-bus")

# Active subscriber connections
SUBSCRIBERS = set()


async def subscriber_handler(ws) -> None:
    """Register a subscriber; keep the connection open and ignore any incoming messages."""
    SUBSCRIBERS.add(ws)
    logger.info("Subscriber connected (%d total)", len(SUBSCRIBERS))
    try:
        # Optionally acknowledge the subscription
        await ws.send(json.dumps({"role": "subscriber", "status": "ok"}))
        # Drain any messages (we ignore them) until the socket closes
        async for _ in ws:
            pass
    finally:
        SUBSCRIBERS.discard(ws)
        logger.info("Subscriber disconnected (%d total)", len(SUBSCRIBERS))


async def updater_handler(ws) -> None:
    """Receive JSON messages and broadcast them to all subscribers."""
    logger.info("Updater connected")
    try:
        await ws.send(json.dumps({"role": "updater", "status": "ok"}))
        async for message in ws:
            # Ensure messages are valid JSON text
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                err = {"error": "invalid_json", "detail": "Message must be valid JSON text"}
                await ws.send(json.dumps(err))
                logger.warning("Rejected non-JSON message from updater")
                continue

            if not SUBSCRIBERS:
                logger.debug("No subscribers to broadcast to")
            else:
                # Broadcast to subscribers only
                text = json.dumps(payload)
                broadcast(SUBSCRIBERS, text)
                logger.info("Broadcasted to %d subscriber(s)", len(SUBSCRIBERS))

            # Optional ACK to updater
            await ws.send(json.dumps({"result": "broadcasted"}))
    finally:
        logger.info("Updater disconnected")


async def route(ws) -> None:
    """
    Route connections by path:
      - /subscribe -> subscriber role
      - /update    -> updater role
    """
    # websockets >= 11 exposes the HTTP request as ws.request
    path = getattr(getattr(ws, "request", None), "path", "/")
    if path == "/subscribe":
        await subscriber_handler(ws)
    elif path == "/update":
        await updater_handler(ws)
    else:
        reason = f"Unknown path '{path}'. Use /subscribe or /update."
        logger.warning(reason)
        await ws.close(code=1008, reason=reason)  # Policy Violation


async def main() -> None:
    # Graceful shutdown support
    stop = asyncio.Event()

    def _handle_sig(*_):
        stop.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_sig)
        except NotImplementedError:
            # Windows on Python <3.8 may not support signals in asyncio
            pass

    logger.info("Starting WebSocket server on %s:%d", HOST, PORT)
    async with serve(
        route,
        HOST,
        PORT,
        # Tuning knobs
        max_size=2**20,        # 1 MiB messages
        ping_interval=20,      # keep-alives
        ping_timeout=20,
        # You could add origin checks with 'origins={...}' if needed
    ):
        logger.info("Server is running. Endpoints: /subscribe, /update")
        await stop.wait()
    logger.info("Server stopped.")


if __name__ == "__main__":
    asyncio.run(main())
