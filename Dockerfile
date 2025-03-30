FROM python:3.11-slim

# Installeer vereiste systeemafhankelijkheden en Chromium
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Stel de versie van ChromeDriver in en installeer deze
ENV CHROMEDRIVER_VERSION=114.0.5735.90
RUN wget -O /tmp/chromedriver.zip https://chromedriver.storage.googleapis.com/${CHROMEDRIVER_VERSION}/chromedriver_linux64.zip \
    && unzip /tmp/chromedriver.zip -d /usr/local/bin/ \
    && rm /tmp/chromedriver.zip \
    && chmod +x /usr/local/bin/chromedriver

# Zorg ervoor dat ChromeDriver in de PATH staat
ENV PATH="/usr/local/bin:${PATH}"

# Kopieer de requirements.txt en installeer de Python-dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Kopieer de rest van de applicatie en stel de werkdirectory in
COPY . /app
WORKDIR /app

# Start de applicatie via uvicorn op poort 10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
