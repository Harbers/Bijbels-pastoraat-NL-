FROM python:3.10-slim

WORKDIR /app

# 1) Kopieer álle bestanden uit de context, inclusief .well-known
COPY . .

# 2) Installeer dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

EXPOSE 80

# 3) Start je FastAPI‐app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
