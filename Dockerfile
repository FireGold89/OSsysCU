FROM python:3.11-slim-bookworm

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    DATA_DIR=/data \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    SAL_USE_VCLPLUGIN=svp

# 精簡 apt：移除 Java / Noto CJK / Liberation（會簽用 AR PL + Carlito/Caladea；QS PDF 用 WQY）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    fontconfig \
    fonts-wqy-zenhei \
    fonts-arphic-uming \
    fonts-arphic-ukai \
    fonts-dejavu-core \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* \
    && fc-cache -f

COPY docker/signoff-fonts.conf /etc/fonts/conf.d/99-signoff.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py start.sh VERSION ./
COPY frontend/ frontend/
COPY assets/ assets/

RUN chmod +x start.sh

VOLUME ["/data"]

EXPOSE 8080

CMD ["./start.sh"]
