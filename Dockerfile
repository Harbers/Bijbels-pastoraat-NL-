# Gebruik een lichte Python-basis
FROM python:3.10-slim

# Werkmap binnen container
WORKDIR /app

# Kopieer alle bestanden uit de context (incl. .well-known en openapi.yaml)
COPY . .

# Installeer vereisten
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Exposeer poort (Render gebruikt meestal 80)
EXPOSE 80

# Start de app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
