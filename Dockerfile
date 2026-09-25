# 與 main（ossys.zeabur.app）相同的最小映像 — 避免 Zeabur registry ImagePull 逾時
# 會簽 PDF 在 Linux 以 ReportLab fallback（無 LibreOffice）
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py start.sh VERSION ./
COPY frontend/ frontend/
COPY assets/ assets/

RUN chmod +x start.sh

ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 8080

CMD ["./start.sh"]
