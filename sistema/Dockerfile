# Pacote do app para qualquer hospedagem com contêiner (Cloud Run, Render, Koyeb, VPS).
# As chaves entram pelas variáveis do servidor: SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY e COOKIE_SEGURO=1.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PORT=8000
WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home elita
USER elita

CMD ["sh", "-c", "exec python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
