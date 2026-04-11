FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Minimal system deps — Chrome/Selenium removed (replaced by Brave Search HTTP API)
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev gcc pkg-config curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
