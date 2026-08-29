#  PLTS On-Grid IoT & SCADA Simulator

Sistem pemantauan Pembangkit Listrik Tenaga Surya (PLTS) *On-Grid* berbasis **SCADA**, **FastAPI**, **MQTT**, dan **WebSockets**. Dirancang untuk simulasi penuh secara lokal tanpa memerlukan perangkat keras fisik.

---

##  Arsitektur Sistem

```text
+------------------------+        MQTT Topic        +-------------------------+
|      simulator.py      | -----------------------> |    MQTT Broker (1883)   |
| (PLTS Sensor Telemetry)|   "plts/telemetry" (2s)  | (Mosquitto / broker.py) |
+------------------------+                          +-------------------------+
                                                                 |
                                                          MQTT Subscribe
                                                                 v
+------------------------+        WebSockets        +-------------------------+
|       index.html       | <----------------------- |         main.py         |
| (SCADA Web Dashboard)  |       ws://localhost/ws  |    (FastAPI Gateway)    |
+------------------------+                          +-------------------------+
```

---

##  Komponen Proyek

| File | Deskripsi |
| :--- | :--- |
| **`simulator.py`** | Pembangkit data telemetri PLTS On-Grid (Tegangan: 30-36V, Arus: 5-8A, Daya: V×A, Suhu: 25-45°C) menggunakan `paho-mqtt`. |
| **`main.py`** | Backend server FastAPI bertindak sebagai MQTT Subscriber & WebSocket broadcaster (`/ws`). Mengatur CORS & endpoint statis. |
| **`index.html`** | Antarmuka web SCADA bergaya *Industrial Control Room* dengan pembacaan metriks real-time, Live Trend Chart, Event Log, dan **Night Mode Toggle**. |
| **`broker.py`** | *(Opsional)* Micro MQTT broker Python bawaan jika Mosquitto belum terpasang di komputer. |
| **`requirements.txt`** | Daftar pustaka dependensi Python (`fastapi`, `uvicorn`, `paho-mqtt`, `websockets`, `jinja2`). |

---

##  Panduan Menjalankan Sistem

Buka **3 Terminal Terpisah** di direktori proyek: `C:\Users\ok\.gemini\antigravity\scratch\plts-scada-iot`

### Langkah 0: Instalasi Dependensi (Cukup 1 kali)
```powershell
pip install -r requirements.txt
```

---

### Terminal 1: Jalankan MQTT Broker
Pilih salah satu:
- **Opsi A (Menggunakan Broker Python Bawaan):**
  ```powershell
  python broker.py
  ```
- **Opsi B (Menggunakan Eclipse Mosquitto lokal):**
  ```powershell
  mosquitto -v
  ```
- **Opsi C (Menggunakan Docker):**
  ```powershell
  docker run -it -p 1883:1883 eclipse-mosquitto
  ```

---

### Terminal 2: Jalankan FastAPI Backend Server
```powershell
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
> Server akan aktif di `http://localhost:8000` dan WebSocket di `ws://localhost:8000/ws`.

---

### Terminal 3: Jalankan Simulator Sensor PLTS
```powershell
python simulator.py
```
> Simulator akan mempublikasikan data telemetri setiap 2 detik ke MQTT Broker dan mencatatnya ke konsol.

---

##  Akses Dashboard SCADA

Buka browser dan navigasikan ke:
 **[http://localhost:8000](http://localhost:8000)**

### Fitur Interaktif pada Dashboard:
1. **Real-Time Telemetry Display:** Tegangan (30-36V), Arus (5-8A), Daya (W), dan Suhu (25-45°C) terupdate otomatis via WebSocket setiap 2 detik.
2. **Interactive Night Mode:** Klik tombol ** Day Mode /  Night Mode** di pojok kanan atas untuk beralih antara tema gelap Cyber-SCADA dan tema terang Industrial.
3. **Live Trend Chart:** Grafik multivariat dinamis yang memvisualisasikan tren daya, tegangan, dan arus secara real-time.
4. **Live MQTT Stream Console:** Memonitor paket data mentah yang masuk dari broker.
