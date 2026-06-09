ARG PYTHON_VERSION=3.11
FROM python:${PYTHON_VERSION}-slim-bookworm

WORKDIR /app

ARG ONNX_VARIANT=gpu
ARG APP_UID=1000
ARG APP_GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=600 \
    PYTHONPATH=/app

# Библиотеки для ONNX, matplotlib/reportlab и healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        curl \
        fontconfig \
        fonts-dejavu-core \
        libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-base.txt requirements-gpu.txt requirements-cpu.txt ./

RUN pip install --upgrade pip setuptools wheel \
    && if [ "$ONNX_VARIANT" = "gpu" ]; then \
        pip install --no-cache-dir -r requirements-gpu.txt; \
    else \
        pip install --no-cache-dir -r requirements-cpu.txt; \
    fi \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /root/.cache/pip

# CUDA wheels из pip (только GPU-сборка)
ENV LD_LIBRARY_PATH=/usr/local/lib/python3.11/site-packages/nvidia/cublas/lib:/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib:/usr/local/lib/python3.11/site-packages/nvidia/cuda_runtime/lib:/usr/local/lib/python3.11/site-packages/nvidia/curand/lib:/usr/local/lib/python3.11/site-packages/nvidia/cufft/lib:/usr/local/lib/python3.11/site-packages/nvidia/cusolver/lib:/usr/local/lib/python3.11/site-packages/nvidia/cusparse/lib:/usr/local/lib/python3.11/site-packages/nvidia/nvjitlink/lib

COPY app ./app
COPY pipeline ./pipeline
COPY src ./src
COPY schemas.py training_utils.py ./
COPY fast_rubert ./fast_rubert

RUN groupadd --gid "${APP_GID}" app \
    && useradd --uid "${APP_UID}" --gid app --create-home --shell /usr/sbin/nologin app \
    && mkdir -p data cache/jobs dataset \
    && chown -R app:app /app

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
