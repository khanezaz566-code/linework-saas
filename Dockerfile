FROM python:3.11-slim

# Install system dependencies required for OpenCV, Resvg and fast math
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    libfontconfig1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache requirements installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files and make data directory writable for non-root containers (e.g. Hugging Face Spaces 16GB Free Tier)
COPY . .
RUN mkdir -p /app/data && chmod -R 777 /app

# Production optimizations (Auto-scales worker threads/processes based on detected RAM)
ENV PYTHONUNBUFFERED=1
ENV RELOAD=0
ENV LINEWORK_INLINE=1
ENV LINEWORK_WORKERS=1
EXPOSE 7860 8000

CMD ["python", "run.py"]
