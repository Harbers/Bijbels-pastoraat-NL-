WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# applicatiecode + manifest
COPY main.py openapi.yaml ./
COPY .well-known/ ./.well-known/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
