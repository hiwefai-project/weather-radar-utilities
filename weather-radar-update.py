from websockets.sync.client import connect
import logging
import json
import time

websocket_url = "ws://localhost:8765/update"

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

product = "VMI"
unix_time = int(time.time())
absolute_file_path = "/storage/abc.tiff"
file_url = "http://abc.tiff"

with connect(websocket_url) as websocket:
    message = {
        "productType": product,
        "productDate": unix_time,
        "file": absolute_file_path,
        "url": file_url
    }
    websocket.send(json.dumps(message))
    ack = websocket.recv()
    logger.info("Notified: " + str(ack))
