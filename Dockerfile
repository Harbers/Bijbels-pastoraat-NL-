# 1. Basis­image
FROM python:3.10-slim

# 2. Werk­directory instellen
WORKDIR /app

# 3. Eerst alleen requirements kopiëren en installeren
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# 4. De rest van de code toevoegen
COPY . .

# 5. Poort open­stellen en app starten
EXPOSE 80
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
