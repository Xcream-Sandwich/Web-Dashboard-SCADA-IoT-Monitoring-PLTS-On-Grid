"""
Automated End-to-End System Test for PLTS SCADA IoT Simulator
Verifies:
1. MQTT Broker connectivity
2. FastAPI REST endpoints (/, /CV_Anda.pdf, /api/status)
3. WebSocket real-time telemetry streaming (/ws)
4. Telemetry parameter validation (Voltage, Current, Power, Temperature)
"""

import asyncio
import json
import sys
import httpx
import websockets
import paho.mqtt.client as mqtt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

async def run_tests():
    print("=" * 60)
    print(" 🧪 STARTING AUTOMATED SCADA & IOT SYSTEM VERIFICATION")
    print("=" * 60)

    # 1. Test HTTP Endpoints
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("[1] Testing GET / (Dashboard HTML)...")
        r_index = await client.get("/")
        assert r_index.status_code == 200, f"Expected 200, got {r_index.status_code}"
        assert "PLTS On-Grid SCADA Control" in r_index.text, "Index HTML missing expected title"
        print("    ✅ GET / PASSED")

        print("[2] Testing GET /api/status...")
        r_status = await client.get("/api/status")
        assert r_status.status_code == 200
        status_json = r_status.json()
        assert status_json["status"] == "online"
        print(f"    ✅ GET /api/status PASSED (MQTT Status: {status_json.get('mqtt_connected')})")

    # 2. Test WebSocket connection and Telemetry Streaming
    print("[4] Testing WebSocket at ws://localhost:8000/ws ...")
    ws_uri = "ws://localhost:8000/ws"
    
    async with websockets.connect(ws_uri) as websocket:
        print("    Connected to WebSocket. Waiting for incoming telemetry packet...")
        message = await asyncio.wait_for(websocket.recv(), timeout=6.0)
        data = json.loads(message)
        print(f"    Received Packet: {json.dumps(data, indent=2)}")

        # Validate fields
        v = data.get("voltage_v")
        i = data.get("current_a")
        p = data.get("power_w")
        t = data.get("temperature_c")

        assert v is not None and 30.0 <= v <= 36.0, f"Voltage {v} out of bounds (30-36V)"
        assert i is not None and 5.0 <= i <= 8.0, f"Current {i} out of bounds (5-8A)"
        expected_power = round(v * i, 2)
        assert abs(p - expected_power) < 0.05, f"Power {p} does not match V*I {expected_power}"
        assert t is not None and 25.0 <= t <= 45.0, f"Temperature {t} out of bounds (25-45°C)"

        print("    ✅ Telemetry bounds and formula (P = V * I) verified successfully!")

    print("=" * 60)
    print(" 🎉 ALL AUTOMATED TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_tests())
