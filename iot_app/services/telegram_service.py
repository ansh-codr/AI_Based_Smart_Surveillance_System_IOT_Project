import asyncio

from telegram import Bot


class TelegramService:
    def __init__(self, token, chat_id, logger):
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()
        self.logger = logger
        self.bot = Bot(token=self.token) if self.token and self.chat_id else None

    @property
    def available(self):
        return self.bot is not None

    def send_photo(self, caption, image_path):
        if self.bot is None:
            return False

        async def _send():
            with open(image_path, "rb") as image_file:
                await self.bot.send_photo(chat_id=self.chat_id, photo=image_file, caption=caption)

        try:
            asyncio.run(_send())
            return True
        except Exception as exc:
            if self.logger:
                self.logger.exception("Telegram send failed: %s", exc)
            return False
