import json
from pathlib import Path

d = json.load(open(Path(__file__).parent / "captures" / "006_totoGameData.do", encoding="utf-8"))
vs = d["voteStatus"]
h = vs["homeVoteStatusList"]
print("homeVoteStatusList len:", len(h))
print("each awayVoteStatusList len:", [len(x["awayVoteStatusList"]) for x in h][:20])
for i in range(min(3, len(h))):
    counts = [a["voteCount"] for a in h[i]["awayVoteStatusList"]]
    m = d["schedulesList"][i]
    total = sum(counts)
    pct = [round(c / total * 100, 1) for c in counts] if total else counts
    print(f"M{i+1:02d} {m['homeName']} vs {m['awayName']}: votes={counts} pct={pct}")
