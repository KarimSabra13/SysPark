#!/usr/bin/env python3
"""
sensor_gate.py — GPIO17 (BeagleY-AI) -> MQTT
- Publishes debounced presence on parking/sensor_gate/present (0/1, retain)
- Publishes heartbeat on parking/sensor_gate/heartbeat (epoch seconds, retain)
- Publishes errors on parking/sensor_gate/error (text, retain)
- Fail-safe: if GPIO read fails repeatedly, force present=1 (prevent closing)
"""

import time
import subprocess
import paho.mqtt.client as mqtt


# --- MQTT ---
BROKER_HOST = "127.0.0.1"
BROKER_PORT = 1883
MQTT_CLIENT_ID = "sensor_gate_b"

TOPIC_PRESENT = "parking/sensor_gate/present"
TOPIC_HEARTBEAT = "parking/sensor_gate/heartbeat"
TOPIC_ERROR = "parking/sensor_gate/error"

# --- GPIO (libgpiod CLI) ---
GPIO_LINE_NAME = "GPIO17"   # must match `gpioinfo` line name

# --- Filtering / timing ---
POLL_PERIOD_S = 0.05        # 50 ms polling
STABLE_MS = 300             # raw must stay unchanged for >= this time to validate

# --- Health monitoring ---
HEARTBEAT_S = 2.0           # publish heartbeat every 2 seconds
READ_FAIL_THRESHOLD = 5     # consecutive failures before declaring sensor error
ERROR_REPEAT_S = 5.0        # don't spam error more often than every 5 seconds


def mqtt_publish(client: mqtt.Client, topic: str, payload: bytes, retain: bool = True) -> None:
    client.publish(topic, payload=payload, qos=0, retain=retain)


def read_gpio_numeric(line_name: str) -> tuple[int, bool]:
    """
    Returns (value, ok).
    ok=False means gpioget failed.
    """
    try:
        out = subprocess.check_output(
            ["gpioget", "--numeric", line_name],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=1.0,
        ).strip()
        return (1 if out == "1" else 0, True)
    except Exception:
        return (0, False)


def main():
    client = mqtt.Client(MQTT_CLIENT_ID)
    client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    client.loop_start()

    stable_required_s = STABLE_MS / 1000.0

    # --- State machine ---
    raw, ok = read_gpio_numeric(GPIO_LINE_NAME)
    last_raw = raw
    raw_change_t0 = time.monotonic()

    stable_state = raw
    published_state = None

    consecutive_failures = 0
    sensor_ok = True

    last_hb_t = 0.0
    last_error_t = 0.0

    print(f"[sensor] start: line={GPIO_LINE_NAME}, poll={POLL_PERIOD_S}s, stable={STABLE_MS}ms")
    print(f"[sensor] mqtt: {BROKER_HOST}:{BROKER_PORT}")
    print(f"[sensor] topics: {TOPIC_PRESENT}, {TOPIC_HEARTBEAT}, {TOPIC_ERROR}")

    try:
        while True:
            now = time.monotonic()

            # --- Heartbeat ---
            if (now - last_hb_t) >= HEARTBEAT_S:
                epoch_s = str(int(time.time())).encode("ascii")
                mqtt_publish(client, TOPIC_HEARTBEAT, epoch_s, retain=True)
                last_hb_t = now

            # --- Read GPIO ---
            raw, ok = read_gpio_numeric(GPIO_LINE_NAME)

            if not ok:
                consecutive_failures += 1
            else:
                consecutive_failures = 0

            # --- Sensor health / fail-safe ---
            if consecutive_failures >= READ_FAIL_THRESHOLD:
                if sensor_ok:
                    sensor_ok = False

                # Rate-limit error messages
                if (now - last_error_t) >= ERROR_REPEAT_S:
                    msg = (
                        f"READ_FAIL threshold={READ_FAIL_THRESHOLD} "
                        f"consecutive_failures={consecutive_failures}"
                    ).encode("utf-8")
                    mqtt_publish(client, TOPIC_ERROR, msg, retain=True)
                    last_error_t = now

                # Fail-safe: force present=1 so gate won't close
                if published_state != 1:
                    mqtt_publish(client, TOPIC_PRESENT, b"1", retain=True)
                    published_state = 1
                    print("[sensor] FAIL-SAFE: present=1 (sensor read failing)")
                time.sleep(POLL_PERIOD_S)
                continue
            else:
                # If we recovered from an error state, clear it once
                if not sensor_ok:
                    sensor_ok = True
                    mqtt_publish(client, TOPIC_ERROR, b"OK", retain=True)
                    print("[sensor] recovered: sensor OK")

            # --- Debounce stable changes ---
            if raw != last_raw:
                last_raw = raw
                raw_change_t0 = now

            if (now - raw_change_t0) >= stable_required_s:
                if stable_state != raw:
                    stable_state = raw
                    if published_state != stable_state:
                        payload = b"1" if stable_state == 1 else b"0"
                        mqtt_publish(client, TOPIC_PRESENT, payload, retain=True)
                        published_state = stable_state
                        print(f"[sensor] present={stable_state}")

            time.sleep(POLL_PERIOD_S)

    except KeyboardInterrupt:
        print("\n[sensor] stopped.")
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
