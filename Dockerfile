# 精簡映像；會簽 PDF 需 LibreOffice headless 轉換 assets/signoff/signoff_template.docx
FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libreoffice-writer-nogui \
    fonts-wqy-zenhei \
    fonts-arphic-uming \
    fonts-arphic-ukai \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
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
