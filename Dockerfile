FROM python:3.11-slim

# Install libmagic for python-magic support.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory for the application.
WORKDIR /app

# Copy dependency definitions first for efficient layer caching.
COPY requirements.txt ./

# Install Python dependencies.
RUN pip install --no-cache-dir -r requirements.txt

# Copy the WebSocket server and default configuration.
COPY weather-radar-websocket-server.py config.json ./

# Expose the WebSocket server port.
EXPOSE 8765

# Run the WebSocket server.
CMD ["python", "weather-radar-websocket-server.py"]
