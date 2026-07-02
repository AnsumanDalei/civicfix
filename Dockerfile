FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# collectstatic only touches static files, not the DB, so a throwaway
# SECRET_KEY at build time is safe and lets real failures surface instead
# of being swallowed.
RUN DJANGO_SECRET_KEY=build-time-only-not-used-at-runtime \
    DJANGO_DEBUG=1 \
    python manage.py collectstatic --noinput

EXPOSE 8000

CMD ["gunicorn", "civicfix.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
