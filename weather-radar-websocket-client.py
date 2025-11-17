import websocket
import rel
import json
import logging


url_ws = "ws://localhost:8765/subscribe"


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

logger.info('Weather Radar Websocket Client')



def on_message(ws, message):
    logger.info(message)
    json_message = json.loads(message)
    if "productType" in json_message:
        if json_message["productType"] == "VMI":
            logger.info(json_message["file"])
            logger.info(json_message["url"])

def on_error(ws, error):
    logger.error(error)

def on_close(ws, close_status_code, close_msg):
    logger.debug("### closed ###")

def on_open(ws):
    logger.debug("Opened connection")

if __name__ == "__main__":
    #websocket.enableTrace(True)
    ws = websocket.WebSocketApp(url_ws,
                              on_open=on_open,
                              on_message=on_message,
                              on_error=on_error,
                              on_close=on_close)

    ws.run_forever(dispatcher=rel, reconnect=5)  # Set dispatcher to automatic reconnection, 5 second reconnect delay if connection closed unexpectedly
    rel.signal(2, rel.abort)  # Keyboard Interrupt
    rel.dispatch()
