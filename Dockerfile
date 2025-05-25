# 1) basis
FROM python:3.11-slim

# 2) systeem-tools
RUN apt-get update && apt-get install -y \
      wget \
      unzip \
      chromium \
    && rm -rf /var/lib/apt/lists/*

# 3) werkdir
WORKDIR /app

# 4) Python-dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

# 5) copy alle code + OpenAPI + plugin-manifest
#    (.well-known bevat ai-plugin.json + eventueel icon/logo)
COPY . .

# 6) run de FastAPI app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
