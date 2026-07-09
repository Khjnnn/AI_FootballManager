"""정적 사이트 빌더 (plan.md 7.5절).

data/rounds/*.json → site/ 정적 HTML.
현재 ① 예정 단계 구현 (경기 리스트 + 투표 분포 바).
② 분석 리포트, ③ 결과 반영은 3~4주차에 확장.

디자인: design_teq.md 토큰·컴포넌트 규칙 준수.
실행: python -m site_builder.build
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path

from collector.models import Match, Round

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent
ROUNDS_DIR = ROOT / "data" / "rounds"
SITE_DIR = ROOT / "site"

CSS = """
:root {
  --bg:#FAF9F5; --surface:#F0EEE6; --surface-raised:#FFFFFF; --border:#E3DFD3;
  --text:#1F1E1D; --text-muted:#6E6C64; --accent:#D97757; --accent-soft:#F5E5DE;
  --kraft:#D4A27F; --olive:#6A6B5F; --positive:#5E7B5E; --negative:#B0554B;
}
* { margin:0; padding:0; box-sizing:border-box; }
body {
  background:var(--bg); color:var(--text);
  font-family:Pretendard,-apple-system,"Malgun Gothic",sans-serif;
  font-size:15px; line-height:1.7;
}
.wrap { max-width:960px; margin:0 auto; padding:48px 16px; }
.serif { font-family:"Noto Serif KR",Georgia,serif; font-weight:600; letter-spacing:-0.01em; }
.hero h1 { font-size:32px; }
.hero .meta { color:var(--text-muted); font-size:13px; margin-top:8px; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:16px; margin-top:32px; }
@media (max-width:900px){ .cards{ grid-template-columns:1fr; } }
.card {
  background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:16px 20px; box-shadow:0 1px 3px rgba(31,30,29,0.06);
  transition:background 120ms ease; display:block; color:inherit; text-decoration:none;
}
.card:hover { background:var(--surface-raised); }
.card .top { display:flex; justify-content:space-between; font-size:12px; color:var(--text-muted); }
.card .teams { font-size:19px; margin:8px 0 12px; }
.card .teams .vs { color:var(--text-muted); font-size:14px; margin:0 6px; }
.num { font-variant-numeric:tabular-nums; }
.bar { display:flex; height:22px; border-radius:6px; overflow:hidden; }
.bar span { display:flex; align-items:center; justify-content:center;
  color:#fff; font-size:11px; font-weight:600; min-width:0; }
.bar .w { background:var(--accent); } .bar .d { background:var(--kraft); } .bar .l { background:var(--olive); }
.legend { display:flex; gap:16px; font-size:12px; color:var(--text-muted); margin-top:24px; }
.legend i { display:inline-block; width:10px; height:10px; border-radius:3px; margin-right:5px; }
.pill { display:inline-block; border:1px solid var(--border); border-radius:999px;
  padding:2px 12px; font-size:12px; color:var(--text-muted); }
.pill.accent { background:var(--accent-soft); color:var(--accent); border-color:transparent; }
.notice { background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:16px 20px; margin-top:32px; color:var(--text-muted); font-size:13px; }
footer { margin-top:48px; padding-top:16px; border-top:1px solid var(--border);
  font-size:12px; color:var(--text-muted); }
.roundlist { margin-top:32px; display:flex; flex-direction:column; gap:12px; }
@media (prefers-reduced-motion:reduce){ *{ transition:none!important; } }
"""

DISCLAIMER = "본 분석은 통계적 참고 자료이며 구매 결과를 보장하지 않습니다."


def page(title: str, body: str) -> str:
    return (f'<!doctype html><html lang="ko"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta name="robots" content="noindex">'
            f'<title>{title}</title><style>{CSS}</style></head>'
            f'<body><div class="wrap">{body}</div></body></html>')


def fmt_kst(dt: datetime) -> str:
    return dt.astimezone(KST).strftime("%m-%d %H:%M")


def vote_bar(m: Match) -> str:
    d = m.vote_dist
    parts = []
    for key, cls in (("win", "w"), ("draw", "d"), ("lose", "l")):
        p = d.get(key) or 0
        label = f"{p:.0%}" if p >= 0.08 else ""
        parts.append(f'<span class="{cls} num" style="width:{p*100:.1f}%">{label}</span>')
    return f'<div class="bar" title="대중 투표 분포 승/무/패">{"".join(parts)}</div>'


def match_card(m: Match) -> str:
    status = "" if m.status == "scheduled" else ' · <span class="pill">적특 예상</span>'
    return f"""<div class="card">
<div class="top"><span>M{m.match_no:02d} · {m.league}</span><span class="num">{fmt_kst(m.kickoff)}{status}</span></div>
<div class="teams serif">{m.home.betman_name}<span class="vs">vs</span>{m.away.betman_name}</div>
{vote_bar(m)}
</div>"""


def build_round_page(r: Round, out_dir: Path):
    body = f"""<div class="hero">
<h1 class="serif">승무패 {r.round_no}회차</h1>
<div class="meta num">발매 마감 {r.sale_close.strftime('%Y-%m-%d %H:%M')} ·
{r.collected_at.strftime('%m-%d %H:%M')} 기준 최신 정보 · <a href="../../index.html" style="color:inherit">전체 회차</a></div>
</div>
<div class="notice">아직 이번 회차 분석이 생성되지 않았습니다. 마감 12시간 전({fmt_kst(r.analysis_due)})에 자동 생성됩니다.
막대는 배트맨 이용자들의 승/무/패 투표 분포입니다.</div>
<div class="cards">{"".join(match_card(m) for m in r.matches)}</div>
<div class="legend">
<span><i style="background:var(--accent)"></i>홈 승</span>
<span><i style="background:var(--kraft)"></i>무승부</span>
<span><i style="background:var(--olive)"></i>원정 승</span>
</div>
<footer>{DISCLAIMER} 데이터 기준: {r.collected_at.strftime('%Y-%m-%d %H:%M')} (배트맨 투표 현황)</footer>"""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        page(f"승무패 {r.round_no}회차 · AI 분석", body), encoding="utf-8")


def build_index(rounds: list[Round]):
    items = []
    for r in sorted(rounds, key=lambda x: (x.year, x.round_no), reverse=True):
        key = f"{r.year}-{r.round_no}"
        stage = '<span class="pill">분석 예정</span>'  # ②③ 단계는 3~4주차에 분기
        items.append(f"""<a class="card" href="rounds/{key}/index.html">
<div class="top"><span>{r.year}년</span><span class="num">마감 {r.sale_close.strftime('%m-%d %H:%M')}</span></div>
<div class="teams serif">승무패 {r.round_no}회차 {stage}</div>
<div class="top"><span>축구 {len(r.matches)}경기</span></div>
</a>""")
    body = f"""<div class="hero">
<h1 class="serif">승무패 · AI 최종 분석</h1>
<div class="meta">회차별 경기 정보와 마감 12시간 전 AI 분석 리포트</div>
</div>
<div class="roundlist">{"".join(items) or '<div class="notice">아직 수집된 회차가 없습니다.</div>'}</div>
<footer>{DISCLAIMER}</footer>"""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(page("승무패 AI 분석", body), encoding="utf-8")


def build_all():
    rounds = []
    for f in sorted(ROUNDS_DIR.glob("*.json")):
        r = Round.model_validate_json(f.read_text(encoding="utf-8"))
        rounds.append(r)
        build_round_page(r, SITE_DIR / "rounds" / f"{r.year}-{r.round_no}")
    build_index(rounds)
    print(f"site built: {len(rounds)} rounds -> {SITE_DIR}")


if __name__ == "__main__":
    build_all()
