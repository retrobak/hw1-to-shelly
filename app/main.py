import os
import asyncio
import socket
import json
import httpx
from fastapi import FastAPI
from zeroconf import ServiceInfo, Zeroconf
import aiocoap

# Config
HOMEWIZARD_HOST = os.getenv("HOMEWIZARD_HOST", "192.168.1.50")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2"))
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
DEVICE_NAME = os.getenv("DEVICE_NAME", "ShellyEM-EMU")

app = FastAPI()

state = {
    "wifi_ssid": "emu",
    "em:0": {
        "a_current": 0,
        "b_current": 0,
        "c_current": 0,
        "total_current": 0,
        "a_act_power": 0,
        "b_act_power": 0,
        "c_act_power": 0,
        "total_act_power": 0,
        "a_voltage": 230,
        "b_voltage": 230,
        "c_voltage": 230,
        "total_power_factor": 1,
    },
    "gas:0": {
        "total_m3": 0.0,
        "timestamp": 0
    }
}

# Helper: LAN IP ophalen
def get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    finally:
        s.close()
    return ip

# Poller: haalt waarden op uit HomeWizard P1
async def poller():
    async with httpx.AsyncClient() as client:
        while True:
            try:
                resp = await client.get(f"http://{HOMEWIZARD_HOST}/api/v1/data")
                hw = resp.json()

                # Wifi SSID
                state["wifi_ssid"] = hw.get("wifi_ssid", "emu")

                # Electriciteit
                total_power = hw.get("active_power_w", 0)
                state["em:0"]["total_act_power"] = total_power
                state["em:0"]["a_act_power"] = total_power / 3
                state["em:0"]["b_act_power"] = total_power / 3
                state["em:0"]["c_act_power"] = total_power / 3
                state["em:0"]["total_current"] = total_power / 230

                # Gas
                state["gas:0"]["total_m3"] = hw.get("total_gas_m3", 0.0)
                state["gas:0"]["timestamp"] = hw.get("gas_timestamp", 0)

            except Exception as e:
                print(f"Poller error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

# REST endpoints
@app.get("/status")
async def get_status():
    return {
        "wifi_sta": {"connected": True, "ssid": state["wifi_ssid"], "rssi": -50},
        "emeters": [
            {"power": state["em:0"]["a_act_power"]},
            {"power": state["em:0"]["b_act_power"]},
            {"power": state["em:0"]["c_act_power"]}
        ],
        "total_power": state["em:0"]["total_act_power"],
        "gas": {
            "total_m3": state["gas:0"]["total_m3"],
            "timestamp": state["gas:0"]["timestamp"]
        }
    }

@app.get("/rpc/Shelly.GetStatus")
async def rpc_status():
    return state

# CoAP announce voor Victron Venus
async def coap_announce():
    context = await aiocoap.Context.create_client_context()
    payload = {
        "id": DEVICE_NAME,
        "model": "SHEM-3",
        "app": "EM",
        "ver": "20230905-123456/0.0.1@emu",
    }
    announce_bytes = json.dumps(payload).encode("utf-8")
    while True:
        try:
            request = aiocoap.Message(
                code=aiocoap.POST,
                payload=announce_bytes,
                uri="coap://224.0.1.187:5683/announce"
            )
            await context.request(request).response
            print("Sent CoAP announce")
        except Exception as e:
            print(f"CoAP error: {e}")
        await asyncio.sleep(30)

# Startup: poller + mDNS + CoAP
@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poller())

    # mDNS
    try:
        zeroconf = Zeroconf()
        ip = socket.inet_aton(get_lan_ip())
        info = ServiceInfo(
            "_http._tcp.local.",
            f"{DEVICE_NAME}._http._tcp.local.",
            addresses=[ip],
            port=HTTP_PORT,
            properties={"id": "shellyem-emu", "model": "SHEM-3"},
            server=f"{DEVICE_NAME}.local."
        )
        zeroconf.register_service(info)
        print(f"mDNS registered: {DEVICE_NAME}.local:{HTTP_PORT}")
    except Exception as e:
        print(f"mDNS error: {e}")

    asyncio.create_task(coap_announce())
