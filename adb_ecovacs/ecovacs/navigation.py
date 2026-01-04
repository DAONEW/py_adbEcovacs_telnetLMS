from collections import deque, defaultdict
from time import sleep
from typing import Callable, Dict, List, Optional, Tuple

from .device import DeviceController


class Navigator:
    """Page detection and navigation between app screens."""

    def __init__(self, device: DeviceController, password: str):
        self.device = device
        self.password = password
        self.page_detectors = self._build_page_detectors()
        self.nav_graph = self._build_nav_graph()

    # --------------------------
    # Page Detection
    # --------------------------
    def _build_page_detectors(self) -> Dict[str, Callable[[], bool]]:
        def in_robot():
            return self.device.find_by_text("Corridor", contains=True) is not None and self.device.find_by_text("Suction Power") is None and (
                self.device.find_by_text("Start") is not None
                or self.device.find_by_text("Pause") is not None
                or self.device.find_by_text("End") is not None
            )

        def in_robot_settings():
            return self.device.find_by_text("Corridor", contains=True) is not None and self.device.find_by_text("Suction Power") is not None and (
                self.device.find_by_text("Start") is not None
                or self.device.find_by_text("Pause") is not None
                or self.device.find_by_text("End") is not None
            )

        def in_station():
            return self.device.find_by_text("Corridor", contains=True) is not None and not in_robot() and not in_robot_settings()

        return {
            "ScreenOff": lambda: not self.device.device.info.get("screenOn"),
            "Lock": lambda: self.device.find_by_desc("Entsperren") is not None,
            "Desktop": lambda: self.device.find_by_desc("Nova-Suche") is not None,
            "Main": lambda: self.device.find_by_desc("Enter") is not None,
            "Scenario": lambda: self.device.find_by_text("Scenario Clean") is not None
            and self.device.find_by_text("Nora") is not None,
            "Robot": in_robot,
            "RobotSettings": in_robot_settings,
            "Station": in_station,
            "StationAdvanced": self._in_station_advanced,
            "Warning": lambda: self.device.find_by_text("Ignore") is not None
            and self.device.find_by_text("View") is not None,
        }

    def _in_station_advanced(self):
        for text in ["Mop Wash Settings", "Auto-Empty settings", "Hot Air Drying Settings"]:
            if self.device.find_by_text(text) is not None:
                return True
        return False

    def in_robot(self):
        return self.page_detectors["Robot"]()

    def in_robot_settings(self):
        return self.page_detectors["RobotSettings"]()

    # --------------------------
    # Navigation
    # --------------------------
    def _build_nav_graph(self) -> Dict[str, Dict[str, Callable[[], None]]]:
        graph = defaultdict(dict)

        graph["None"]["Desktop"] = self._none_to_desktop
        graph["ScreenOff"]["Lock"] = self._screen_off_to_lock
        graph["Lock"]["Desktop"] = self._lock_to_desktop
        graph["Desktop"]["Main"] = self._desktop_to_main
        graph["Main"]["Scenario"] = lambda: self.device.click_elem(self.device.find_by_desc("Scenario Clean"))
        graph["Scenario"]["Main"] = self._scenario_to_main
        graph["Main"]["Robot"] = lambda: self.device.click_elem(self.device.find_by_desc("Enter"))
        graph["RobotSettings"]["Desktop"] = self._robot_settings_to_desktop
        graph["Robot"]["Main"] = lambda: self.device.click_elem(self.device.find_by_text("Back"))
        graph["Station"]["Main"] = lambda: self.device.click_elem(self.device.find_by_text("Back"))
        graph["Robot"]["Station"] = lambda: self.device.click_elem(self.device.find_by_text("Station"))
        graph["Station"]["Robot"] = lambda: self.device.click_elem(
            self.device.find_by_text("ROBOT ", contains=True)
        )
        graph["Warning"]["None"] = lambda: self.device.click_elem(self.device.find_by_text("Ignore"))
        return graph

    def _none_to_desktop(self):
        self.device.press("home")

    def _screen_off_to_lock(self):
        self.device.screen_on()

    def _lock_to_desktop(self):
        self.device.swipe(0.5, 0.8, 0.5, 0.5, 0.1)
        for ch in self.password:
            self.device.click_elem(self.device.find_by_text(ch))

    def _desktop_to_main(self):
        self.device.click_elem(self.device.find_by_text("ECOVACS HOME", contains=True))

    def _robot_settings_to_desktop(self):
        self.device.press("back")

    def _scenario_to_main(self):
        self.device.device.click(0.5, 0.5)
        self.device.clear_tree()

    def detect_current_page(self) -> str:
        pages = self.page_detectors
        for _ in range(10):
            for name, func in pages.items():
                if func():
                    print("Current page:", name)
                    return name
            sleep(1)
            print("Retrying page detection...")
            self.device.refresh_tree()
        return "None"

    def find_path(self, start: str, goal: str) -> Optional[List[Tuple[str, str]]]:
        queue = deque([(start, [])])
        visited = set()
        while queue:
            current, path = queue.popleft()
            if current == goal:
                return path
            visited.add(current)
            for neighbor in self.nav_graph.get(current, {}):
                if neighbor not in visited:
                    queue.append((neighbor, path + [(current, neighbor)]))
        return None

    def navigate_to(self, target_page: str):
        for _ in range(10):
            current = self.detect_current_page()
            if current == target_page:
                print("already at ", target_page)
                return
            path = self.find_path(current, target_page)
            if not path:
                return
            for src, dst in path:
                print(f"Navigating {src} -> {dst}")
                self.nav_graph[src][dst]()
                if self.detect_current_page() == dst:
                    print(f"Arrived at {dst}")
                    break
                break
