# BASIS: een lichte Python image
FROM python:3.11-slim

# INSTALLATIE: systeemtools die nodig zijn
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    curl \
    gnupg \
    ca-certificates \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# INSTALLEER DE CHROMEDRIVER
ENV CHROMEDRIVER_VERSION=114.0.5735.90
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && chmod +x /usr/local/bin/chromedriver \
    && rm /tmp/chromedriver.zip

# PATH instellen zodat chromedriver vindbaar is
ENV PATH="/usr/local/bin:${PATH}"

# PYTHON: vereisten installeren
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# COPY: de rest van de applicatie
COPY . /app
WORKDIR /app

# START commando
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
