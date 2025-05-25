FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
      wget \
      unzip \
      chromium \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# kopieer alles wat in de build nodig is
COPY main.py openapi.yaml ./.well-known/ ./.well-known/
# let op: openapi.yaml ligt in root, en ai-plugin.json in .well-known

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
