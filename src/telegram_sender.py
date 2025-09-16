from dataclasses import dataclass
from typing import Optional
from logging_utils import setup_logger

logger = setup_logger("telegram")

@dataclass
class PostResult:
    ok: bool
    error: Optional[str] = None
    message_id: Optional[int] = None

def safe_post(bot_token: str, chat_id: str, text: str, parse_mode: str = "HTML", disable_web_page_preview: bool = False) -> PostResult:
    """
    Простой постер через HTTP API Telegram. Можно заменить на aiogram/pytelegrambotapi по желанию.
    """
    import requests
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": disable_web_page_preview
        }, timeout=20)
        if resp.status_code != 200:
            logger.error("TG API %s: %s", resp.status_code, resp.text)
            return PostResult(ok=False, error=f"HTTP {resp.status_code}: {resp.text}")
        data = resp.json()
        if not data.get("ok"):
            logger.error("TG error: %s", data)
            return PostResult(ok=False, error=str(data))
        msg_id = data["result"]["message_id"]
        logger.info("Отправлено в TG, message_id=%s", msg_id)
        return PostResult(ok=True, message_id=msg_id)
    except Exception as ex:
        logger.exception("Исключение TG постинга: %s", ex)
        return PostResult(ok=False, error=str(ex))
