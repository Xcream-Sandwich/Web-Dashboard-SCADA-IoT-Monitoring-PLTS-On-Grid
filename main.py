"""
FastAPI SCADA Backend Server with MQTT Subscriber & WebSocket Relay
Listens to MQTT topic 'plts/telemetry' and broadcasts telemetry data
to web clients connected via WebSockets at /ws.
"""

import asyncio
import json
import os
import sys
from contextlib import asynccontextmanager
from typing import Set, Optional
from datetime import datetime

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import paho.mqtt.client as mqtt

# Configuration
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_TOPIC = "plts/telemetry"
MQTT_CLIENT_ID = "PLTS_FastAPI_Backend_Subscriber"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_HTML_PATH = os.path.join(BASE_DIR, "index.html")

# Global State
event_loop: Optional[asyncio.AbstractEventLoop] = None
latest_telemetry: dict = {
    "device_id": "PLTS-INV-01",
    "timestamp": datetime.utcnow().isoformat(),
    "voltage_v": 0.0,
    "current_a": 0.0,
    "power_w": 0.0,
    "temperature_c": 0.0,
    "total_energy_kwh": 0.0,
    "grid_voltage_v": 220.0,
    "grid_frequency_hz": 50.0,
    "inverter_efficiency_pct": 97.5,
    "grid_status": "WAITING_DATA",
    "system_state": "STANDBY"
}
mqtt_connected = False


class ConnectionManager:
    """Manages active WebSocket connections."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        print(f"[+] WebSocket client connected. Active clients: {len(self.active_connections)}")
        # Send latest telemetry snapshot immediately upon connection
        if latest_telemetry:
            await websocket.send_json(latest_telemetry)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        print(f"[-] WebSocket client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return
        
        dead_connections = set()
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception as exc:
                print(f"[!] Error sending to WebSocket client: {exc}")
                dead_connections.add(connection)
                
        for dead in dead_connections:
            self.disconnect(dead)


manager = ConnectionManager()


# MQTT Callbacks
def on_connect(client, userdata, flags, rc, properties=None):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"[+] MQTT Connected successfully to {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        print(f"[+] Subscribed to topic: {MQTT_TOPIC}")
    else:
        mqtt_connected = False
        print(f"[-] MQTT Connection failed with result code {rc}")


def on_disconnect(client, userdata, flags_or_rc, rc=None, properties=None):
    global mqtt_connected
    mqtt_connected = False
    print("[!] MQTT Disconnected from broker.")


def on_message(client, userdata, msg):
    global latest_telemetry, event_loop
    try:
        payload_str = msg.payload.decode("utf-8")
        data = json.loads(payload_str)
        latest_telemetry = data
        
        # Thread-safe dispatch to FastAPI's asyncio event loop
        if event_loop and event_loop.is_running():
            asyncio.run_coroutine_threadsafe(manager.broadcast(data), event_loop)
    except Exception as e:
        print(f"[-] Error processing MQTT message: {e}")


def init_mqtt_client() -> mqtt.Client:
    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID
        )
    except (AttributeError, TypeError):
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)

    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    return client


mqtt_client = init_mqtt_client()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager handling MQTT connection and background threads."""
    global event_loop
    event_loop = asyncio.get_running_loop()
    
    print("[*] Initializing MQTT Client background connection...")
    try:
        mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        print("[+] MQTT Client loop started in background.")
    except Exception as e:
        print(f"[-] Warning: Failed to initiate MQTT connection: {e}")
        print("[!] Backend will continue running, reconnect attempts will proceed in background.")
        
    yield  # Application runs here
    
    print("[*] Shutting down MQTT Client...")
    mqtt_client.loop_stop()
    mqtt_client.disconnect()
    print("[+] MQTT Client disconnected cleanly.")


# FastAPI Application initialization
app = FastAPI(
    title="PLTS On-Grid SCADA IoT Gateway",
    description="Real-time SCADA WebSocket and MQTT Bridge for Solar Telemetry",
    version="1.0.0",
    lifespan=lifespan
)

# Robust CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/", response_class=HTMLResponse)
async def get_index():
    """Serves the industrial SCADA dashboard HTML."""
    if os.path.exists(INDEX_HTML_PATH):
        with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h1>SCADA Dashboard file (index.html) not found.</h1>", status_code=404)


@app.get("/api/status")
async def get_system_status():
    """Returns the current backend health, MQTT status, and latest telemetry."""
    return {
        "status": "online",
        "mqtt_connected": mqtt_connected,
        "active_websocket_clients": len(manager.active_connections),
        "latest_telemetry": latest_telemetry
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time SCADA telemetry streaming.
    Clients connect to ws://localhost:8000/ws to receive live sensor updates.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive and accept any client pings / messages
            data = await websocket.receive_text()
            # Respond to ping if client sends heartbeats
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as exc:
        print(f"[!] WebSocket exception: {exc}")
        manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
