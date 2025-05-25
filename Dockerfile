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

# kopieer applicatie, OpenAPI en plugin-manifest + logo
COPY main.py openapi.yaml ./.well-known/ai-plugin.json ./.well-known/logo.png ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
