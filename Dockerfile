# Dockerfile
FROM python:3.11-slim

# 1) Installeer systeem-dependencies
RUN apt-get update && apt-get install -y \
      wget \
      unzip \
      chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Installeer Python-dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 3) Kopieer app-code, OpenAPI-spec én de .well-known map 
COPY main.py openapi.yaml ./.well-known/ ./

# 4) Start de FastAPI-server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
