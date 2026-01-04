import json
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class MqttContext:
    client: Optional[object] = None
    device_info: Optional[dict] = None
    ha_prefix: Optional[str] = None


class MqttEntity:
    def __init__(
        self,
        client,
        device_info,
        android_name: str,
        entity_type: str,
        ha_prefix: str,
        enabled: bool = False,
    ):
        self.client = client
        self.device_info = device_info
        self.android_name = android_name
        self.safe_name = self._to_safe_name(android_name)
        self.name = self.android_name
        self.entity_type = entity_type.lower()
        self.unique_id = self.safe_name
        self.config_topic = f"{ha_prefix}/{self.entity_type}/{self.unique_id}/config"
        base_topic = f"{ha_prefix}/{self.unique_id}"
        self.state_topic = f"{base_topic}/state"
        if self.entity_type == "switch":
            self.command_topic = f"{base_topic}/set"
        elif self.entity_type == "button":
            self.command_topic = f"{base_topic}/press"
        else:
            self.command_topic = None
        self.enabled = bool(enabled)

    @staticmethod
    def _to_safe_name(name: str) -> str:
        cleaned = re.sub(r"[^\w]+", "_", name.strip().lower())
        return cleaned.strip("_")

    def publish_discovery(self):
        if self.client is None:
            return

        cfg = {
            "name": self.android_name,
            "unique_id": self.unique_id,
            "device": self.device_info,
        }
        if self.entity_type == "switch":
            cfg.update(
                {
                    "state_topic": self.state_topic,
                    "command_topic": self.command_topic,
                    "payload_on": "ON",
                    "payload_off": "OFF",
                }
            )
        elif self.entity_type == "button":
            cfg.update(
                {
                    "command_topic": self.command_topic,
                    "payload_press": "PRESS",
                }
            )
        elif self.entity_type == "sensor":
            cfg.update(
                {
                    "state_topic": self.state_topic,
                }
            )
        self.client.publish(self.config_topic, json.dumps(cfg), retain=True)
        print(f"✅ Published {self.entity_type} discovery for {self.name}")
        print(cfg)

    def set_state(self, state, force=False):
        if self.entity_type != "switch" or self.client is None:
            return

        if isinstance(state, bool):
            desired = state
            payload = "ON" if state else "OFF"
        else:
            payload = str(state).upper()
            desired = payload == "ON"

        if self.enabled == desired and not force:
            return

        self.enabled = desired
        self.publish_state(payload)
        print(f"💡 {self.name} state -> {payload}")

    def press(self):
        if self.entity_type != "button" or self.client is None:
            return
        self.client.publish(self.command_topic, "PRESS")
        print(f"⚡ {self.name} button pressed")

    def publish_state(self, payload, retain=True):
        if self.client is None:
            return
        self.client.publish(self.state_topic, str(payload), retain=retain)
