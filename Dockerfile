FROM python:3.11-slim

# 1) Install systeem‐dependencies
RUN apt-get update && apt-get install -y \
      wget \
      unzip \
      chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2) Installeer Python‐requirements
COPY requirements.txt ./
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 3) Kopieer applicatie‐code + OpenAPI‐spec + plugin‐config
COPY main.py openapi.yaml ./.well-known/ai-plugin.json ./

# Als je nog andere .well-known‐bestanden hebt (bijv. icon, etc):
# COPY .well-known ./ ./.well-known/

# 4) Start de app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
