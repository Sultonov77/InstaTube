#!/bin/sh
# PO Token serverini ishga tushiradi, so'ng botni boshlaydi.
set -e

PORT="${POT_PORT:-4416}"

if [ -f /opt/bgutil/server/build/main.js ]; then
    echo "PO Token serveri ishga tushirilmoqda (port $PORT)..."
    node /opt/bgutil/server/build/main.js --port "$PORT" &

    # Server tayyor bo'lguncha kutamiz (eng ko'pi 30 soniya).
    i=0
    while [ "$i" -lt 30 ]; do
        if node -e "require('net').connect($PORT,'127.0.0.1').on('connect',()=>process.exit(0)).on('error',()=>process.exit(1))" 2>/dev/null; then
            echo "PO Token serveri tayyor."
            break
        fi
        i=$((i + 1))
        sleep 1
    done
    [ "$i" -lt 30 ] || echo "OGOHLANTIRISH: PO Token serveri javob bermadi, u holda ishlayveramiz."
else
    echo "OGOHLANTIRISH: PO Token serveri topilmadi."
fi

exec python main.py
