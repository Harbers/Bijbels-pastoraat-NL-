# Bijbels-Pastoraat-NL Backend

## Snel starten (Docker, Hetzner)

```bash
# 1) Build image
docker build -t bijbels-pastoraat:latest .

# 2) Run container (extern 8000 → container 80)
docker run -d --name bijbels-pastoraat \
  -p 8000:80 \
  --restart unless-stopped \
  bijbels-pastoraat:latest

## Lokaal ontwikkelen

Installeer afhankelijkheden en draai de tests:

```bash
pip install -r requirements.txt
pytest -q
```
