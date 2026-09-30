FROM python:3.12-slim
# Chrome libs for kaleido only (starting list, may need iterating)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 libatk-bridge2.0-0 libcups2 libxkbcommon0 libgbm1 libasound2 \
    libxcomposite1 libxdamage1 libxrandr2 libpango-1.0-0 fonts-liberation \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY . .
RUN pip install --upgrade pip \
 && pip install -r requirements/requirements-py312-linux64.txt \
 && pip install ".[web]" \
 && pip install -U "Django==6.0.3" --upgrade-strategy eager
RUN python -c "import kaleido; kaleido.get_chrome_sync()"
ENV DJANGO_SETTINGS_MODULE=egsim.settings.prod \
    EGSIM_DB_DEFAULT_NAME=/data/db.sqlite3 \
    EGSIM_MEDIA_ROOT=/data/media \
    EGSIM_STATIC_ROOT=/static
RUN useradd -m -u 1000 egsim && mkdir /data /static && chown egsim /data /static
USER egsim
EXPOSE 8001
CMD python -m django collectstatic --noinput && exec gunicorn \
    --workers=3 --max-requests=20 --max-requests-jitter=10 \
    --timeout=180 --graceful-timeout=30 \
    --log-file=/logs/gunicorn.log --bind=0.0.0.0:8001 \
    egsim.wsgi:application