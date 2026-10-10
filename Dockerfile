FROM python:3.13-slim-bookworm

WORKDIR /app

RUN groupadd --system verity \
    && useradd --system --gid verity --home-dir /app --shell /usr/sbin/nologin verity \
    && mkdir -p /data \
    && chown verity:verity /data

COPY requirements.txt run.py ./
COPY verity ./verity
COPY static ./static
COPY config ./config
COPY samples ./samples

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VERITY_HOST=0.0.0.0 \
    VERITY_PORT=8080 \
    VERITY_DB=/data/verity.sqlite3

USER verity

EXPOSE 8080
VOLUME ["/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.environ.get('VERITY_PORT','8080')+'/api/health', timeout=3)"

CMD ["python", "run.py"]
