#!/usr/bin/env python3
"""
mqtt_bridge.py — Bridge Cloud ⇄ Local
- avoids loops by whitelisting topics
"""

import time
import paho.mqtt.client as mqtt

CLOUD_BROKER = "broker.hivemq.com"
LOCAL_BROKER = "127.0.0.1"
TOPIC_FILTER = "parking/#"

print("[Bridge] started (secured mode)")
print(f"  Cloud : {CLOUD_BROKER}")
print(f"  Local : {LOCAL_BROKER}")
print(f"  Topics: {TOPIC_FILTER}")

cloud = mqtt.Client("bridge_cloud_secure")
cloud.tls_set()  # enables TLS

local = mqtt.Client("bridge_local")

ALLOW_CLOUD_TO_LOCAL = {
    "parking/acl/add",
    "parking/acl/del",
    "parking/acl/full",
    "parking/acl/enroll",
    "parking/acl/get",
    "parking/ascenseur/cmd",
    "parking/ascenseur/get",
    "parking/barriere/cmd",
    "parking/barriere_entree/cmd",
    "parking/camera/cmd",
    "parking/config/pin",
    "parking/config/exit_pin",
    "parking/display/text",
    "parking/payment/req",
    "parking/payment/success",

    # --- Radio control (cloud -> local) ---
    "parking/radio/tx/cmd",
    "parking/radio/tx/params",
}

ALLOW_LOCAL_TO_CLOUD = {
    "parking/sensor_gate/present",
    "parking/sensor_gate/heartbeat",
    "parking/sensor_gate/error",
    "parking/acl/list",
    "parking/acl/event",
    "parking/ascenseur/state",
    "parking/barriere",
    "parking/sync/req",

    # --- Radio status (local -> cloud) ---
    "parking/radio/tx/status",
    "parking/radio/tx/error",
}

def connect_with_retry(client: mqtt.Client, host: str, port: int = 1883):
    while True:
        try:
            client.connect(host, port, 60)
            print(f"[Bridge] connected to {host}:{port}")
            return
        except Exception as e:
            print(f"[Bridge] connect failed {host}:{port} -> retry 5s ({e})")
            time.sleep(5)

def on_cloud_message(client, userdata, msg):
    topic = msg.topic
    if topic not in ALLOW_CLOUD_TO_LOCAL:
        return
    try:
        # clean payload to valid UTF-8 text if possible
        try:
            payload_str = msg.payload.decode("utf-8")
            payload_clean = payload_str.encode("utf-8")
        except Exception:
            print(f"⚠️ [Bridge] ignored corrupted binary on {topic}")
            return
        local.publish(topic, payload_clean)
        print(f"☁️→🏠 {topic}")
    except Exception as e:
        print(f"[Bridge] cloud→local error: {e}")

def on_local_message(client, userdata, msg):
    topic = msg.topic
    if topic not in ALLOW_LOCAL_TO_CLOUD:
        return
    try:
        cloud.publish(topic, msg.payload)
        print(f"🏠→☁️ {topic}")
    except Exception as e:
        print(f"[Bridge] local→cloud error: {e}")

cloud.on_message = on_cloud_message
local.on_message = on_local_message

connect_with_retry(cloud, CLOUD_BROKER, 8883)
connect_with_retry(local, LOCAL_BROKER, 1883)

cloud.subscribe(TOPIC_FILTER)
local.subscribe(TOPIC_FILTER)

cloud.loop_start()
local.loop_start()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\n[Bridge] stopped.")
finally:
    cloud.loop_stop()
    local.loop_stop()
