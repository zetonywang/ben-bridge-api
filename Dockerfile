FROM python:3.9-slim

# Install system dependencies INCLUDING git-lfs for large model files
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    wget \
    unzip \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Initialize Git LFS
RUN git lfs install

WORKDIR /app

# Clone Ben repository WITH LFS (this downloads the model files!)
RUN git clone https://github.com/lorserker/ben.git /app/ben

# Verify the model file was downloaded
RUN ls -lh /app/ben/models/TF2models/ && \
    echo "Checking model file..." && \
    if [ -f "/app/ben/models/TF2models/GIB-BBO-8730_2025-04-19-E30.keras" ]; then \
        echo "✅ Model file found!"; \
    else \
        echo "❌ Model file NOT found - might need Git LFS"; \
        exit 1; \
    fi

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
CMD sh -c "uvicorn ben_api_cloud:app --host 0.0.0.0 --port ${PORT:-8000}"
