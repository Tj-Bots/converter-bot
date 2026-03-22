# Use Python 3.13-slim for a small, efficient image
FROM python:3.13-slim

# Install system dependencies (ffmpeg is critical for this bot)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create downloads directory
RUN mkdir -p downloads

# Run the bot
CMD ["python", "main.py"]
