FROM python:3.12-slim

# ffmpeg — doira video yasash va videolarni birlashtirish uchun kerak.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORK_DIR=/tmp/instatube

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# YouTube himoyasi tez-tez o'zgaradi, shuning uchun har build'da yt-dlp'ning eng
# so'nggi (nightly) versiyasi o'rnatiladi. bgutil-ytdlp-pot-provider — PO Token
# plagini; tokenni alohida ishlaydigan POT serveridan oladi (POT_BASE_URL).
RUN pip install --no-cache-dir --upgrade --pre "yt-dlp[default]" \
    && pip install --no-cache-dir --upgrade bgutil-ytdlp-pot-provider

CMD ["python", "main.py"]
