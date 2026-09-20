# InstaTube

YouTube va Instagram'dan video yuklab beradigan hamda to'rtburchak videoni Telegram'ning
doira videosiga (video note) aylantiradigan Telegram bot.

## Imkoniyatlar

- 🔗 **YouTube** (oddiy video, Shorts) va **Instagram** (post, reel, IGTV) havolalaridan video yuklash
- 🔵 **Doira video**: istalgan to'rtburchak videoni markazidan kvadrat kesib, video note qilib yuborish
- 📢 **Majburiy obuna**: botdan foydalanish uchun belgilangan kanalga a'zolik tekshiriladi
- 🎛 Yuklangan videoning tagidagi tugma orqali darhol doira video yasash

## Sozlamalar (environment variables)

| O'zgaruvchi | Majburiy | Izoh |
|---|---|---|
| `BOT_TOKEN` | ha | @BotFather bergan token |
| `CHANNEL_ID` | yo'q | Majburiy obuna kanali, `@username` yoki `-100...` |
| `CHANNEL_TITLE` | yo'q | Tugmada ko'rinadigan kanal nomi |
| `CHANNEL_URL` | yo'q | Kanal havolasi (ko'rsatilmasa `CHANNEL_ID` dan yasaladi) |
| `MAX_FILE_MB` | yo'q | Yuboriladigan fayl chegarasi, sukut bo'yicha 48 |
| `NOTE_MAX_SECONDS` | yo'q | Doira video uzunligi chegarasi, sukut bo'yicha 60 |
| `NOTE_SIZE` | yo'q | Doira video o'lchami (piksel), sukut bo'yicha 480 |
| `INSTAGRAM_COOKIES` | yo'q | Yopiq postlar uchun Netscape formatdagi cookies |

> ⚠️ Obuna tekshiruvi ishlashi uchun bot **kanalga administrator** qilib qo'shilgan bo'lishi kerak.
> Aks holda bot tekshiruvni o'tkazib yuboradi (hamma foydalana oladi).

## Lokal ishga tushirish

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
copy .env.example .env         # va BOT_TOKEN ni to'ldiring
python main.py
```

`ffmpeg` va `ffprobe` tizimda o'rnatilgan bo'lishi shart (Docker image'da allaqachon bor).

## Railway'ga joylash

1. Railway'da yangi project → **Deploy from GitHub repo** → shu repo.
2. Service → **Settings → Build** da `Dockerfile Path` = `Dockerfile` qilib qo'ying
   (shunda ffmpeg o'rnatilgan image ishlatiladi).
3. **Variables** bo'limida `BOT_TOKEN` va `CHANNEL_ID` ni qo'shing.
4. Deploy tugagach loglarda `Bot ishga tushdi: @...` yozuvi chiqadi.

Bot web server emas, shuning uchun unga domen ham, PORT ham kerak emas.

## Cheklovlar

- Telegram botlari 20 MB dan katta faylni **yuklab ola olmaydi** (doira video uchun kiruvchi fayl).
- Telegram botlari 50 MB dan katta faylni **yubora olmaydi**.
- Doira video eng ko'pi 60 soniya bo'ladi — uzunroq video avtomatik qirqiladi.
- Yopiq (private) Instagram postlari cookies'siz yuklanmaydi.
