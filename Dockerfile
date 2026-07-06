# Clean Label Agent - Production Deployment Dockerfile
# Owner: YOU (Lead)

# Use official Python lightweight image
FROM python:3.11-slim

# Set environment variables to optimize Python runtime in containers
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire workspace into the container
COPY . .

# Expose target port for container traffic
EXPOSE 8080

# Default command to spin up the ADK Agent Service via standard playground runner
CMD ["python", "-m", "google.adk.runners.playground"]
