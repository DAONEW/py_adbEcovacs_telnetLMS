import json
import sys
from pathlib import Path
from typing import Callable, Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import paho.mqtt.client as mqtt

from settings import HA_DISCOVERY_PREFIX, MQTT_BROKER, MQTT_PASSWORD, MQTT_PORT, MQTT_USER

SENSOR_NAME = "LMS Output"
SENSOR_UNIQUE = "lms_output"
STATE_TOPIC = f"{HA_DISCOVERY_PREFIX}/{SENSOR_UNIQUE}/state"
CONFIG_TOPIC = f"{HA_DISCOVERY_PREFIX}/sensor/{SENSOR_UNIQUE}/config"
METHOD_SENSOR_NAME = "LMS Output Method"
METHOD_SENSOR_UNIQUE = "lms_output_method"
METHOD_STATE_TOPIC = f"{HA_DISCOVERY_PREFIX}/{METHOD_SENSOR_UNIQUE}/state"
METHOD_CONFIG_TOPIC = f"{HA_DISCOVERY_PREFIX}/sensor/{METHOD_SENSOR_UNIQUE}/config"
DEVICE_INFO = {
    "identifiers": [SENSOR_UNIQUE],
    "name": SENSOR_NAME,
    "manufacturer": "TelnetSqueezelite",
    "model": "LMS output monitor",
}

mqtt_client: Optional[mqtt.Client] = None
EventLogger = Callable[[str], None]
event_logger: Optional[EventLogger] = None
STATE_ICON_MAP = {"play": "▶", "pause": "⏸", "off": "⏹"}
METHOD_ICON_MAP = {"LMS": "🎵", "BT": "🅱️", "AirPlay": "📡"}


def set_event_logger(logger: Optional[EventLogger]) -> None:
    global event_logger
    event_logger = logger


def publish_state_label(label: str, value: Optional[int] = None) -> None:
    if mqtt_client is None:
        print("⚠️ MQTT client not ready; skipping publish")
        return

    mqtt_client.publish(STATE_TOPIC, label, retain=True)
    state_base = label.split(" - ", 1)[0]
    icon = STATE_ICON_MAP.get(state_base, "")
    message = f"📡 {icon} state -> {label}"
    print(message)
    if event_logger:
        event_logger(message)


def publish_method_label(label: str) -> None:
    if mqtt_client is None:
        print("⚠️ MQTT client not ready; skipping publish")
        return

    mqtt_client.publish(METHOD_STATE_TOPIC, label, retain=True)
    icon = METHOD_ICON_MAP.get(label, "🎧")
    message = f"{icon} method -> {label}"
    print(message)
    if event_logger:
        event_logger(message)


def publish_discovery():
    if mqtt_client is None:
        return

    cfg = {
        "name": SENSOR_NAME,
        "unique_id": SENSOR_UNIQUE,
        "device": DEVICE_INFO,
        "state_topic": STATE_TOPIC,
    }
    mqtt_client.publish(CONFIG_TOPIC, json.dumps(cfg), retain=True)
    method_cfg = {
        "name": METHOD_SENSOR_NAME,
        "unique_id": METHOD_SENSOR_UNIQUE,
        "device": DEVICE_INFO,
        "state_topic": METHOD_STATE_TOPIC,
    }
    mqtt_client.publish(METHOD_CONFIG_TOPIC, json.dumps(method_cfg), retain=True)
    print(f"✅ Published MQTT discovery for {SENSOR_NAME} and {METHOD_SENSOR_NAME}")


def init_mqtt():
    global mqtt_client

    if mqtt_client is not None:
        return

    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        mqtt_client = client
    except Exception as exc:
        print(f"⚠️ MQTT connection failed: {exc}")
        return

    publish_discovery()
