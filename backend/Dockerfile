FROM python:3.11-slim

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/app/.cache/huggingface \
    EMBEDDING_MODEL=BAAI/bge-small-en-v1.5 \
    WHISPER_MODEL_SIZE=small

# Install minimal OS dependencies for audio processing, OCR, and healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    curl \
    tesseract-ocr \
    tesseract-ocr-fra \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Step 1: Install CPU-only PyTorch first to avoid multi-gigabyte CUDA bloat
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Step 2: Install application requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Step 3: Pre-download model weights during build for zero cold-start latency
RUN mkdir -p /app/.cache/huggingface && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-small-en-v1.5')" && \
    python -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8')"

# Copy application source code
COPY app /app/app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
