# 1) Basisimage
FROM python:3.10-slim

# 2) Zorg voor niet-root user (optioneel, voor extra veiligheid)
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser

# 3) Werkmap instellen
WORKDIR /app

# 4) Copy en install dependencies vóór de rest van de code  
#    (zodat bij code-wijzigingen alleen de laatste lagen opnieuw builden)
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# 5) Kopieer de app-code en statische mappen
COPY . .

# 6) Run als niet-root user
USER appuser

# 7) Expose poort voor Render
EXPOSE 80

# 8) Start de FastAPI-applicatie
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]
