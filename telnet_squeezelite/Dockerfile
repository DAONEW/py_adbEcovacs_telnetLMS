FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

RUN pip install --no-cache-dir telnetlib3 paho-mqtt

COPY . .
RUN mkdir -p logs
CMD ["python", "telnet_squeezelite/telnet_squeezelite.py"]
