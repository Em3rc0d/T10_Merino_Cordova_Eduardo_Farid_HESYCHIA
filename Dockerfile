FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MPLBACKEND=Agg \
    HESYCHIA_OUTPUT_ROOT=/workspace/04_build/selective_audio_lab/outputs/web \
    URBANSOUND8K_ROOT=/data/UrbanSound8K

WORKDIR /workspace

RUN apt-get update \
    && apt-get install -y --no-install-recommends libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

COPY 04_build/selective_audio_lab/requirements-lock.txt /tmp/requirements-lock.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r /tmp/requirements-lock.txt

COPY 03_architecture ./03_architecture
COPY 04_build/selective_audio_lab ./04_build/selective_audio_lab

WORKDIR /workspace/04_build/selective_audio_lab
EXPOSE 8080

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=4 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=2).read()" || exit 1

CMD ["python", "src/web_server.py", "--host", "0.0.0.0", "--port", "8080"]