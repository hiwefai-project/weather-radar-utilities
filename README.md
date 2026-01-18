# Weather Radar Utilities

Utilities for managing data acquisition and distribution for the Italian Department of Civil Protection weather radar products.

## Contents
- **Downloader** (`weather-radar-download.py`): Fetches radar products and notifies the WebSocket server.
- **WebSocket server** (`weather-radar-websocket-server.py`): Broadcasts update events to subscribed clients.
- **WebSocket client** (`weather-radar-websocket-client.py`): Subscribes to updates and logs incoming product info.
- **Update notifier** (`weather-radar-update.py`): Sends an update message to the server.

## Requirements
- Python 3.9+
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

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

4. **Run the downloader (cron-friendly launcher)**
   ```bash
   ./weather-radar-download
   ```

## Configuration
All Python scripts read the shared `config.json` file in the repository root. Example:
```json
{
  "logging": { "level": "INFO", "download_log_file": "weather-radar-download.log" },
  "download": {
    "max_trys": 7,
    "websocket_url": "ws://localhost:8765/update",
    "radar_api_url": "https://radar-api.protezionecivile.it/wide/product/downloadProduct",
    "base_url": "https://data.meteo.uniparthenope.it/instruments/rdr0",
    "base_path": "/storage/ccmmma/prometeo/data/instruments/rdr0",
    "products": ["VMI"],
    "timezone": "Europe/Rome",
    "interval_minutes": 10,
    "retry_sleep_seconds": 60
  },
  "websocket_client": { "url": "ws://localhost:8765/subscribe", "product_type": "VMI" },
  "update_sender": {
    "websocket_url": "ws://localhost:8765/update",
    "product_type": "VMI",
    "file_path": "/storage/abc.tiff",
    "file_url": "http://abc.tiff"
  },
  "websocket_server": { "host": "0.0.0.0", "port": 8765 }
}
```

### Cron example
Run the launcher every 10 minutes:
```cron
*/10 * * * * /path/to/weather-radar-utilities/weather-radar-download
```
