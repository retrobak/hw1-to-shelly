FROM python:3.11-slim

WORKDIR /app
COPY app /app

# Install build dependencies for netifaces, then clean up
RUN apt-get update \
    && apt-get install -y gcc python3-dev \
    && pip install --no-cache-dir fastapi uvicorn httpx zeroconf aiocoap==0.4.7 netifaces \
    && apt-get remove -y gcc python3-dev \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
