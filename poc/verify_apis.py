"""3주차 착수: 두 부가 데이터 API 키 검증 (무과금/저비용 엔드포인트만).

- The Odds API /v4/sports : 크레딧 소모 없음. 커버 리그 확인.
- API-Football /status : 무과금. 플랜·잔여 쿼터 확인.
"""
import os
from pathlib import Path

import httpx

env = {}
for line in (Path(__file__).parent.parent / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

# 1) The Odds API — 축구 리그 커버리지
r = httpx.get("https://api.the-odds-api.com/v4/sports",
              params={"apiKey": env["ODDS_API_KEY"], "all": "true"}, timeout=30)
print("odds-api /sports:", r.status_code,
      "| remaining:", r.headers.get("x-requests-remaining"),
      "used:", r.headers.get("x-requests-used"))
if r.status_code == 200:
    soccer = [s for s in r.json() if s["group"] == "Soccer"]
    targets = [s for s in soccer
               if any(k in s["key"] for k in ("korea", "kleague", "norway"))]
    print(f"  soccer sports: {len(soccer)}, 관심 리그:")
    for s in targets:
        print(f"   - {s['key']} | {s['title']} | active={s['active']}")

# 2) API-Football — 플랜 상태
r2 = httpx.get("https://v3.football.api-sports.io/status",
               headers={"x-apisports-key": env["API_FOOTBALL_KEY"]}, timeout=30)
print("api-football /status:", r2.status_code)
if r2.status_code == 200:
    d = r2.json().get("response", {})
    req = d.get("requests", {})
    sub = d.get("subscription", {})
    print(f"  plan={sub.get('plan')}, active={sub.get('active')}, "
          f"today {req.get('current')}/{req.get('limit_day')}")
    if r2.json().get("errors"):
        print("  errors:", r2.json()["errors"])
