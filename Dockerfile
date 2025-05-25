FROM python:3.11-slim

# 1) systeem‐dependencies
RUN apt-get update && apt-get install -y \
      wget \
      unzip \
      chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Python‐dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 3) App‐code + OpenAPI‐spec + plugin‐config
COPY main.py openapi.yaml ./
# kopieer .well-known (ai-plugin.json e.d.)
COPY .well-known ./.well-known

# 4) Start de server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
