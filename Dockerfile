FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for compiling certain python packages (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ /app/app/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/
COPY tests/ /app/tests/

# Create directory for uploads
RUN mkdir -p /app/uploads

EXPOSE 8000

# Entry point will be configured via docker-compose commands for flexibility
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
