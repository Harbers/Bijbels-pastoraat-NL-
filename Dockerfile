FROM python:3.11-slim

# 1) Installeer systeem‐dependencies
RUN apt-get update \
 && apt-get install -y wget unzip chromium \
 && rm -rf /var/lib/apt/lists/*

# 2) Zet de werkdirectory
WORKDIR /app

# 3) Installeer de Python‐requirements
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 4) Kopieer de app‐code en OpenAPI‐spec
COPY main.py openapi.yaml ./

# 5) Kopieer de hele .well-known map (inclusief ai-plugin.json en logo’s e.d.)
COPY .well-known ./ .well-known

# 6) Start de applicatie
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
