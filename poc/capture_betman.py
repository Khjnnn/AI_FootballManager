"""배트맨 승무패(G011) 페이지 네트워크 캡처 PoC.

buyableGameList.do → gameSlip.do(G011) 순으로 열어 XHR/JSON 응답을 전부 기록한다.
개인 연구 목적의 1회성 저빈도 실행 (plan.md 4.4절 원칙 준수).

실행: python poc/capture_betman.py
산출: poc/captures/index.json + 응답 본문 파일들
"""
import json
import re
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "https://www.betman.co.kr"
LIST_URL = f"{BASE}/main/mainPage/gamebuy/buyableGameList.do"
CAPTURE_DIR = Path(__file__).parent / "captures"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")

captured = []


def safe_name(url: str, idx: int) -> str:
    tail = re.sub(r"[^A-Za-z0-9._-]", "_", url.split("/")[-1])[:80]
    return f"{idx:03d}_{tail}"


def make_handler(context_label: str):
    def on_response(response):
        try:
            url = response.url
            req = response.request
            ctype = response.headers.get("content-type", "")
            # 정적 리소스 제외, XHR/fetch 또는 JSON/.do 응답만 기록
            interesting = (
                req.resource_type in ("xhr", "fetch")
                or "json" in ctype
                or (".do" in url and req.resource_type == "document")
            )
            if not interesting:
                return
            idx = len(captured)
            body_file = None
            try:
                body = response.body()
                if body:
                    body_file = safe_name(url, idx)
                    (CAPTURE_DIR / body_file).write_bytes(body)
            except Exception:
                pass
            captured.append({
                "idx": idx,
                "phase": context_label,
                "url": url,
                "method": req.method,
                "status": response.status,
                "content_type": ctype,
                "resource_type": req.resource_type,
                "post_data": req.post_data,
                "body_file": body_file,
            })
        except Exception:
            pass
    return on_response


def main():
    CAPTURE_DIR.mkdir(exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="ko-KR",
                                  viewport={"width": 1440, "height": 900})
        page = ctx.new_page()

        # 1) 발매 게임 목록 페이지
        phase = "list"
        page.on("response", make_handler(phase))
        print(f"[1] open {LIST_URL}")
        page.goto(LIST_URL, wait_until="networkidle", timeout=60000)
        (CAPTURE_DIR / "list_page.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(CAPTURE_DIR / "list_page.png"), full_page=True)

        # 2) 페이지에서 G011(승무패) 회차 링크/gmTs 탐색
        html = page.content()
        gmts_candidates = sorted(set(re.findall(r"G011[^0-9]{0,40}?(\d{6})", html)))
        print(f"[2] G011 gmTs candidates in list page: {gmts_candidates}")

        # 3) 승무패 구매 슬립 페이지 (gmTs 후보가 있으면 그 값, 없으면 링크 클릭 시도)
        time.sleep(2)  # 요청 간 지연 (4.4절)
        if gmts_candidates:
            gmts = gmts_candidates[-1]
            slip_url = f"{BASE}/main/mainPage/gamebuy/gameSlip.do?gmId=G011&gmTs={gmts}"
            print(f"[3] open {slip_url}")
            page.goto(slip_url, wait_until="networkidle", timeout=60000)
        else:
            link = page.locator("a[href*='G011'], [onclick*='G011']").first
            if link.count():
                print("[3] click first G011 link")
                link.click()
                page.wait_for_load_state("networkidle", timeout=60000)
            else:
                print("[3] no G011 link found on list page")
        (CAPTURE_DIR / "slip_page.html").write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(CAPTURE_DIR / "slip_page.png"), full_page=True)

        browser.close()

    (CAPTURE_DIR / "index.json").write_text(
        json.dumps(captured, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"done: {len(captured)} responses captured -> {CAPTURE_DIR / 'index.json'}")


if __name__ == "__main__":
    main()
