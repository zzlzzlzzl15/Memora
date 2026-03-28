FROM python:3.11-slim

WORKDIR /app

# Use Alibaba Cloud mirrors for apt (China server)
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ libffi-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies with Chinese mirrors
RUN pip install --no-cache-dir torch==2.1.2 --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p uploads logs huggingface_cache

EXPOSE 8000

CMD ["python", "start.py", "--host", "0.0.0.0", "--port", "8000"]
