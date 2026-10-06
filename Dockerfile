FROM python:3.11-slim

# Terminal çıktılarını gecikmesiz almak için
ENV PYTHONUNBUFFERED=1

# FFmpeg ve Opus ses kütüphanelerini yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libopus-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Paketleri yükle
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Proje dosyalarını kopyala
COPY . .

# Botu başlat
CMD ["python", "main.py"]
