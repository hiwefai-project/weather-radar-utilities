# Weather Radar Utilities

Utilities for managing data acquisition and distribution for the Italian Department of Civil Protection weather radar products.

## Contents
- **WebSocket server** (`weather-radar-websocket-server.py`): Broadcasts update events to subscribed clients.
- **WebSocket client** (`weather-radar-websocket-client.py`): Subscribes to updates and logs incoming product info.
- **Update notifier** (`weather-radar-update.py`): Sends an update message to the server.

## Requirements
- Python 3.9+
- Packages:
  - `websockets`
  - `websocket-client`
  - `rel`

## Quick start
1. **Start the server**
   ```bash
   python weather-radar-websocket-server.py
   ```

2. **Start a subscriber**
   ```bash
   python weather-radar-websocket-client.py
   ```

3. **Send an update**
   ```bash
   python weather-radar-update.py
   ```

## Configuration notes
- Server host/port are defined at the top of `weather-radar-websocket-server.py`.
- Client update URLs are defined near the top of each script.
