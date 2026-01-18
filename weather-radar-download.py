# Python program to illustrate Python get current time
# Importing datetime module
from datetime import datetime, timedelta
import time
import pytz
import os
import sys
import json
import requests
import shutil
import logging
import magic
from websockets.sync.client import connect

max_trys = 7
websocket_url = "ws://localhost:8765/update"
url = "https://radar-api.protezionecivile.it/wide/product/downloadProduct"
base_url = "https://data.meteo.uniparthenope.it/instruments/rdr0/"

base_path = "/storage/ccmmma/prometeo/data/instruments/rdr0/"

logger = logging.getLogger(__name__)
logging.basicConfig(filename='weather-radar-download.log', encoding='utf-8', level=logging.DEBUG)

logger.info('Italian Civil Protection Weather Radar Smart Downloader')

# Products available "VMI", "SRI", "SRT1"
products = [ "VMI" ]

local = pytz.timezone("Europe/Rome")

# storing the current time in the variable
current_time = datetime.now()

# Get the minutes
minutes =  float(current_time.strftime('%M'))

# Check if the minutes are 00, 10, ..., 50
if int(minutes/10) == minutes/10:

    current_time = current_time.replace(second=0, microsecond=0)

    # Subtract 10 minutes
    current_time = current_time - timedelta(minutes=10)

    utc_current_time = local.localize(current_time,is_dst=None).astimezone(pytz.utc)

    logger.info(utc_current_time)

    unix_time = int(1000*time.mktime(current_time.timetuple()))

    file_path = base_path + "/" + utc_current_time.strftime('%Y') + "/" + utc_current_time.strftime('%m') + "/" + utc_current_time.strftime('%d')

    if not os.path.exists(file_path):
        os.makedirs(file_path)

    file_name = "rdr0_d01_" + utc_current_time.strftime('%Y%m%dZ%H%M') + ".tiff"

    headers = {
        "accept": "application/json, text/plain, */*",
        "content-type": "application/json", 
        "origin": "https://radar.protezionecivile.it",
        "priority": "u=1, i",
        "referer": "https://radar.protezionecivile.it/",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site"
    }
    
    for product in products:

        file_name = "rdr0_d01_" + utc_current_time.strftime('%Y%m%dZ%H%M') + "_" + product + ".tiff"


        payload = {
            "productType": product,
            "productDate": unix_time
        }

        absolute_file_path = file_path+"/"+file_name
        file_url = base_url + "/" + utc_current_time.strftime('%Y') + "/" + utc_current_time.strftime('%m') + "/" + utc_current_time.strftime('%d') +"/"+file_name

        trys = 0

        while trys < max_trys:

            logger.info("Try number:" + str(trys))

            command = """curl 'https://radar-api.protezionecivile.it/wide/product/downloadProduct' \
  -H 'accept: application/json, text/plain, */*' \
  -H 'content-type: application/json' \
  -H 'origin: https://radar.protezionecivile.it' \
  -H 'priority: u=1, i' \
  -H 'referer: https://radar.protezionecivile.it/' \
  -H 'sec-fetch-dest: empty' \
  -H 'sec-fetch-mode: cors' \
  -H 'sec-fetch-site: same-site' \
  --data-raw '"""+json.dumps(payload)+"""' --silent --output """ + absolute_file_path
  
            os.system(command)
            mime_type = magic.from_file(absolute_file_path, mime=True)
            
            logger.warning(mime_type)
            
            if "image/tiff" == mime_type:
                logger.info("Downloaded!")
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
                break

            os.remove(absolute_file_path)

            logger.warning("Waiting...")
            time.sleep(60)
            logger.warning("Retrying...")
            trys = trys + 1

