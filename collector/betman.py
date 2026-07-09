"""배트맨 수집 클라이언트.

방식 A(httpx 직접 호출)를 기본으로 하고, 스키마 검증 실패·요청 실패 시
방식 B(Playwright 렌더링)로 자동 폴백한다 (plan.md 4.1절).
엔드포인트 상세: docs/poc-betman.md
"""
import json
import logging
import time

import httpx

from .models import Round
from .parse import extract_g011_gmts, parse_round

log = logging.getLogger(__name__)

BASE = "https://www.betman.co.kr"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Content-Type": "application/json",
    "Referer": f"{BASE}/main/mainPage/gamebuy/buyableGameList.do",
    "X-Requested-With": "XMLHttpRequest",
}
SBM = {"_sbmInfo": {"_sbmInfo": {"debugMode": "false"}}}
REQUEST_DELAY_SEC = 3  # 요청 간 지연 (4.4절)


class BetmanClient:
    def __init__(self, delay: float = REQUEST_DELAY_SEC):
        self.delay = delay
        self._last_request = 0.0

    def _throttle(self):
        wait = self._last_request + self.delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.monotonic()

    def _post(self, path: str, body: dict) -> dict:
        self._throttle()
        with httpx.Client(headers=HEADERS, timeout=30) as client:
            r = client.post(f"{BASE}{path}", json=body)
            r.raise_for_status()
            return r.json()

    def detect_g011_gmts(self) -> int | None:
        """발매 중인 승무패 회차의 gmTs를 반환 (없으면 None)."""
        raw = self._post("/buyPsblGame/inqBuyAbleGameInfoList.do", SBM)
        return extract_g011_gmts(raw)

    def fetch_round(self, gmts: int) -> Round:
        """회차 상세(14경기 + 투표 분포)를 수집·검증해 Round로 반환.

        방식 A 실패 시 폴백 엔드포인트 → Playwright 순으로 시도한다.
        """
        for path in ("/buyPsblGame/totoGameData.do", "/buyPsblGame/gameInfoInq.do"):
            try:
                raw = self._post(path, dict(SBM, gmId="G011", gmTs=gmts))
                return parse_round(raw)
            except (httpx.HTTPError, json.JSONDecodeError, KeyError, ValueError) as e:
                log.warning("방식 A 실패 (%s): %s", path, e)
        log.warning("방식 A 전부 실패 → Playwright 폴백")
        return self._fetch_round_via_browser(gmts)

    def _fetch_round_via_browser(self, gmts: int) -> Round:
        """방식 B: 실제 브라우저로 페이지를 열고 totoGameData 응답을 가로챈다."""
        from playwright.sync_api import sync_playwright

        captured: dict = {}
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_context(user_agent=UA, locale="ko-KR").new_page()

            def on_response(resp):
                if "totoGameData.do" in resp.url or "gameInfoInq.do" in resp.url:
                    try:
                        captured.update(resp.json())
                    except Exception:
                        pass

            page.on("response", on_response)
            page.goto(f"{BASE}/main/mainPage/gamebuy/gameSlip.do?gmId=G011&gmTs={gmts}",
                      wait_until="networkidle", timeout=60000)
            browser.close()
        if not captured:
            raise RuntimeError(f"Playwright 폴백도 실패: gmTs={gmts}")
        return parse_round(captured)
