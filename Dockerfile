# Use standard Python 3.10 slim image
FROM python:3.10-slim

# Install system dependencies (ffmpeg is required by WhisperX)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    git \
    libsndfile1 \
    ca-certificates \
    nodejs \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Ensure temp directory exists and is fully writable
RUN mkdir -p /app/temp && chmod 777 /app/temp

# Set environment variables
ENV PORT=7860
ENV FRONTEND_DIR=/app/frontend

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Start FastAPI application
CMD ["python", "server.py"]
