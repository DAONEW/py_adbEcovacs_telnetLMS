FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        android-tools-adb \
        openssh-client && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uiautomator2 paho-mqtt

COPY . .
CMD ["python", "adb_ecovacs/ecovacs_app.py"]
