from time import sleep
import sys
from pathlib import Path

import uiautomator2 as ui
import paho.mqtt.client as mqtt

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from settings import (
    ANDROID_PASSWORD,
    DEVICE_NAME,
    HA_DISCOVERY_PREFIX,
    MQTT_BROKER,
    MQTT_PASSWORD,
    MQTT_PORT,
    MQTT_USER,
)
from ecovacs.command_queue import CommandQueue
from ecovacs.device import DeviceController
from ecovacs.map_utils import MapManager
from ecovacs.mqtt_entities import MqttContext, MqttEntity
from ecovacs.navigation import Navigator
from ecovacs.rooms import RoomManager

# Device / navigation setup
device = DeviceController(ui.connect_usb())
command_queue = CommandQueue()
navigator = Navigator(device, ANDROID_PASSWORD)

# MQTT context + helpers
mqtt_context = MqttContext()
room_manager = RoomManager(device, navigator, mqtt_context)
map_manager = MapManager(device, navigator, command_queue.queue_task)


# --------------------------
# Convenience wrappers (retain original function names)
# --------------------------
def queue_task(func, *args, **kwargs):
    command_queue.queue_task(func, *args, **kwargs)


def ClickPause():
    navigator.navigate_to("Robot")
    device.refresh_tree()
    device.click_elem(device.find_by_text("Pause"))


def ClickEnd():
    navigator.navigate_to("Robot")
    device.refresh_tree()
    device.click_elem(device.find_by_text("End"))


def ClickStart():
    navigator.navigate_to("Robot")
    device.refresh_tree()
    start = device.find_by_text("Start")
    if start is None:
        start = device.find_by_text("Continue")
    print("Start button:", start.attrib.get("text", "") if start is not None else "")
    device.click_elem(start)


def MapScreenshot():
    map_manager.map_screenshot()


def map_refresh_task():
    map_manager.map_refresh_task()


def schedule_map_refresh():
    map_manager.schedule_map_refresh()


def RefreshRoomState(entities=None):
    return room_manager.refresh_room_state(entities)


def enbl_room(room_name):
    room_manager.enable_room(room_name)


def get_room_enabled_state(room_name):
    return room_manager.get_room_enabled_state(room_name)


def wait_for_room_state(room_name, desired_state, retries=10, delay=0.5):
    return room_manager.wait_for_room_state(room_name, desired_state, retries, delay)


def ClickZone():
    navigator.navigate_to("Robot")
    device.refresh_tree()
    device.click_elem(device.find_by_text("Zone"))
    zone_elem = device.find_by_text("1.0m * 1.0m")
    if zone_elem is not None:
        children = list(zone_elem.iterfind("../*"))
        print(f"Found {len(children)} child elements")
    else:
        print('Object "1.0m * 1.0m" not found.')


def ClickNora():
    navigator.navigate_to("Scenario")
    device.click_elem(device.find_by_text("Nora"))


def ClickPostMeal():
    navigator.navigate_to("Scenario")
    device.clear_tree()
    device.click_elem(device.find_by_desc("Post-meal Clean"))


def ClickStopDryMop():
    navigator.navigate_to("Station")
    cancel = device.find_by_text("Cancel")
    if cancel is not None:
        bounds = cancel.attrib["bounds"]
        x1, y1, x2, y2 = map(int, bounds.replace("[", "").replace("]", " ").replace(",", " ").split())
        x, y = (x1 + x2) / 2, y1 - 100
        device.device.click(x, y)
        device.clear_tree()


# --------------------------
# MQTT wiring
# --------------------------
device_info = {
    "identifiers": [DEVICE_NAME.lower().replace(" ", "_")],
    "name": DEVICE_NAME,
    "manufacturer": "PythonMQTT",
    "model": "Robot Vacuum",
}

entities = []
map_status_entity = None

def mqtt_received(topic, payload):
    decoded_payload = payload.upper()
    print(f"📩 Received '{decoded_payload}' on {topic}")
    handled = False

    for entity in entities:
        if topic != entity.command_topic:
            continue

        handled = True
        if entity.entity_type == "switch":
            desired_state = decoded_payload == "ON"
            if entity.enabled != desired_state:
                print(f"⚙️ Switch {entity.android_name} toggled {decoded_payload} (was {entity.enabled})")
                enbl_room(entity.android_name)
                wait_for_room_state(entity.android_name, desired_state)
            else:
                print(f"ℹ️ {entity.android_name} already {decoded_payload}")
        elif entity.entity_type == "button":
            print(f"⚙️ Button press {entity.name}")
            handler = globals().get(entity.name)
            if callable(handler):
                handler()
            else:
                print(f"⚠️ No handler found for {entity.name}")

    if handled:
        RefreshRoomState(entities)
        MapScreenshot()
        print("🔄 Room state refreshed after command processing.")
    else:
        print(f"⚠️ No entity matched topic {topic}")


def on_message(client, userdata, msg):
    payload = msg.payload.decode()
    queue_task(mqtt_received, msg.topic, payload)


def on_connect(client, userdata, flags, rc, properties=None):
    print("Connected to MQTT broker with result code", rc)
    for entity in entities:
        if not entity.command_topic:
            continue
        client.subscribe(entity.command_topic)
        print(f"🔔 Subscribed to {entity.command_topic}")


def main():
    command_queue.start_worker()

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_message = on_message

    mqtt_context.client = client
    mqtt_context.device_info = device_info
    mqtt_context.ha_prefix = HA_DISCOVERY_PREFIX

    global entities, map_status_entity
    entities = RefreshRoomState()

    map_status_entity = MqttEntity(client, device_info, "Map Status", "sensor", HA_DISCOVERY_PREFIX)
    entities.append(map_status_entity)
    map_manager.set_status_entity(map_status_entity)

    for name in [n for n in globals() if n.startswith("Click")]:
        entities.append(MqttEntity(client, device_info, name, "button", HA_DISCOVERY_PREFIX))

    client.connect(MQTT_BROKER, MQTT_PORT, 60)

    for entity in entities:
        entity.publish_discovery()
        if entity.entity_type == "switch":
            entity.set_state(entity.enabled, force=True)

    print("🏠 All entities published via MQTT Discovery!")
    command_queue.queue_task(map_refresh_task)
    client.loop_forever()


if __name__ == "__main__":
    main()
