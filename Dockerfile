FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Collect static files
RUN python manage.py collectstatic --noinput

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python manage.py check --deploy || exit 1

EXPOSE 8000

CMD ["daphne", "config.asgi:application", "--port", "8000", "--bind", "0.0.0.0"]
