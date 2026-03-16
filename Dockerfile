# Use official Python runtime as a parent image
FROM python:3.11-slim

# Set environment variables to ensure stdout is not buffered and prevent python from writing .pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies required for psycopg2 and other packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
        gettext \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . /app/

# Expose port (can be overridden by docker-compose)
EXPOSE 8000

# Default command for development (overridden in production or docker-compose)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
