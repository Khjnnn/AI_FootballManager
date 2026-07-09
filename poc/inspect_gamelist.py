import json
from pathlib import Path

d = json.load(open(Path(__file__).parent / "captures" / "002_inqBuyAbleGameInfoList.do", encoding="utf-8"))
print("keys:", list(d.keys()))
toto = d.get("totoGames") or []
print("totoGames count:", len(toto))
for g in toto:
    if isinstance(g, dict):
        gm = g.get("gameMaster") or {}
        print(" -", gm.get("gmId") or g.get("gmId"), "|",
              (gm.get("gameNickName") or "?"), "| gmTs:", g.get("gmTs"),
              "| keys:", [k for k in g.keys() if "ts" in k.lower() or "date" in k.lower()][:8])
