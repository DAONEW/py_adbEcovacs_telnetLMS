import re
from time import sleep
from typing import List, Optional

from .device import DeviceController
from .navigation import Navigator
from .mqtt_entities import MqttEntity, MqttContext


class RoomManager:
    """Handle room parsing and MQTT state sync."""

    def __init__(self, device: DeviceController, navigator: Navigator, mqtt_context: MqttContext):
        self.device = device
        self.navigator = navigator
        self.mqtt_context = mqtt_context

    @staticmethod
    def _clean_room_text(raw_text: str) -> str:
        """Strip icon glyphs and whitespace from the front of a room label."""
        if not raw_text:
            return ""
        return re.sub(r"^[^A-Za-z0-9]+\s*", "", raw_text).strip()

    def _normalize_room_name(self, name: str) -> str:
        cleaned = self._clean_room_text(name).replace("_", " ")
        return re.sub(r"\s+", " ", cleaned).strip().lower()

    def _is_room_selected(self, btn, parent_map) -> bool:
        """Detect selection badge/flags near a room button."""

        def _index_selected(node):
            try:
                return int(node.attrib.get("index", "0")) > 0
            except ValueError:
                return False

        def _flag_selected(node):
            return node.attrib.get("selected") == "true" or node.attrib.get("checked") == "true"

        def _has_number_badge(node):
            for sibling in list(node):
                if sibling is btn:
                    continue
                if sibling.attrib.get("class") == "android.widget.TextView":
                    txt = (sibling.attrib.get("text", "") or "").strip()
                    if txt.isdigit():
                        return True
            return False

        parent = parent_map.get(btn)
        if parent is not None:
            if _flag_selected(parent) or _has_number_badge(parent):
                return True
        return _index_selected(btn) or _flag_selected(btn)

    def _get_room_buttons_with_state(self, tree):
        """Return tuples of (android_name, enabled, button_node)."""
        parent = tree.find(".//*[@resource-id='3d-map-out-div-9527']")
        if parent is None:
            return []

        parent_map = {child: parent for parent in parent.iter() for child in parent}
        rooms = []
        for btn in parent.findall(".//*[@class='android.widget.Button']"):
            raw_text = btn.get("text", "") or ""
            android_name = self._clean_room_text(raw_text)
            if not android_name:
                continue
            enabled = self._is_room_selected(btn, parent_map)
            rooms.append((android_name, enabled, btn))
        return rooms

    def _log_room_debug(self, room_name, tree):
        """Print debug info for a given room if present in the tree."""
        normalized = self._normalize_room_name(room_name)
        parent = tree.find(".//*[@resource-id='3d-map-out-div-9527']")
        if parent is None:
            print("🛑 No map parent found while debugging room state.")
            return
        parent_map = {child: parent for parent in parent.iter() for child in parent}
        for android_name, _, btn in self._get_room_buttons_with_state(tree):
            if self._normalize_room_name(android_name) != normalized:
                continue
            ancestor = parent_map.get(btn)
            print(
                f"🧭 Debug room '{android_name}': btn(index={btn.attrib.get('index')}, "
                f"selected={btn.attrib.get('selected')}, checked={btn.attrib.get('checked')}, "
                f"bounds={btn.attrib.get('bounds')}), "
                f"parent(index={ancestor.attrib.get('index') if ancestor is not None else None}, "
                f"selected={ancestor.attrib.get('selected') if ancestor is not None else None}, "
                f"checked={ancestor.attrib.get('checked') if ancestor is not None else None})"
            )
            return
        print(f"🛑 Room '{room_name}' not found in debug scan.")

    def refresh_room_state(self, entities: Optional[List[MqttEntity]] = None):
        self.navigator.navigate_to("Robot")
        self.device.refresh_tree()

        button_states = self._get_room_buttons_with_state(self.device.get_tree())
        if not button_states:
            print("⚠️ No map found for RefreshRoomState()")
            return [] if entities is None else entities

        ctx_client = self.mqtt_context.client
        ctx_device = self.mqtt_context.device_info
        ctx_prefix = self.mqtt_context.ha_prefix
        if None in (ctx_client, ctx_device, ctx_prefix):
            raise RuntimeError("MQTT entity context is not initialized; call set_mqtt_entity_context first.")

        if entities is None:
            return [MqttEntity(ctx_client, ctx_device, name, "switch", ctx_prefix, enabled) for name, enabled, _ in button_states]

        existing = {e.android_name: e for e in entities if e.entity_type == "switch"}
        for name, enabled, _ in button_states:
            entity = existing.get(name)
            if entity is None:
                new_entity = MqttEntity(ctx_client, ctx_device, name, "switch", ctx_prefix, enabled)
                entities.append(new_entity)
                new_entity.publish_discovery()
                new_entity.set_state(enabled, force=True)
                print(f"➕ Added new room entity for {name}")
                continue
            if entity.enabled != enabled:
                entity.set_state(enabled)
            else:
                entity.enabled = enabled
        return entities

    def enable_room(self, room_name):
        self.navigator.navigate_to("Robot")
        self.device.refresh_tree()
        tree = self.device.get_tree()
        target = None
        normalized = self._normalize_room_name(room_name)
        rooms = self._get_room_buttons_with_state(tree)
        print(f"🔎 enbl_room searching for '{room_name}' (normalized '{normalized}'). Rooms visible: {[n for n, _, _ in rooms]}")
        for android_name, enabled, btn in rooms:
            if self._normalize_room_name(android_name) == normalized:
                target = (android_name, enabled, btn)
                break
        if target is None:
            for android_name, enabled, btn in rooms:
                if normalized in self._normalize_room_name(android_name):
                    print(f"ℹ️ Using contains-match on '{android_name}'")
                    target = (android_name, enabled, btn)
                    break
        if target is None and "_" in room_name:
            fallback = room_name.replace("_", " ")
            target = self.device.find_by_text(fallback, contains=True)
        if target is None:
            print(f"⚠️ Room '{room_name}' not found on screen.")
            return
        if isinstance(target, tuple):
            android_name, enabled, btn = target
            print(f"➡️ Clicking room '{android_name}' (was enabled={enabled}, bounds={btn.attrib.get('bounds')})")
            self.device.click_elem(btn)
        else:
            print(f"➡️ Clicking fallback element for '{room_name}'")
            self.device.click_elem(target)
        print(f"🏠 Clicked on room: {room_name}")
        sleep(0.3)
        self.device.refresh_tree()
        post_state = self.get_room_enabled_state(room_name)
        print(f"🔁 Post-click state for '{room_name}': {post_state}")

    def get_room_enabled_state(self, room_name):
        """
        Read the current enabled state for a single room button from the UI.
        Returns True/False, or None if the room is not visible.
        """
        tree = self.device.get_tree()
        for android_name, enabled, _ in self._get_room_buttons_with_state(tree):
            if self._normalize_room_name(android_name) == self._normalize_room_name(room_name):
                return enabled
        return None

    def wait_for_room_state(self, room_name, desired_state, retries=3, delay=0.5):
        """
        Poll the UI until the room reflects the desired enabled state.
        Returns True on success, False on timeout.
        """
        for attempt in range(1, retries + 1):
            self.device.refresh_tree()
            state = self.get_room_enabled_state(room_name)
            if state is None:
                print(f"⏳ Room '{room_name}' not visible (attempt {attempt}/{retries})")
                self._log_room_debug(room_name, self.device.get_tree())
            elif state == desired_state:
                print(f"✅ Room '{room_name}' reached state {desired_state} after {attempt} attempt(s)")
                return True
            else:
                print(f"⏳ Room '{room_name}' state {state} != desired {desired_state} (attempt {attempt}/{retries})")
                self._log_room_debug(room_name, self.device.get_tree())
            sleep(delay)
        print(f"⚠️ Room '{room_name}' did not reach desired state {desired_state} after {retries} attempts")
        return False
