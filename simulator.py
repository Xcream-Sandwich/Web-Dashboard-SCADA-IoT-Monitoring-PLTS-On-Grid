"""
PLTS On-Grid Solar Telemetry Simulator
Simulates real-time telemetry from a solar photovoltaic (PV) array and on-grid inverter,
publishing measurements to a local MQTT broker (localhost:1883) every 2 seconds.
"""

import time
import json
import random
import math
import sys
from datetime import datetime, timezone
import paho.mqtt.client as mqtt

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# MQTT Configuration
MQTT_BROKER = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "plts/telemetry"
MQTT_CLIENT_ID = "PLTS_Solar_Sensor_Simulator"
PUBLISH_INTERVAL_SECONDS = 2.0

def create_mqtt_client():
    """Create MQTT client handling both paho-mqtt v1 and v2 API versions."""
    try:
        # Paho MQTT v2.0+
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=MQTT_CLIENT_ID
        )
    except (AttributeError, TypeError):
        # Fallback for Paho MQTT v1.x
        client = mqtt.Client(client_id=MQTT_CLIENT_ID)
    
    return client

class PLTSSimulator:
    def __init__(self):
        # Base simulation values
        self.step_counter = 0
        self.total_energy_kwh = 124.50  # Starting initial cumulative energy
        
    def generate_telemetry(self) -> dict:
        """
        Generate realistic On-Grid PLTS telemetry data.
        - Voltage: 30.0 - 36.0 V
        - Current: 5.0 - 8.0 A
        - Power: Voltage * Current (W)
        - Temperature: 25.0 - 45.0 °C
        """
        self.step_counter += 1
        
        # Add smooth solar irradiance variation using sine wave + small noise
        cycle = math.sin(self.step_counter * 0.05)  # slow smooth curve
        noise_v = random.uniform(-0.3, 0.3)
        noise_i = random.uniform(-0.2, 0.2)
        noise_t = random.uniform(-0.5, 0.5)
        
        # 1. Voltage: 30.0 - 36.0 V
        # Center around 33.0V with amplitude 2.5V + noise
        voltage = round(33.0 + (2.5 * cycle) + noise_v, 2)
        voltage = max(30.0, min(36.0, voltage))
        
        # 2. Current: 5.0 - 8.0 A
        # Center around 6.5A with amplitude 1.2A + noise
        current = round(6.5 + (1.2 * cycle) + noise_i, 2)
        current = max(5.0, min(8.0, current))
        
        # 3. Power: V * I (Watt)
        power = round(voltage * current, 2)
        
        # 4. Temperature: 25.0 - 45.0 °C (correlates with power/irradiance)
        temp = round(35.0 + (8.0 * cycle) + noise_t, 2)
        temp = max(25.0, min(45.0, temp))
        
        # 5. Calculate cumulative energy (kWh)
        energy_increment = (power * (PUBLISH_INTERVAL_SECONDS / 3600.0)) / 1000.0
        self.total_energy_kwh = round(self.total_energy_kwh + energy_increment, 4)
        
        # 6. Grid & Inverter Auxiliary Telemetry
        grid_voltage = round(220.0 + random.uniform(-1.5, 1.5), 1)
        grid_frequency = round(50.0 + random.uniform(-0.08, 0.08), 2)
        inverter_efficiency = round(97.2 + random.uniform(-0.3, 0.4), 1)
        
        payload = {
            "device_id": "PLTS-INV-01",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "voltage_v": voltage,
            "current_a": current,
            "power_w": power,
            "temperature_c": temp,
            "total_energy_kwh": self.total_energy_kwh,
            "grid_voltage_v": grid_voltage,
            "grid_frequency_hz": grid_frequency,
            "inverter_efficiency_pct": inverter_efficiency,
            "grid_status": "SYNCHRONIZED",
            "system_state": "ON_GRID_NORMAL"
        }
        return payload

def main():
    print("=" * 60)
    print(" ☀️  PLTS ON-GRID TELEMETRY SIMULATOR (MQTT PRODUCER)")
    print("=" * 60)
    print(f"[*] Target Broker : {MQTT_BROKER}:{MQTT_PORT}")
    print(f"[*] MQTT Topic    : {MQTT_TOPIC}")
    print(f"[*] Interval      : {PUBLISH_INTERVAL_SECONDS} seconds")
    print("-" * 60)
    
    client = create_mqtt_client()
    simulator = PLTSSimulator()
    
    connected = False
    while not connected:
        try:
            print(f"[>] Connecting to MQTT broker at {MQTT_BROKER}:{MQTT_PORT}...")
            client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
            client.loop_start()
            connected = True
            print("[+] Successfully connected to MQTT Broker!")
        except Exception as e:
            print(f"[-] Connection failed: {e}")
            print("[!] Retrying in 3 seconds... (Make sure MQTT Broker is running)")
            time.sleep(3)
            
    print("-" * 60)
    print("[*] Starting telemetry transmission. Press Ctrl+C to stop.")
    print("-" * 60)
    
    try:
        while True:
            telemetry = simulator.generate_telemetry()
            payload_str = json.dumps(telemetry)
            
            result = client.publish(MQTT_TOPIC, payload_str, qos=1)
            
            # Print formatted log to terminal
            ts = datetime.now().strftime("%H:%M:%S")
            print(f"[{ts}] PUBLISH -> {MQTT_TOPIC}")
            print(f"       ⚡ Tegangan: {telemetry['voltage_v']:>5.2f} V | 🔌 Arus: {telemetry['current_a']:>4.2f} A | "
                  f"⚡ Daya: {telemetry['power_w']:>6.2f} W | 🌡️ Suhu: {telemetry['temperature_c']:>5.2f} °C")
            
            time.sleep(PUBLISH_INTERVAL_SECONDS)
            
    except KeyboardInterrupt:
        print("\n[!] Simulator stopped by user.")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[*] MQTT client disconnected.")

if __name__ == "__main__":
    main()
