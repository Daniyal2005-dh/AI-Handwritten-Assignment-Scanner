# Hugging Face Space / generic Docker image for the AI Assignment Scanner.
# CPU-only build (HF free tier has no GPU); swap torch index for CUDA if needed.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    SCANNER_DEVICE=cpu

WORKDIR /app

# 1) torch first, from the CPU-only wheel index (the default Linux wheel
#    bundles the whole CUDA stack and bloats the image by ~8 GB).
COPY requirements.txt .
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir -r requirements.txt

# 2) application code (mock mode works fully offline; TrOCR weights are
#    fetched into the model cache on first request when enabled)
COPY backend ./backend
COPY frontend ./frontend

# HF Spaces routes traffic to this port.
EXPOSE 7860
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860"]
