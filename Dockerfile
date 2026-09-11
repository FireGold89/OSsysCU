FROM python:3.11-slim-bookworm

WORKDIR /app

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
    fonts-noto-cjk \
    fonts-liberation \
    fonts-crosextra-carlito \
    fonts-crosextra-caladea \
    libreoffice-writer \
    libreoffice-java-common \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f

COPY docker/signoff-fonts.conf /etc/fonts/conf.d/99-signoff.conf

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x start.sh

ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

VOLUME ["/data"]

EXPOSE 8080

CMD ["./start.sh"]
