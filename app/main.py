import os
import asyncio
from fastapi import FastAPI
import httpx
from typing import Dict

HOMEWIZARD_HOST = os.getenv("HOMEWIZARD_HOST", "192.168.1.50")
POLL_INTERVAL = float(os.getenv("POLL_INTERVAL", "2"))
HTTP_PORT = int(os.getenv("HTTP_PORT", "8080"))
DEVICE_NAME = os.getenv("DEVICE_NAME", "ShellyEM-EMU")

app = FastAPI(title="Shelly EM Gen3 Emulator")

state = {
    "total_power_w": 0.0,
    "total_import_kwh": 0.0,
    "total_export_kwh": 0.0,
    "power_l1_w": 0.0,
    "power_l2_w": 0.0,
    "power_l3_w": 0.0,
    "gas_m3": 0.0,
    "tariff": 1
}

async def fetch_homewizard(client: httpx.AsyncClient) -> Dict:
    url = f"http://{HOMEWIZARD_HOST}/api/v1/data"
    try:
        r = await client.get(url, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching HomeWizard: {e}")
        return {}

async def poller():
    async with httpx.AsyncClient() as client:
        while True:
            data = await fetch_homewizard(client)
            if data:
                try:
                    state["total_power_w"] = data.get("active_power_w", 0.0)
                    state["total_import_kwh"] = data.get("total_power_import_kwh", 0.0)
                    state["total_export_kwh"] = data.get("total_power_export_kwh", 0.0)
                    state["tariff"] = data.get("active_tariff", 1)
                    state["gas_m3"] = data.get("total_gas_m3", 0.0)

                    # Voorbereiding voor 3 fasen support:
                    state["power_l1_w"] = data.get("active_power_l1_w", 0.0)
                    state["power_l2_w"] = data.get("active_power_l2_w", 0.0)
                    state["power_l3_w"] = data.get("active_power_l3_w", 0.0)

                except Exception as e:
                    print(f"Parse error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(poller())

@app.get("/status")
async def get_status():
    """
    Shelly-achtige status endpoint.
    """
    return {
        "device": DEVICE_NAME,
        "emulated": "shelly_em_gen3",
        "total_power_w": state["total_power_w"],
        "channels": {
            "total_import_kwh": state["total_import_kwh"],
            "total_export_kwh": state["total_export_kwh"],
            "l1_power_w": state["power_l1_w"],
            "l2_power_w": state["power_l2_w"],
            "l3_power_w": state["power_l3_w"],
        },
        "gas_m3": state["gas_m3"],
        "tariff": state["tariff"]
    }

@app.get("/rpc/Shelly.GetStatus")
async def shelly_rpc_status():
    """
    Nabootsing van Shelly RPC status API.
    """
    return {
        "emeters": [
            {"id": 0, "power": state["power_l1_w"], "total": state["total_import_kwh"]},
            {"id": 1, "power": state["power_l2_w"], "total": state["total_import_kwh"]},
            {"id": 2, "power": state["power_l3_w"], "total": state["total_import_kwh"]},
        ],
        "total_power": state["total_power_w"],
        "export_kwh": state["total_export_kwh"],
        "gas_m3": state["gas_m3"],
        "tariff": state["tariff"]
    }
