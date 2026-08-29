"""
Embedded Lightweight MQTT Broker (Python Native)
Provides a standalone MQTT 3.1.1 broker on localhost:1883 without needing Mosquitto or Docker.
Supports CONNECT, PUBLISH, SUBSCRIBE, PINGREQ, and DISCONNECT packets.
"""

import asyncio
import struct
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

HOST = "0.0.0.0"
PORT = 1883

class MQTTServer:
    def __init__(self):
        # Map topic -> set of (writer, client_id)
        self.subscribers = {}
        self.clients = set()

    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_addr = writer.get_extra_info("peername")
        client_id = f"client-{id(writer)}"
        self.clients.add(writer)
        print(f"[Broker] New connection from {client_addr}")

        try:
            while not reader.at_eof():
                # Read fixed header byte 1
                header = await reader.read(1)
                if not header:
                    break
                
                packet_type = header[0] >> 4
                flags = header[0] & 0x0F

                # Read Remaining Length (variable length encoding)
                multiplier = 1
                length = 0
                while True:
                    len_byte = await reader.read(1)
                    if not len_byte:
                        break
                    digit = len_byte[0]
                    length += (digit & 127) * multiplier
                    multiplier *= 128
                    if (digit & 128) == 0:
                        break

                payload = await reader.readexactly(length) if length > 0 else b""

                # 1. CONNECT (Type 1)
                if packet_type == 1:
                    # Send CONNACK (0x20, length 2: flags 0x00, return code 0x00)
                    connack = bytes([0x20, 0x02, 0x00, 0x00])
                    writer.write(connack)
                    await writer.drain()
                    print(f"[Broker] Client connected and authenticated.")

                # 2. PUBLISH (Type 3)
                elif packet_type == 3:
                    dup = (flags >> 3) & 1
                    qos = (flags >> 1) & 3
                    retain = flags & 1
                    
                    # Parse Topic Name
                    topic_len = (payload[0] << 8) | payload[1]
                    topic = payload[2:2+topic_len].decode("utf-8", errors="ignore")
                    idx = 2 + topic_len

                    packet_id = None
                    if qos > 0:
                        packet_id = (payload[idx] << 8) | payload[idx+1]
                        idx += 2

                    msg_content = payload[idx:]

                    # PUBACK if QoS 1
                    if qos == 1 and packet_id is not None:
                        puback = bytes([0x40, 0x02, (packet_id >> 8) & 0xFF, packet_id & 0xFF])
                        writer.write(puback)
                        await writer.drain()

                    # Broadcast to subscribers
                    await self.broadcast(topic, msg_content)

                # 3. SUBSCRIBE (Type 8)
                elif packet_type == 8:
                    if len(payload) >= 2:
                        packet_id = (payload[0] << 8) | payload[1]
                        idx = 2
                        while idx < len(payload):
                            t_len = (payload[idx] << 8) | payload[idx+1]
                            sub_topic = payload[idx+2 : idx+2+t_len].decode("utf-8", errors="ignore")
                            requested_qos = payload[idx+2+t_len]
                            idx += 2 + t_len + 1

                            if sub_topic not in self.subscribers:
                                self.subscribers[sub_topic] = set()
                            self.subscribers[sub_topic].add(writer)
                            print(f"[Broker] Client subscribed to: '{sub_topic}'")

                        # Send SUBACK (0x90, length 3: packet_id(2), granted_qos(1))
                        suback = bytes([0x90, 0x03, (packet_id >> 8) & 0xFF, packet_id & 0xFF, 0x00])
                        writer.write(suback)
                        await writer.drain()

                # 4. PINGREQ (Type 12)
                elif packet_type == 12:
                    # PINGRESP (0xD0, length 0)
                    writer.write(bytes([0xD0, 0x00]))
                    await writer.drain()

                # 5. DISCONNECT (Type 14)
                elif packet_type == 14:
                    break

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            pass
        except Exception as e:
            print(f"[Broker] Client handler error: {e}")
        finally:
            print(f"[Broker] Client disconnected: {client_addr}")
            self.clients.discard(writer)
            for topic, subs in self.subscribers.items():
                subs.discard(writer)
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def broadcast(self, topic: str, msg_content: bytes):
        topic_bytes = topic.encode("utf-8")
        topic_len = len(topic_bytes)
        
        # Build PUBLISH packet (QoS 0)
        var_header = struct.pack("!H", topic_len) + topic_bytes
        body = var_header + msg_content
        rem_len = len(body)
        
        # Encode remaining length
        encoded_len = bytearray()
        val = rem_len
        while True:
            byte = val % 128
            val = val // 128
            if val > 0:
                byte |= 0x80
            encoded_len.append(byte)
            if val <= 0:
                break

        packet = bytes([0x30]) + bytes(encoded_len) + body

        dead_writers = set()
        # Match topic directly or wildcard
        for sub_topic, writers in self.subscribers.items():
            if sub_topic == topic or sub_topic == "#" or (sub_topic.endswith("/#") and topic.startswith(sub_topic[:-2])):
                for w in list(writers):
                    try:
                        w.write(packet)
                        await w.drain()
                    except Exception:
                        dead_writers.add(w)

        for dw in dead_writers:
            for subs in self.subscribers.values():
                subs.discard(dw)


async def main():
    broker = MQTTServer()
    server = await asyncio.start_server(broker.handle_client, HOST, PORT)
    print("=" * 60)
    print(" 📡 STANDALONE PYTHON MQTT BROKER (PORT 1883)")
    print("=" * 60)
    print(f"[*] Listening on {HOST}:{PORT}")
    print("[*] Ready for telemetry and SCADA subscriber connections.")
    print("=" * 60)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Broker stopped.")
