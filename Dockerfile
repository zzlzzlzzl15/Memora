FROM python:3.11-slim

WORKDIR /app

# Use Chinese mirrors for Debian to avoid proxy issues during build
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true; \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# Install system dependencies with retry
RUN apt-get update --fix-missing && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev curl \
    # MinerU 依赖
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-chi-sim \
    tesseract-ocr-chi-tra \
    libreoffice \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with Chinese mirrors
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads logs huggingface_cache

EXPOSE 8000

CMD ["python", "app/main.py"]
