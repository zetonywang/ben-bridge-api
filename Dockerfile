FROM python:3.9-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Clone Ben repository
RUN git clone https://github.com/lorserker/ben.git /app/ben

# Install Ben dependencies
WORKDIR /app/ben
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir colorama

# Install API dependencies
RUN pip install --no-cache-dir \
    fastapi==0.104.1 \
    uvicorn[standard]==0.24.0 \
    pydantic==2.5.0

# Copy API file
COPY ben_api_cloud.py /app/ben/ben_api_cloud.py

# Set working directory
WORKDIR /app/ben

# Expose port
EXPOSE 8000

# Start the API
CMD uvicorn ben_api_cloud:app --host 0.0.0.0 --port ${PORT:-8000}
