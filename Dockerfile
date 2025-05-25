FROM python:3.11-slim

# …system deps installeren…

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install -r requirements.txt

COPY main.py .

# Kopieer nu de hele .well-known map
COPY .well-known ./.well-known

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
