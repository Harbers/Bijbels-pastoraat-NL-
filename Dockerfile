FROM python:3.11-slim

# ---- 1) werkdirectory instellen
WORKDIR /app

# ---- 2) Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# ---- 3) app-code en plugin manifest
COPY main.py openapi.yaml ./
COPY .well-known ./.well-known

# (optioneel) expose de poort waarop Uvicorn draait
EXPOSE 10000

# ---- 4) start commando
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
