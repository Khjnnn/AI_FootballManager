"""회차 JSON → claude_Football 입력용 리스트 md 생성.

사용: python scripts/export_input_list.py 2026-40
출력: C:/Users/Pro/Documents/claude_Football/input/list_YYYYMMDD.md (오늘 날짜)
"""
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = Path(r"C:\Users\Pro\Documents\claude_Football\input")
KST = timezone(timedelta(hours=9))
WEEKDAY = "월화수목금토일"


def export(round_key: str) -> Path:
    from collector.models import Round

    r = Round.model_validate_json(
        (ROOT / "data" / "rounds" / f"{round_key}.json").read_text(encoding="utf-8"))
    lines = [
        "",
        "",
        "| 경기 | 일시 | 대진 (홈 vs 원정) | 승(%) | 무(%) | 패(%) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for m in r.matches:
        k = m.kickoff.astimezone(KST)
        when = f"{k.month:02d}.{k.day:02d} ({WEEKDAY[k.weekday()]}) {k:%H:%M}"
        v = m.vote_dist
        lines.append(
            f"| **{m.match_no}** | {when} | {m.home.betman_name} vs {m.away.betman_name} "
            f"| {v['win'] * 100:.1f}% | {v['draw'] * 100:.1f}% | {v['lose'] * 100:.1f}% |")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"list_{datetime.now(KST):%Y%m%d}.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    print(export(sys.argv[1]))
