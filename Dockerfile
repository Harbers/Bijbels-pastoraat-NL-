# … stap 1 & 2 onveranderd …
WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# zet main.py in /app
COPY main.py ./

# copy de hele .well-known map (inclusief openapi.yaml & ai-plugin.json)
COPY .well-known ./.well-known

CMD ["uvicorn","main:app","--host","0.0.0.0","--port","10000"]
