"""API-Football에서 K리그1/2·엘리테세리엔 2026시즌 팀 목록 조회 (요청 5회).

응답은 data/cache/에 저장해 재조회 없이 매핑 작업에 재사용한다.
"""
import json
from pathlib import Path

import httpx

ROOT = Path(__file__).parent.parent
CACHE = ROOT / "data" / "cache"
CACHE.mkdir(parents=True, exist_ok=True)

env = {}
for line in (ROOT / ".env").read_text().splitlines():
    if "=" in line and not line.startswith("#"):
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

H = {"x-apisports-key": env["API_FOOTBALL_KEY"]}
BASE = "https://v3.football.api-sports.io"

# 리그 ID 확인 (국가별 1회씩)
for country in ("South-Korea", "Norway"):
    r = httpx.get(f"{BASE}/leagues", headers=H,
                  params={"country": country, "season": 2026, "type": "league"},
                  timeout=30)
    data = r.json()
    (CACHE / f"leagues_{country}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    for item in data.get("response", []):
        lg = item["league"]
        print(f"{country}: id={lg['id']} {lg['name']}")

print()
# 팀 목록 (리그별 1회)
LEAGUES = {292: "kleague1", 293: "kleague2", 103: "eliteserien"}
for lid, name in LEAGUES.items():
    r = httpx.get(f"{BASE}/teams", headers=H,
                  params={"league": lid, "season": 2026}, timeout=30)
    data = r.json()
    (CACHE / f"teams_{name}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    teams = [(t["team"]["id"], t["team"]["name"]) for t in data.get("response", [])]
    print(f"[{name}] {len(teams)} teams:")
    for tid, tname in teams:
        print(f"  {tid}: {tname}")
