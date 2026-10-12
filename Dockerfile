# Deno: yt-dlp'nin YouTube şifre çözme (n-challenge / EJS) işlemleri için gerekli JavaScript çalıştırıcısı
FROM denoland/deno:bin AS deno-bin

FROM python:3.11-slim

# Terminal çıktılarını gecikmesiz almak için
ENV PYTHONUNBUFFERED=1

# FFmpeg ve Opus ses kütüphanelerini yükle
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libopus-dev \
    gcc \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Deno çalıştırıcısını kopyala (yt-dlp otomatik olarak algılar)
COPY --from=deno-bin /deno /usr/local/bin/deno

WORKDIR /app

# Paketleri yükle (yt-dlp her derlemede en güncel sürüme yükseltilir)
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir --upgrade -r requirements.txt \
    && deno --version \
    && python -m yt_dlp --version

# Proje dosyalarını kopyala
COPY . .

# Botu başlat
CMD ["python", "main.py"]
