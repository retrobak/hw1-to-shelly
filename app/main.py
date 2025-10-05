import os
import asyncio
import time
import socket
import httpx
from fastapi import FastAPI, Response, status
from zeroconf import ServiceInfo
from zeroconf.asyncio import AsyncZeroconf
import platform
import traceback
import netifaces

app = FastAPI()

HOMEWIZARD_HOST = os.getenv("HOMEWIZARD_HOST", "192.168.1.50")
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
DEVICE_NAME = os.getenv("DEVICE_NAME", "P1-Proxy")
DEVICE_ID = os.getenv("DEVICE_ID", DEVICE_NAME)
CACHE_TTL = 3  # seconds

# Simple in-memory cache
cache = {
    "data": None,
    "timestamp": 0
}

# Helper to get LAN IP
def get_lan_ip():
    try:
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr['addr']
                    if not ip.startswith('127.'):
                        return ip
        return "127.0.0.1"
    except Exception as e:
        print(f"[ERROR] get_lan_ip: {e}")
        return "127.0.0.1"

@app.get("/api/v1/data")
async def proxy_data():
    now = time.time()
    # Serve from cache if not expired
    if cache["data"] is not None and (now - cache["timestamp"] < CACHE_TTL):
        return Response(content=cache["data"], media_type="application/json")
    # Otherwise, fetch from HomeWizard
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"http://{HOMEWIZARD_HOST}/api/v1/data", timeout=5)
            resp.raise_for_status()
            cache["data"] = resp.text
            cache["timestamp"] = now
            return Response(content=resp.text, media_type="application/json")
    except Exception as e:
        print(f"[ERROR] Proxy fetch failed: {e}")
        if cache["data"] is not None:
            # Serve stale cache if available
            return Response(content=cache["data"], media_type="application/json", status_code=status.HTTP_206_PARTIAL_CONTENT)
        return Response(content='{"error": "Failed to fetch from HomeWizard"}', media_type="application/json", status_code=502)

@app.on_event("startup")
async def startup_event():
    try:
        print("[DEBUG] Starting mDNS announcement...")
        lan_ip = get_lan_ip()
        async_zeroconf = AsyncZeroconf(interfaces=[lan_ip])
        ip = socket.inet_aton(lan_ip)
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{DEVICE_NAME}._http._tcp.local.",
            addresses=[ip],
            port=HTTP_PORT,
            properties={"id": DEVICE_ID, "type": "p1-proxy"},
            server=f"{DEVICE_NAME}.local."
        )
        await async_zeroconf.async_register_service(info)
        print(f"[DEBUG] mDNS registered: {DEVICE_NAME}.local:{HTTP_PORT}")
    except Exception as e:
        print(f"[ERROR] mDNS error: {e}")
        traceback.print_exc()
        if platform.system().lower() == "windows":
            print(f"Note: mDNS/zeroconf may not work in Docker on Windows. Run natively or use Linux for full support.")
