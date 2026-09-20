FROM python:3.12-slim

# ffmpeg — doira video yasash va videolarni birlashtirish uchun.
# nodejs  — YouTube PO Token provayderi uchun (pastga qarang).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg ca-certificates git nodejs npm \
    && rm -rf /var/lib/apt/lists/*

# YouTube server (datacenter) IP'laridan kelgan so'rovlarni "bot" deb bloklaydi.
# BgUtils PO Token provayderi shu blokni aylanib o'tish uchun token ishlab beradi.
ENV BGUTIL_VERSION=2.0.0
RUN git clone --single-branch --branch "$BGUTIL_VERSION" --depth 1 \
        https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /opt/bgutil \
    && cd /opt/bgutil/server \
    && npm ci \
    && npx tsc \
    && npm cache clean --force

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    WORK_DIR=/tmp/instatube \
    POT_PORT=4416

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# YouTube himoyasi tez-tez o'zgaradi, shuning uchun har build'da yt-dlp'ning eng
# so'nggi (nightly) versiyasi va PO Token plagini o'rnatiladi.
RUN pip install --no-cache-dir --upgrade --pre "yt-dlp[default]" \
    && pip install --no-cache-dir --upgrade bgutil-ytdlp-pot-provider

RUN chmod +x start.sh

CMD ["./start.sh"]
