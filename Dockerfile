FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies separately so Docker can cache this layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY core ./core

WORKDIR /app/core

# WhiteNoise serves the generated static files in production.
RUN python manage.py collectstatic --noinput

# Run the application as a non-root user.
RUN addgroup --system django \
    && adduser --system --ingroup django django \
    && chown -R django:django /app

USER django

EXPOSE 8080

# Hardcoded to port 8080 to match Railway Networking
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn core.asgi:application --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080 --workers ${WEB_CONCURRENCY:-2} --timeout ${GUNICORN_TIMEOUT:-120} --access-logfile - --error-logfile -"]

