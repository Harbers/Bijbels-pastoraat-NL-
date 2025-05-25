# 1) Kies een lichte Python-basis
FROM python:3.10-slim

# 2) Werkmap instellen
WORKDIR /app

# 3) Copy requirements en installeer
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 4) Copy de rest van de app (main.py, openapi.yaml, .well-known/)
COPY . .

# 5) Exposeer poort 80 (Render gebruikt dit)
EXPOSE 80

# 6) Start de FastAPI-app via uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
