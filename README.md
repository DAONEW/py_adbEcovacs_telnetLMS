# py_adbEcovacs_telnetLMS

This repo holds two focused Python helpers for automating and monitoring Ecovacs / Squeezelite devices via MQTT.

## Projects

- **`adb_ecovacs/` – MQTT bridge for Ecovacs robots**  
  Automates the Ecovacs app UI (via `uiautomator2`) to expose rooms, buttons, and map metadata through MQTT entities. It keeps an Android device connection, queues navigation commands, and republishes Home Assistant discovery payloads so the vacuum can be controlled remotely and the map state refreshed on demand. Convenience helpers such as `ClickStart`, `ClickZone`, and `RefreshRoomState` can be routed from MQTT buttons or used manually.

  **Setup & run**
  1. Install prerequisites: at least Python 3, `uiautomator2`, `paho-mqtt`, and any Android `adb` tooling.
  2. Pair with the vacuum over USB and ensure `adb`/`uiautomator2` can reach it.
  3. Copy `.env.example` to `.env` and update the MQTT credentials, discovery prefix, and Android passwords if needed; the helper pulls from that file at runtime.
  4. Start the bridge: `python -m adb_ecovacs.ecovacs_app` (or `python adb_ecovacs/ecovacs_app.py`).
  5. The script publishes HA discovery for sensors, buttons, and a map-status entity, and it handles MQTT commands by driving the app and then refreshing room/map state.

- **`telnet_squeezelite/` – Squeezelite output monitor over telnet**  
  Connects to a Squeezelite instance over Telnet, streams its logs, and detects LMS/Bluetooth/AirPlay state changes. It logs the raw trace, optionally prints verbose events, and republishes the status/method as MQTT sensors (via `telnet_squeezelite/telnet_mqtt.py`) so Home Assistant stays in sync with your player.

  **Setup & run**
  1. Install `telnetlib3` and `paho-mqtt`.
  2. Copy `.env.example` to `.env`, then tweak the Telnet host/port and MQTT credentials as necessary; the scripts load that file on startup.
  3. Execute: `python telnet_squeezelite/telnet_squeezelite.py`. Logs land in `telnet_squeezelite/logs/`, and state changes stream both to the console and MQTT discovery topics.
  4. Toggle `VERBOSE_EVENTS` to get the full telnet trace in `logs/events_full.log`.

## Configuration

Copy `.env.example` to `.env` at the repo root and edit the MQTT, device, and Telnet settings to match your environment. The helpers use `python-dotenv` (install it with `pip install python-dotenv`) to load those values, and `settings.py` enforces that the critical ports, hosts, and secrets are present (only `HA_DISCOVERY_PREFIX` keeps a safe default), so scripts fail fast if `.env` is missing or incomplete.

## Notes

- Both projects load their configuration from the environment variables defined in `.env` (see `.env.example`), and `settings.py` refuses to start unless the required ports, hosts, and secrets are present.
- `settings.py` still enforces integer ports, so invalid `.env` values fail fast rather than letting containers start with bad configuration.
- Use a virtual environment per project to keep dependencies clean, and refer to the Python files above when you need to extend the MQTT entities or add new automation helpers.
- Map screenshots are copied to `hassio:/root/config/www/` via `scp`. The `adb_ecovacs` container now includes `openssh-client` so uploads succeed by default, but you can still skip or replace that step if you prefer a different storage path.

## Publishing container images

1. Create a GitHub personal access token scoped for `write:packages` (and optionally `delete:packages`) and store it somewhere secure. Then log into GHCR before you build:

   ```bash
   echo "$GHCR_PAT" | docker login ghcr.io -u <github-username> --password-stdin
   ```

2. From the repo root, build and push each service with the matching Dockerfile:

   ```bash
   docker build -f telnet_squeezelite/Dockerfile -t ghcr.io/<OWNER>/telnet_squeezelite:latest .
   docker push ghcr.io/<OWNER>/telnet_squeezelite:latest

   docker build -f adb_ecovacs/Dockerfile -t ghcr.io/<OWNER>/adb_ecovacs:latest .
   docker push ghcr.io/<OWNER>/adb_ecovacs:latest
   ```

   Replace `<OWNER>` with your GitHub user or organization that owns the repository. Tag additional versions as needed (e.g., `:v1.2.0`) before pushing.

3. The `docker-compose.yml` now pulls the prebuilt images from GHCR, so deployments only need to run:

   ```bash
   docker compose pull
   docker compose up -d
   ```

   Keep the `.env` file next to the compose file; it still drives the runtime configuration for both services.

4. For a one-command publish, run `./publish_images.sh` from the repo root to build/push both images at once. The helper automatically loads `.env`, detects the GitHub owner from `origin`, and only requires `GHCR_OWNER` if that automatic inference needs to be overridden; optionally pass `GHCR_PAT`/`TAG` as well. The script auto-increments `.image_version`, tags the builds with that integer, retags them as `latest`, and pushes both tags; commit the version file if you want to track the release history. Set `TAG` manually only when you need to override the automatic counter.
