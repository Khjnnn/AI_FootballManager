"""The Odds API에서 K리그1·엘리테세리엔 1X2 배당 조회 (크레딧 2 소모).

응답을 data/cache/에 저장 — 팀명 매핑 확정과 수집기 픽스처로 재사용.
"""
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "data" / "cache"

env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

for sport in ("soccer_korea_kleague1", "soccer_norway_eliteserien"):
    r = httpx.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                  params={"apiKey": env["ODDS_API_KEY"], "regions": "eu",
                          "markets": "h2h", "oddsFormat": "decimal"},
                  timeout=30)
    print(sport, r.status_code, "| remaining:", r.headers.get("x-requests-remaining"))
    data = r.json()
    (CACHE / f"odds_{sport}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for ev in data:
        n_books = len(ev.get("bookmakers", []))
        print(f"  {ev['commence_time']} {ev['home_team']} vs {ev['away_team']} "
              f"(북메이커 {n_books})")
