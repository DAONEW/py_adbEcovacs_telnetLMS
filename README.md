# py_adbEcovacs_telnetLMS

Minimal MQTT helpers that keep Home Assistant aware of Ecovacs robots and Squeezelite players by wrapping their APIs inside containers. Both services expose Home Assistant discovery payloads, handle MQTT commands, and relay the state that hass can act on.

## Services

- **`adb_ecovacs`** – drives an Android device via `uiautomator2` to surface rooms, buttons, and the latest map metadata; publishes them as Home Assistant MQTT entities and executes HA-triggered navigation requests.
- **`telnet_squeezelite`** – monitors a Squeezelite Telnet stream for LMS/Bluetooth/AirPlay activity, logs the trace, and republishes the current method plus playback state through MQTT sensors for Home Assistant.

## Docker usage

1. Create a `.env` file in the repo root and populate MQTT credentials, Android credentials, and Telnet hosts so the services can connect to hass and your devices.
2. Build or pull the containers that include the required dependencies (see `adb_ecovacs/Dockerfile` and `telnet_squeezelite/Dockerfile` for the package lists that back each helper). Local installs can also reference `adb_ecovacs/requirements.txt` and `telnet_squeezelite/requirements.txt`.
3. Run both helpers together with Compose:

   ```bash
   docker compose pull
   docker compose up -d
   ```

   Keep the `.env` file alongside `docker-compose.yml`; Compose feeds it to both services so they publish discovery for Home Assistant.
4. If you need to rebuild or publish the images, run `./publish_images.sh` from the repo root.

## Tips for Home Assistant

- The MQTT discovery topics emitted by each helper let hass load the vacuum sensors/buttons and the LMS playback state automatically; you just need to enable MQTT integration with the same broker.
- If you want to drop the Ecovacs map images into Home Assistant, configure passwordless SSH access from inside the `adb_ecovacs` container to the destination defined by `MAP_UPLOAD_TARGET` so `scp` can push the latest floorplan without interactive prompts.

Keep the containers running on a host that has access to your MQTT broker, the Android device for Ecovacs, and the Telnet endpoint for Squeezelite. Regularly refresh `.env` secrets if your broker rotates credentials.
