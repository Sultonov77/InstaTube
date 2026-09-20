"""Kirish nuqtasi: `python main.py`."""
import asyncio
import contextlib

from app.bot import main

if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt, SystemExit):
        asyncio.run(main())
