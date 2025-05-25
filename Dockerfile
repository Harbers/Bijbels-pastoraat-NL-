FROM python:3.11-slim

RUN apt-get update && apt-get install -y wget unzip chromium && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY main.py openapi.yaml ai-plugin.json ./
# eventueel .well-known/logo.png kopiëren
COPY .well-known ./ ./.well-known/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
