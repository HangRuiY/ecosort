# CPU 镜像（便于在没有 GPU 的机器上部署演示）。GPU 部署见 README。
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /srv/backend
COPY requirements.txt .
RUN pip install --no-cache-dir torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cpu \
 && grep -v tensorrt requirements.txt > req-docker.txt && pip install --no-cache-dir -r req-docker.txt
COPY app ./app
COPY scripts ./scripts
COPY assets ./assets
ENV ECOSORT_ROOT=/project ECOSORT_STORAGE=/data/storage ECOSORT_DEVICE=cpu ECOSORT_DEFAULT_BACKEND=onnx_fp32 \
    ECOSORT_BACKENDS=onnx_fp32,pytorch_fp32
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
