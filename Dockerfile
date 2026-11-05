FROM python:3.11-slim

# Install system dependencies required for OpenCV, Resvg and fast math
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libgomp1 \
    libfontconfig1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Cache requirements installation
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Production optimizations
ENV PYTHONUNBUFFERED=1
ENV RELOAD=0
ENV PORT=7860
EXPOSE 7860

CMD ["python", "run.py"]
