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

# Set up a new user named "user" with UID 1000 to comply with Hugging Face Spaces
RUN useradd -m -u 1000 user

# Set environment variables for HF and home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PORT=7860 \
    FRONTEND_DIR=/home/user/app/frontend \
    PYTHONUNBUFFERED=1

# Set up working directory inside user's home
WORKDIR $HOME/app

# Copy requirements file and install dependencies as root (to cache them globally)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application files and change ownership to the non-root user
COPY --chown=user . $HOME/app

# Ensure cache directories are writable by the user
RUN mkdir -p $HOME/.cache && chmod -R 777 $HOME/.cache

# Switch to the non-root user
USER user

# Expose the default Hugging Face Spaces port
EXPOSE 7860

# Start FastAPI application
CMD ["python", "server.py"]
