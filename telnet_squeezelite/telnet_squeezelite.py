import asyncio
import re
import sys
import datetime
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import telnetlib3

from settings import TELNET_HOST, TELNET_PORT

LOG_DIR = Path(__file__).resolve().parent / "logs"
STATE_EVENTS_FILE = LOG_DIR / "events.log"
GENERAL_EVENTS_FILE = LOG_DIR / "events_full.log"
VERBOSE_EVENTS = False  # flip to True when you want the full telnet trace
OUTPUT_STATE_REGEX = re.compile(r"Output state is (-?\d+)", re.IGNORECASE)

LOG_DIR.mkdir(parents=True, exist_ok=True)

# reuse the root settings
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from telnet_squeezelite import telnet_mqtt as mqtt_service


class OutputStateTracker:
    def __init__(self):
        self.bt_active = False
        self.airplay_active = False
        self.last_state_label: Optional[str] = None
        self.last_method_label: Optional[str] = None
        self.last_value: Optional[int] = None

    @staticmethod
    def _lms_status_from_value(value: int) -> str:
        if value < 0:
            return "off"
        if value == 0:
            return "pause"
        return "play"

    def _current_method(self) -> str:
        if self.airplay_active:
            return "AirPlay"
        if self.bt_active:
            return "BT"
        return "LMS"

    def _format_state_label(self, status: str) -> str:
        return status

    def _publish_state_for_value(self, value: int) -> None:
        status = self._lms_status_from_value(value)
        label = self._format_state_label(status)
        if self.last_state_label == label:
            return

        self.last_state_label = label
        mqtt_service.publish_state_label(label, value)

    def _publish_method(self) -> None:
        method_label = self._current_method()
        if self.last_method_label == method_label:
            return

        self.last_method_label = method_label
        mqtt_service.publish_method_label(method_label)

    def _republish_state(self) -> None:
        if self.last_value is None:
            return
        self._publish_state_for_value(self.last_value)

    def handle_lms_state(self, value: int) -> None:
        self.last_value = value
        self._publish_state_for_value(value)
        self._publish_method()

    def handle_bluetooth_started(self) -> None:
        self.bt_active = True
        self.airplay_active = False
        self._publish_method()
        self._republish_state()

    def handle_bluetooth_stopped(self) -> None:
        self.bt_active = False
        self._publish_method()
        self._republish_state()

    def handle_airplay(self, connected: bool) -> None:
        self.airplay_active = connected
        if connected:
            self.bt_active = False
        self._publish_method()
        self._republish_state()


state_tracker = OutputStateTracker()


def log_mqtt_message(message: str) -> None:
    normalized = message.strip()
    if not normalized:
        return
    with open(STATE_EVENTS_FILE, "a") as f:
        f.write(normalized + "\n")


mqtt_service.set_event_logger(log_mqtt_message)


def log_event(event: str, line: str):
    if not VERBOSE_EVENTS:
        return
    ts = datetime.datetime.now().isoformat()
    with open(GENERAL_EVENTS_FILE, "a") as f:
        f.write(f"[{ts}] {event}: {line}\n")
    print(f"⚡ Event detected: {event} → {line}")


def try_log_lms_state(line: str) -> bool:
    match = OUTPUT_STATE_REGEX.search(line)
    if not match:
        return False

    try:
        value = int(match.group(1))
    except ValueError:
        return False

    status = OutputStateTracker._lms_status_from_value(value)
    log_event(f"LMS {status}", line)
    state_tracker.handle_lms_state(value)
    return True


def try_log_bluetooth(line: str) -> bool:
    lower = line.lower()
    if "bt sink" not in lower:
        return False

    if "started" in lower:
        log_event("Bluetooth ++ BT sink started", line)
        state_tracker.handle_bluetooth_started()
        return True

    if "stopped" in lower:
        log_event("Bluetooth -- BT sink stopped", line)
        state_tracker.handle_bluetooth_stopped()
        return True

    return False


def try_log_airplay(line: str) -> bool:
    lower = line.lower()
    if "rtsp_thread" not in lower:
        return False

    if "got rtsp connection" in lower:
        log_event("AIRPLAY ++ got RTSP connection", line)
        state_tracker.handle_airplay(True)
        return True

    if "rtsp close" in lower:
        log_event("AIRPLAY -- RTSP close", line)
        state_tracker.handle_airplay(False)
        return True

    return False


def try_log_filtered_event(line: str) -> None:
    if try_log_lms_state(line):
        return
    if try_log_bluetooth(line):
        return
    if try_log_airplay(line):
        return

async def shell(reader, writer):
    current_day = datetime.date.today()
    log_path = LOG_DIR / f"log-{current_day}.log"
    log_file = open(log_path, "a")
    try:
        while True:
            try:
                line = await asyncio.wait_for(reader.__anext__(), timeout=360)
            except asyncio.TimeoutError:
                log_event("disconnect", "No data received (timeout), assuming connection lost.")
                break
            except StopAsyncIteration:
                break
            line = line.strip()
            today = datetime.date.today()
            if today != current_day:
                log_file.close()
                current_day = today
                log_path = LOG_DIR / f"log-{current_day}.log"
                log_file = open(log_path, "a")
            log_file.write(line + "\n")
            log_file.flush()

            try_log_filtered_event(line)


    except asyncio.CancelledError:
        raise
    except Exception as disconnect_exc:
        log_event("disconnect", f"Lost connection: {disconnect_exc}")
    finally:
        log_file.close()
        writer.close()

async def main():
    mqtt_service.init_mqtt()
    try:
        while True:
            try:
                print(f"Connecting to {TELNET_HOST}:{TELNET_PORT} ...")
                reader, writer = await telnetlib3.open_connection(TELNET_HOST, TELNET_PORT, shell=shell)
                print("✔ Connected.")
                await writer.protocol.waiter_closed
            except Exception as e:
                print(f"⚠ Connection error: {e}, retrying in 1min...")
                await asyncio.sleep(60)
            except KeyboardInterrupt:
                print("Stopping logger...")
                break
    except KeyboardInterrupt:
        print("Stopping logger...")
    finally:
        if mqtt_service.mqtt_client is not None:
            mqtt_service.mqtt_client.loop_stop()
            mqtt_service.mqtt_client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
