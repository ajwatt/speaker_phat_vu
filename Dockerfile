FROM alpine:3.22
RUN apk add --no-cache python3 pulseaudio-utils
COPY meter.py /opt/meter.py
ENV PYTHONUNBUFFERED=1
CMD ["python3", "/opt/meter.py"]
