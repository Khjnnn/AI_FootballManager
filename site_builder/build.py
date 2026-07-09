"""정적 사이트 빌더 (plan.md 7.5절).

data/rounds/*.json + data/reports/{key}/ → site/ 정적 HTML.
- ① 예정: 경기 리스트 + 대중 투표 분포 바
- ② 분석: AI 확률 바 + 최종 픽·신뢰도 배지 + 경기별 상세 페이지 + 종합 리포트
- ③ 결과: 4주차 확장 예정 (results/ 반영)

디자인: design_teq.md 토큰·컴포넌트 규칙 준수.
실행: python -m site_builder.build
"""
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from markdown import markdown

from collector.models import Match, Round

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent
ROUNDS_DIR = ROOT / "data" / "rounds"
REPORTS_DIR = ROOT / "data" / "reports"
SITE_DIR = ROOT / "site"

PICK_KO = {"win": "승", "draw": "무", "lose": "패"}
CONF_CLASS = {"상": "conf-high", "중": "conf-mid", "하": "conf-low"}
JSON_BLOCK = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)

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
.hero .meta a { color:inherit; }
.cards { display:grid; grid-template-columns:repeat(auto-fill,minmax(420px,1fr)); gap:16px; margin-top:32px; }
@media (max-width:900px){ .cards{ grid-template-columns:1fr; } }
.card {
  background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:16px 20px; box-shadow:0 1px 3px rgba(31,30,29,0.06);
  transition:background 120ms ease; display:block; color:inherit; text-decoration:none;
}
a.card:hover { background:var(--surface-raised); }
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
  padding:2px 12px; font-size:12px; color:var(--text-muted); background:transparent; }
.pill.accent { background:var(--accent-soft); color:var(--accent); border-color:transparent; font-weight:600; }
.pill.conf-high { background:var(--text); color:var(--bg); border-color:var(--text); }
.pill.conf-mid { border:1px solid var(--text-muted); color:var(--text); }
.pill.conf-low { border:1px dashed var(--text-muted); color:var(--text-muted); }
.badges { display:flex; gap:8px; align-items:center; margin-top:12px; flex-wrap:wrap; }
.sub { font-size:12px; color:var(--text-muted); margin-top:10px; }
.notice { background:var(--surface); border:1px solid var(--border); border-radius:16px;
  padding:16px 20px; margin-top:32px; color:var(--text-muted); font-size:13px; }
footer { margin-top:48px; padding-top:16px; border-top:1px solid var(--border);
  font-size:12px; color:var(--text-muted); }
.roundlist { margin-top:32px; display:flex; flex-direction:column; gap:12px; }
article { margin-top:32px; }
article h1 { font-family:"Noto Serif KR",Georgia,serif; font-size:26px; margin:24px 0 12px; }
article h2 { font-family:"Noto Serif KR",Georgia,serif; font-size:20px; margin:28px 0 8px; }
article h3 { font-size:16px; margin:20px 0 8px; }
article p, article li { margin-bottom:8px; }
article ul, article ol { padding-left:22px; }
article hr { border:none; border-top:1px solid var(--border); margin:24px 0; }
article em { color:var(--text-muted); }
article a { color:var(--accent); }
.tablewrap { overflow-x:auto; }
article table { border-collapse:collapse; width:100%; font-size:13px; margin:12px 0; }
article th, article td { border-bottom:1px solid var(--border); padding:10px 12px; text-align:left; }
article td { font-variant-numeric:tabular-nums; }
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


def prob_bar(probs: dict, title: str) -> str:
    parts = []
    for key, cls in (("win", "w"), ("draw", "d"), ("lose", "l")):
        p = probs.get(key) or 0
        label = f"{p:.0%}" if p >= 0.08 else ""
        parts.append(f'<span class="{cls} num" style="width:{p*100:.1f}%">{label}</span>')
    return f'<div class="bar" title="{title}">{"".join(parts)}</div>'


def load_reports(key: str) -> tuple[dict, bool]:
    """(summaries, has_round_report)"""
    sp = REPORTS_DIR / key / "summary.json"
    summaries = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    return summaries, (REPORTS_DIR / key / "round.md").exists()


def match_card(m: Match, key: str, summary: dict | None) -> str:
    name = f"M{m.match_no:02d}"
    top = (f'<div class="top"><span>{name} · {m.league}</span>'
           f'<span class="num">{fmt_kst(m.kickoff)}</span></div>')
    teams = (f'<div class="teams serif">{m.home.betman_name}'
             f'<span class="vs">vs</span>{m.away.betman_name}</div>')

    if m.status != "scheduled":
        body = top + teams + '<div class="badges"><span class="pill">적특 예상 (취소·연기)</span></div>'
        return f'<div class="card">{body}</div>'

    vote_line = " · ".join(f"{PICK_KO[k]} {int(round((m.vote_dist.get(k) or 0)*100))}%"
                           for k in ("win", "draw", "lose"))
    if summary and not summary.get("void"):
        bar = prob_bar(summary["probs"], "AI 예측 확률 승/무/패")
        conf = summary.get("confidence", "중")
        badges = (f'<div class="badges">'
                  f'<span class="pill accent">픽 · {PICK_KO.get(summary["pick"], "?")}</span>'
                  f'<span class="pill">보조 · {PICK_KO.get(summary.get("backup_pick"), "—")}</span>'
                  f'<span class="pill {CONF_CLASS.get(conf, "conf-mid")}">신뢰도 {conf}</span></div>')
        sub = f'<div class="sub num">대중 투표: {vote_line}</div>'
        report = REPORTS_DIR / key / f"{name}.md"
        inner = top + teams + bar + badges + sub
        if report.exists():
            return f'<a class="card" href="{name.lower()}.html">{inner}</a>'
        return f'<div class="card">{inner}</div>'

    # 분석 전(①) 또는 미완: 투표 분포 바
    bar = prob_bar(m.vote_dist, "대중 투표 분포 승/무/패")
    pending = '<div class="badges"><span class="pill">분석 대기</span></div>' if summary is None else ""
    return f'<div class="card">{top}{teams}{bar}{pending}</div>'


def render_markdown(md_text: str) -> str:
    text = JSON_BLOCK.sub("", md_text)  # 기계용 JSON 블록은 페이지에서 숨김
    # 리포트 말미의 고지문(푸터가 대신)과 중첩 CLI 상용구를 본문에서 제거
    drop = ("본 분석은 통계적 참고 자료", "📊 bkit", "✅ Used", "✅ 사용", "⏭️", "⏭ ",
            "💡 Recommended", "💡 추천")
    text = "\n".join(ln for ln in text.splitlines()
                     if not any(d in ln for d in drop) and set(ln.strip()) != {"─"})
    text = re.sub(r"(\n---\s*)+$", "", text.rstrip())
    html = markdown(text, extensions=["tables", "fenced_code"])
    return html.replace("<table>", '<div class="tablewrap"><table>') \
               .replace("</table>", "</table></div>")


def build_match_page(m: Match, key: str, out_dir: Path):
    report = REPORTS_DIR / key / f"M{m.match_no:02d}.md"
    if not report.exists():
        return
    body = f"""<div class="hero">
<h1 class="serif">{m.home.betman_name} vs {m.away.betman_name}</h1>
<div class="meta num">M{m.match_no:02d} · {m.league} · 킥오프 {fmt_kst(m.kickoff)} ·
<a href="index.html">회차로 돌아가기</a></div></div>
<article>{render_markdown(report.read_text(encoding="utf-8"))}</article>
<footer>{DISCLAIMER}</footer>"""
    (out_dir / f"m{m.match_no:02d}.html").write_text(
        page(f"{m.home.betman_name} vs {m.away.betman_name} · AI 분석", body),
        encoding="utf-8")


def build_round_report_page(r: Round, key: str, out_dir: Path):
    report = REPORTS_DIR / key / "round.md"
    if not report.exists():
        return
    body = f"""<div class="hero">
<h1 class="serif">승무패 {r.round_no}회차 · 종합 리포트</h1>
<div class="meta num">발매 마감 {r.sale_close.strftime('%Y-%m-%d %H:%M')} ·
<a href="index.html">경기 카드 보기</a></div></div>
<article>{render_markdown(report.read_text(encoding="utf-8"))}</article>
<footer>{DISCLAIMER}</footer>"""
    (out_dir / "round.html").write_text(
        page(f"승무패 {r.round_no}회차 종합 리포트", body), encoding="utf-8")


def build_round_page(r: Round, out_dir: Path):
    key = f"{r.year}-{r.round_no}"
    summaries, has_round = load_reports(key)
    analyzed = bool(summaries)

    if analyzed:
        n = len([s for s in summaries.values() if not s.get("void")])
        link = ' · <a href="round.html">종합 리포트</a>' if has_round else ""
        notice = (f'<div class="notice">AI 분석 {n}/14 경기 완료. 막대는 AI 예측 확률, '
                  f'카드에서 경기별 상세 분석을 볼 수 있습니다.{link}</div>')
        bar_label = "AI 예측 확률"
    else:
        notice = (f'<div class="notice">아직 이번 회차 분석이 생성되지 않았습니다. '
                  f'마감 12시간 전({fmt_kst(r.analysis_due)})에 자동 생성됩니다. '
                  f'막대는 배트맨 이용자들의 승/무/패 투표 분포입니다.</div>')
        bar_label = "대중 투표 분포"

    cards = "".join(match_card(m, key, summaries.get(f"M{m.match_no:02d}"))
                    for m in r.matches)
    body = f"""<div class="hero">
<h1 class="serif">승무패 {r.round_no}회차{' · AI 최종 분석' if analyzed else ''}</h1>
<div class="meta num">발매 마감 {r.sale_close.strftime('%Y-%m-%d %H:%M')} ·
{r.collected_at.strftime('%m-%d %H:%M')} 기준 최신 정보 · <a href="../../index.html">전체 회차</a></div>
</div>
{notice}
<div class="cards">{cards}</div>
<div class="legend">
<span><i style="background:var(--accent)"></i>홈 승</span>
<span><i style="background:var(--kraft)"></i>무승부</span>
<span><i style="background:var(--olive)"></i>원정 승</span>
<span>({bar_label})</span>
</div>
<footer>{DISCLAIMER} 데이터 기준: {r.collected_at.strftime('%Y-%m-%d %H:%M')}</footer>"""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        page(f"승무패 {r.round_no}회차 · AI 분석", body), encoding="utf-8")

    for m in r.matches:
        build_match_page(m, key, out_dir)
    build_round_report_page(r, key, out_dir)


def build_index(rounds: list[Round]):
    items = []
    for r in sorted(rounds, key=lambda x: (x.year, x.round_no), reverse=True):
        key = f"{r.year}-{r.round_no}"
        summaries, has_round = load_reports(key)
        stage = ('<span class="pill accent">분석 완료</span>' if has_round
                 else '<span class="pill">분석 진행 중</span>' if summaries
                 else '<span class="pill">분석 예정</span>')
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
