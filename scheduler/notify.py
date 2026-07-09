"""알림 스텁 (plan.md 5절·9절).

4주차에 텔레그램 봇으로 교체한다. 그때까지는 ERROR 로그로 경보를 남겨
서버 로그 감시로 확인 가능하게 한다.
"""
import logging

log = logging.getLogger("notify")


def notify(message: str):
    # TODO(4주차): .env의 TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID로 전송
    log.error("[알림] %s", message)
