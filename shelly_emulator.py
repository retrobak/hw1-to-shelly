#!/usr/bin/env python3
"""
Shelly Pro 3EM Emulator
Reads data from HomeWizard P1 Meter and emulates Shelly Pro 3EM API
"""

import asyncio
import json
import logging
from datetime import datetime
from aiohttp import web, ClientSession, ClientTimeout
from typing import Optional, Dict, Any

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HomeWizardClient:
    """Client to fetch data from HomeWizard P1 Meter"""
    
    def __init__(self, host: str):
        self.host = host
        self.base_url = f"http://{host}/api/v1"
        self.timeout = ClientTimeout(total=5)
        self._cached_data = None
        self._last_fetch = 0
        
    async def fetch_data(self) -> Optional[Dict[str, Any]]:
        """Fetch current measurement from HomeWizard"""
        try:
            async with ClientSession(timeout=self.timeout) as session:
                async with session.get(f"{self.base_url}/data") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self._cached_data = data
                        self._last_fetch = asyncio.get_event_loop().time()
                        logger.debug(f"Fetched data from HomeWizard: {data}")
                        return data
                    else:
                        logger.error(f"Failed to fetch from HomeWizard: {resp.status}")
                        return self._cached_data
        except Exception as e:
            logger.error(f"Error fetching from HomeWizard: {e}")
            return self._cached_data
    
    def get_cached_data(self) -> Optional[Dict[str, Any]]:
        """Get last cached data"""
        return self._cached_data


class ShellyEmulator:
    """Emulates Shelly Pro 3EM API endpoints"""
    
    def __init__(self, hw_client: HomeWizardClient):
        self.hw_client = hw_client
        self.device_id = "shellyproem3-emulator"
        self.start_time = datetime.now()
        
    def convert_hw_to_shelly(self, hw_data: Optional[Dict]) -> Dict[str, Any]:
        """Convert HomeWizard data format to Shelly Pro 3EM format"""
        if not hw_data:
            return self._get_empty_status()
        
        # HomeWizard provides total values, we'll split them across 3 phases
        # For single phase, phase A gets all the power
        total_power = hw_data.get('active_power_w', 0)
        total_current = hw_data.get('active_current_a', 0)
        voltage = hw_data.get('active_voltage_v', 230)  # Default 230V
        
        # Calculate per-phase values (assuming single phase on L1)
        power_a = total_power
        current_a = total_current
        
        return {
            "id": 0,
            "source": "init",
            # Phase A (main phase)
            "a_current": round(current_a, 3),
            "a_voltage": round(voltage, 2),
            "a_act_power": round(power_a, 2),
            "a_aprt_power": round(power_a * 1.02, 2),  # Approximate apparent power
            "a_pf": 0.98,  # Assume good power factor
            "a_freq": 50.0,
            # Phase B (zero for single phase)
            "b_current": 0.0,
            "b_voltage": 0.0,
            "b_act_power": 0.0,
            "b_aprt_power": 0.0,
            "b_pf": 0.0,
            "b_freq": 0.0,
            # Phase C (zero for single phase)
            "c_current": 0.0,
            "c_voltage": 0.0,
            "c_act_power": 0.0,
            "c_aprt_power": 0.0,
            "c_pf": 0.0,
            "c_freq": 0.0,
            # Neutral
            "n_current": 0.0,
            # Totals
            "total_current": round(current_a, 3),
            "total_act_power": round(power_a, 2),
            "total_aprt_power": round(power_a * 1.02, 2),
            # Energy counters (Wh)
            "user_calibrated_phase": [],
        }
    
    def _get_empty_status(self) -> Dict[str, Any]:
        """Return empty status when no data available"""
        return {
            "id": 0,
            "source": "init",
            "a_current": 0.0, "a_voltage": 0.0, "a_act_power": 0.0,
            "a_aprt_power": 0.0, "a_pf": 0.0, "a_freq": 50.0,
            "b_current": 0.0, "b_voltage": 0.0, "b_act_power": 0.0,
            "b_aprt_power": 0.0, "b_pf": 0.0, "b_freq": 0.0,
            "c_current": 0.0, "c_voltage": 0.0, "c_act_power": 0.0,
            "c_aprt_power": 0.0, "c_pf": 0.0, "c_freq": 0.0,
            "n_current": 0.0,
            "total_current": 0.0, "total_act_power": 0.0,
            "total_aprt_power": 0.0,
            "user_calibrated_phase": [],
        }
    
    async def handle_status(self, request: web.Request) -> web.Response:
        """Handle /status endpoint (Gen1 style)"""
        hw_data = self.hw_client.get_cached_data()
        status = self.convert_hw_to_shelly(hw_data)
        
        # Add device info
        response = {
            "wifi_sta": {"connected": True, "ssid": "EmulatedNetwork", "ip": "192.168.1.100"},
            "cloud": {"enabled": False, "connected": False},
            "mqtt": {"connected": False},
            "time": datetime.now().strftime("%H:%M"),
            "unixtime": int(datetime.now().timestamp()),
            "serial": 1,
            "has_update": False,
            "mac": "AABBCCDDEEFF",
            "cfg_changed_cnt": 0,
            "actions_stats": {"skipped": 0},
            "relays": [],
            "emeters": [status],
            "fs_size": 233681,
            "fs_free": 150621,
            "uptime": int((datetime.now() - self.start_time).total_seconds()),
            "ram_total": 51032,
            "ram_free": 38836,
            "update": {"status": "idle", "has_update": False},
        }
        
        return web.json_response(response)
    
    async def handle_shelly(self, request: web.Request) -> web.Response:
        """Handle /shelly endpoint (device info)"""
        response = {
            "type": "SPEM-003CEBEU",
            "mac": "AABBCCDDEEFF",
            "auth": False,
            "fw": "1.0.0-emulator",
            "discoverable": True,
            "longid": 1,
            "num_outputs": 0,
            "num_meters": 3,
            "profile": "triphase"
        }
        return web.json_response(response)
    
    async def handle_settings(self, request: web.Request) -> web.Response:
        """Handle /settings endpoint"""
        response = {
            "device": {
                "type": "SPEM-003CEBEU",
                "mac": "AABBCCDDEEFF",
                "hostname": "shellyproem3-emulator",
                "num_outputs": 0,
                "num_meters": 3,
            },
            "wifi_ap": {"enabled": False},
            "wifi_sta": {"enabled": True, "ssid": "EmulatedNetwork", "ipv4_method": "dhcp"},
            "mqtt": {"enable": False},
            "sntp": {"server": "time.google.com"},
            "login": {"enabled": False},
            "pin_code": "",
            "name": "Shelly Pro 3EM Emulator",
            "fw": "1.0.0-emulator",
            "discoverable": True,
            "build_info": {"build_id": "emulator", "build_timestamp": "2025-01-01T00:00:00Z"},
            "cloud": {"enabled": False},
        }
        return web.json_response(response)
    
    async def handle_emeter(self, request: web.Request) -> web.Response:
        """Handle /emeter/0 endpoint"""
        hw_data = self.hw_client.get_cached_data()
        emeter_data = self.convert_hw_to_shelly(hw_data)
        return web.json_response(emeter_data)
    
    async def handle_rpc_status(self, request: web.Request) -> web.Response:
        """Handle Gen2 RPC style /rpc/EM.GetStatus"""
        hw_data = self.hw_client.get_cached_data()
        
        if not hw_data:
            total_power = 0
            voltage = 0
            current = 0
        else:
            total_power = hw_data.get('active_power_w', 0)
            voltage = hw_data.get('active_voltage_v', 230)
            current = hw_data.get('active_current_a', 0)
        
        response = {
            "id": 0,
            "a_current": round(current, 3),
            "a_voltage": round(voltage, 2),
            "a_act_power": round(total_power, 2),
            "a_aprt_power": round(total_power * 1.02, 2),
            "a_pf": 0.98,
            "a_freq": 50.0,
            "b_current": 0.0,
            "b_voltage": 0.0,
            "b_act_power": 0.0,
            "b_aprt_power": 0.0,
            "b_pf": 0.0,
            "b_freq": 0.0,
            "c_current": 0.0,
            "c_voltage": 0.0,
            "c_act_power": 0.0,
            "c_aprt_power": 0.0,
            "c_pf": 0.0,
            "c_freq": 0.0,
            "n_current": 0.0,
            "total_current": round(current, 3),
            "total_act_power": round(total_power, 2),
            "total_aprt_power": round(total_power * 1.02, 2),
        }
        
        return web.json_response(response)


async def poll_homewizard(hw_client: HomeWizardClient):
    """Background task to poll HomeWizard regularly"""
    while True:
        try:
            await hw_client.fetch_data()
            await asyncio.sleep(1)  # Poll every second for fast updates
        except Exception as e:
            logger.error(f"Error in polling task: {e}")
            await asyncio.sleep(5)


async def start_background_tasks(app):
    """Start background tasks"""
    hw_client = app['hw_client']
    app['poll_task'] = asyncio.create_task(poll_homewizard(hw_client))


async def cleanup_background_tasks(app):
    """Cleanup background tasks"""
    app['poll_task'].cancel()
    await app['poll_task']


def create_app(homewizard_host: str) -> web.Application:
    """Create and configure the web application"""
    hw_client = HomeWizardClient(homewizard_host)
    emulator = ShellyEmulator(hw_client)
    
    app = web.Application()
    app['hw_client'] = hw_client
    app['emulator'] = emulator
    
    # Register routes (Gen1 API style)
    app.router.add_get('/status', emulator.handle_status)
    app.router.add_get('/shelly', emulator.handle_shelly)
    app.router.add_get('/settings', emulator.handle_settings)
    app.router.add_get('/emeter/0', emulator.handle_emeter)
    
    # Gen2 RPC style
    app.router.add_get('/rpc/EM.GetStatus', emulator.handle_rpc_status)
    
    # Background tasks
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    
    return app


if __name__ == '__main__':
    import os
    
    # Configuration from environment variables
    HOMEWIZARD_HOST = os.getenv('HOMEWIZARD_HOST', '192.168.1.50')
    PORT = int(os.getenv('PORT', 8080))
    
    logger.info(f"Starting Shelly Pro 3EM Emulator")
    logger.info(f"HomeWizard P1 Meter: {HOMEWIZARD_HOST}")
    logger.info(f"Listening on port: {PORT}")
    
    app = create_app(HOMEWIZARD_HOST)
    web.run_app(app, host='0.0.0.0', port=PORT)
