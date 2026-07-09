"""방식 A 검증: 브라우저 없이 httpx로 배트맨 엔드포인트 직접 호출.

세션 쿠키 필요 여부를 확인한다. 1회성 저빈도 실행 (4.4절 원칙).
"""
import json
import time

import httpx

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


def main():
    with httpx.Client(headers=HEADERS, timeout=30) as client:
        # 1) 회차 감지 (쿠키 없이 바로 POST)
        r1 = client.post(f"{BASE}/buyPsblGame/inqBuyAbleGameInfoList.do", json=SBM)
        print("inqBuyAbleGameInfoList:", r1.status_code, r1.headers.get("content-type"))
        toto = None
        try:
            data = r1.json()
            games = [g for g in data.get("totoGames", [])
                     if (g.get("gameMaster") or {}).get("gmId") == "G011"]
            if games:
                toto = games[0]
                print("  G011 gmTs:", toto.get("gmTs"))
        except json.JSONDecodeError:
            print("  JSON 아님 — 세션/차단 가능성. 본문 앞부분:", r1.text[:200])

        if not toto:
            print("결과: 쿠키 없이 감지 실패 → Playwright 폴백 필요 여부 재검토")
            return

        time.sleep(3)  # 요청 간 지연

        # 2) 회차 상세
        body = dict(SBM, gmId="G011", gmTs=toto["gmTs"])
        r2 = client.post(f"{BASE}/buyPsblGame/totoGameData.do", json=body)
        print("totoGameData:", r2.status_code, r2.headers.get("content-type"))
        try:
            d = r2.json()
            n = len(d.get("schedulesList") or [])
            print(f"  schedulesList: {n}경기, gmTs={d.get('gmTs')}")
            print("결과: 방식 A(httpx 직접 호출) 동작 확인" if n == 14
                  else "결과: 응답은 오나 경기 수 이상 — 확인 필요")
        except json.JSONDecodeError:
            print("  JSON 아님. 본문 앞부분:", r2.text[:200])


if __name__ == "__main__":
    main()
