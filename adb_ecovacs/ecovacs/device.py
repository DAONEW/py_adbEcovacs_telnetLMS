import re
import xml.etree.ElementTree as ET
from typing import Optional


class DeviceController:
    """Wrapper around the uiautomator device with cached XML access."""

    def __init__(self, device):
        self.device = device
        self._tree_cache: Optional[ET.Element] = None

    # --------------------------
    # Cached XML Helper
    # --------------------------
    def refresh_tree(self) -> ET.Element:
        """Dump UI hierarchy to disk and refresh the cached tree."""
        xml_str = self.device.dump_hierarchy()
        with open("adb_ecovacs/ui_dump.xml", "w", encoding="utf-8") as f:
            f.write(xml_str)
        self._tree_cache = ET.fromstring(xml_str)
        return self._tree_cache

    def get_tree(self) -> ET.Element:
        """Return the cached tree, refreshing if necessary."""
        if self._tree_cache is None:
            return self.refresh_tree()
        return self._tree_cache

    def clear_tree(self):
        """Invalidate the cached tree after an interaction."""
        self._tree_cache = None

    # --------------------------
    # XML Query Helpers
    # --------------------------
    def find_by_text(self, text: str, contains: bool = False):
        for elem in self.get_tree().iter("node"):
            t = elem.attrib.get("text", "")
            if (contains and text in t) or (not contains and t == text):
                return elem
        return None

    def find_by_desc(self, desc: str, contains: bool = False):
        for elem in self.get_tree().iter("node"):
            dsc = elem.attrib.get("content-desc", "")
            if (contains and desc in dsc) or (not contains and dsc == desc):
                return elem
        return None

    # --------------------------
    # Interaction helpers
    # --------------------------
    def click_elem(self, elem):
        """Click element using bounds and invalidate tree cache."""
        if elem is None:
            return False
        bounds = elem.attrib["bounds"]  # e.g., "[0,1443][1080,1600]"
        numbers = list(map(int, re.findall(r"\d+", bounds)))
        if len(numbers) != 4:
            print("Warning: invalid bounds:", bounds)
            return False
        x1, y1, x2, y2 = numbers
        x = (x1 + x2) / 2
        y = (y1 + y2) / 2
        self.device.click(x, y)
        self.clear_tree()
        return True

    def swipe(self, *args, **kwargs):
        self.device.swipe(*args, **kwargs)
        self.clear_tree()

    def drag(self, *args, **kwargs):
        self.device.drag(*args, **kwargs)
        self.clear_tree()

    def press(self, *args, **kwargs):
        self.device.press(*args, **kwargs)
        self.clear_tree()

    def screen_on(self):
        self.device.screen_on()
        self.clear_tree()

    def double_click(self, *args, **kwargs):
        self.device.double_click(*args, **kwargs)
        self.clear_tree()

    def screenshot(self):
        return self.device.screenshot()

    # --------------------------
    # UI-specific helpers
    # --------------------------
    def get_robot_status_bar(self):
        """
        Locate a structure of three nested android.view.View (index == 0) elements
        followed by a child android.widget.TextView with index 0. Returns the TextView node or None.
        """

        def _first_child(node, cls):
            for child in list(node):
                if child.attrib.get("class") == cls and child.attrib.get("index") == "0":
                    return child
            return None

        for elem in self.get_tree().iter("node"):
            if elem.attrib.get("class") != "android.view.View" or elem.attrib.get("index") != "0":
                continue
            level1 = _first_child(elem, "android.view.View")
            if level1 is None:
                continue
            level2 = _first_child(level1, "android.view.View")
            if level2 is None:
                continue
            target = _first_child(level2, "android.widget.TextView")
            if target is not None:
                return target.attrib.get("text", None)
        return None
