import subprocess
import threading
from typing import Optional

from PIL import Image, ImageDraw

from .device import DeviceController
from .navigation import Navigator


MAP_REFRESH_INTERVAL_CLEANING = 10
MAP_REFRESH_INTERVAL_IDLE = 3600


class MapManager:
    """Capture and publish map screenshots plus status polling."""

    def __init__(
        self,
        device: DeviceController,
        navigator: Navigator,
        queue_task,
    ):
        self.device = device
        self.navigator = navigator
        self.queue_task = queue_task
        self.map_refresh_timer: Optional[threading.Timer] = None
        self.last_map_status = "Unknown"
        self.map_status_entity = None

    def set_status_entity(self, entity):
        self.map_status_entity = entity

    def map_screenshot(self):
        self.navigator.navigate_to("Robot")

        self.dismiss_warnings_and_log()
        self.center_map()

        img = self.device.screenshot()
        w, h = img.size
        img = img.resize((w // 2, h // 2), Image.LANCZOS)
        w, h = img.size
        img = img.crop((0, int(h * 0.09), w, int(h * 0.55))).convert("RGBA")
        ImageDraw.floodfill(img, xy=(0, -1), value=(255, 255, 255, 0), thresh=25)
        img.save("adb_ecovacs/Map_cropped.png")
        print("Map screenshot saved.")
        try:
            subprocess.run(
                ["scp", "adb_ecovacs/Map_cropped.png", "hassio:/root/config/www/"],
                check=True,
            )
            print("File successfully copied to Home Assistant.")
        except FileNotFoundError:
            print("Warning: scp binary not available; install OpenSSH client or skip map uploads.")
        except subprocess.CalledProcessError as exc:
            print("Error during SCP:", exc)
        self._update_map_status()

    def _update_map_status(self):
        self.device.refresh_tree()
        status_text = ""
        for grandchild in self.device.get_tree().findall(
                ".//node[@class='android.view.View'][@index='1']"
                "/node[@class='android.view.View'][@index='0']"
                "/node[@class='android.view.View'][@index='0']"
                "/node[@class='android.view.View'][@index='0']"
            ):
            status_text = ' '.join([tv.attrib.get("text", "") for tv in grandchild.findall("./node[@class='android.widget.TextView']") if tv.attrib.get("text")])
        text_elem = self.device.find_by_text("Clean water tank low on water or not installed")
        if text_elem is not None:
            status_text = text_elem.attrib.get("text", "")
        if not status_text.strip():
            status_text = self.device.get_robot_status_bar() or ""
        if not status_text:
            status_text = self.last_map_status or "Idle"
        status_text = status_text.strip()
        print("Status:", status_text)
        self.last_map_status = status_text
        if self.map_status_entity is not None:
            self.map_status_entity.publish_state(status_text)
            print(f"📤 MQTT map status -> {status_text}")
        else:
            print("⚠️ Map status entity not initialized; skipping MQTT publish")
        self.device.clear_tree()

    def map_refresh_task(self):
        """Run a map screenshot and schedule the next refresh."""
        self.map_screenshot()
        self.schedule_map_refresh()

    def schedule_map_refresh(self):
        """Schedule the next map screenshot based on the current robot status."""
        status = (self.last_map_status or "").strip().lower()
        interval = MAP_REFRESH_INTERVAL_CLEANING if status.startswith("clean") else MAP_REFRESH_INTERVAL_IDLE
        if self.map_refresh_timer is not None:
            self.map_refresh_timer.cancel()
        self.map_refresh_timer = threading.Timer(interval, lambda: self.queue_task(self.map_refresh_task))
        self.map_refresh_timer.daemon = True
        self.map_refresh_timer.start()
        print(f"🗓️ Next map refresh scheduled in {interval} seconds (status: {self.last_map_status})")

    def dismiss_warnings_and_log(self):
        cleaning_log = self.device.find_by_text("Cleaning completed. Tap to view the Log.")
        if cleaning_log is not None:
            bounds = cleaning_log.attrib["bounds"]
            x1, y1, x2, y2 = map(int, bounds.replace("[", "").replace("]", " ").replace(",", " ").split())
            x, y = x2 + 130, (y1 + y2) / 2
            self.device.device.click(x, y)
            self.device.clear_tree()
            print("Click to dismiss cleaning log at", x, y)

    def center_map(self):
        corridor = self.device.find_by_text("Corridor", contains=True)
        if corridor is not None:
            bounds = corridor.attrib["bounds"]
            x1, y1, x2, y2 = map(int, bounds.replace("[", "").replace("]", " ").replace(",", " ").split())
            x, y = (x1 + x2) / 2, (y1 + y2) / 2
            print("Corridor bounds:", bounds, x, y)
            if y < 630 or y > 640 or x < 360 or x > 400:
                self.device.double_click(0.5, 0.5, 0.001)
                self.device.drag(0.5, 0.5, 0.5, 0.38, 0.05)
