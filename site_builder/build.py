"""정적 사이트 빌더 (plan.md 7.5절) — 다크 네온 디자인 (Claude Design 'Round Analysis' 참조).

data/rounds/*.json + data/reports/{key}/ → site/ 정적 HTML.
- 회차 페이지: 2단(리스트+상세) 단일 페이지 앱, 실데이터 기반
- 경기별 상세 리포트 페이지(전체 마크다운), 회차 종합 리포트 페이지, 아카이브 인덱스

실행: python -m site_builder.build
"""
import json
import re
from datetime import timedelta, timezone
from pathlib import Path

from markdown import markdown

from collector.models import Match, Round
from site_builder import theme as T

KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).parent.parent
ROUNDS_DIR = ROOT / "data" / "rounds"
REPORTS_DIR = ROOT / "data" / "reports"
MATCHES_DIR = ROOT / "data" / "matches"
MIX_DIR = ROOT / "data" / "mix"
SITE_DIR = ROOT / "site"

PICK_KO = {"win": "승", "draw": "무", "lose": "패"}
JSON_BLOCK = re.compile(r"```json\s*\{.*?\}\s*```", re.DOTALL)


# ── 데이터 추출 ────────────────────────────────────────────────
def load_summaries(key: str) -> tuple[dict, bool]:
    sp = REPORTS_DIR / key / "summary.json"
    summaries = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    return summaries, (REPORTS_DIR / key / "round.md").exists()


def load_mix(key: str) -> dict | None:
    """추천 조합(MIX) 리포트 데이터. data/mix/{key}.json 있으면 반환, 없으면 None."""
    mp = MIX_DIR / f"{key}.json"
    if not mp.exists():
        return None
    try:
        return json.loads(mp.read_text(encoding="utf-8"))
    except Exception:
        return None


def match_payload(r: Round, key: str, summaries: dict) -> list[dict]:
    """SPA가 소비할 경기별 데이터 배열."""
    pkg_dir = MATCHES_DIR / key
    out = []
    for m in r.matches:
        name = f"M{m.match_no:02d}"
        s = summaries.get(name)
        market = None
        pkg_file = pkg_dir / f"{name}.json"
        if pkg_file.exists():
            mo = json.loads(pkg_file.read_text(encoding="utf-8")).get("market_odds")
            if mo and mo.get("implied_prob"):
                ip = mo["implied_prob"]
                market = {
                    "w": round(ip["win"] * 100), "d": round(ip["draw"] * 100),
                    "l": round(ip["lose"] * 100),
                    "ow": mo.get("win"), "od": mo.get("draw"), "ol": mo.get("lose"),
                    "books": mo.get("bookmakers"),
                }
        vd = m.vote_dist
        report_href = f"{name.lower()}.html" if (REPORTS_DIR / key / f"{name}.md").exists() else None
        item = {
            "no": name,
            "league": m.league,
            "date": m.kickoff.astimezone(KST).strftime("%m-%d"),
            "time": m.kickoff.astimezone(KST).strftime("%H:%M"),
            "home": m.home.betman_name,
            "away": m.away.betman_name,
            "venue": m.stadium or "",
            "status": m.status,
            "pubW": round((vd.get("win") or 0) * 100),
            "pubD": round((vd.get("draw") or 0) * 100),
            "pubL": round((vd.get("lose") or 0) * 100),
            "market": market,
            "reportHref": report_href,
            "analyzed": bool(s and not s.get("void")),
        }
        if item["analyzed"]:
            p = s["probs"]
            item.update({
                "w": round(p["win"] * 100), "d": round(p["draw"] * 100),
                "l": round(p["lose"] * 100),
                "pick": PICK_KO.get(s["pick"], "?"),
                "sub": PICK_KO.get(s.get("backup_pick"), "—"),
                "conf": s.get("confidence", "중"),
                "keyFactors": s.get("key_factors", []),
                "dataGaps": s.get("data_gaps", []),
                "expectedScores": s.get("expected_scores", []),
            })
        else:
            item.update({"w": item["pubW"], "d": item["pubD"], "l": item["pubL"],
                         "pick": None, "sub": None, "conf": None,
                         "keyFactors": [], "dataGaps": [], "expectedScores": []})
        out.append(item)
    return out


# ── 회차 SPA 페이지 ─────────────────────────────────────────────
# 색·문구는 JS 객체 C로 주입한다 (Python % 포매팅과 JS 리터럴 % 충돌 방지).
ROUND_JS = r"""
const OC = {'승':C.win,'무':C.draw,'패':C.lose};
function confColor(c){return c==='하'?C.muted:c==='중'?C.draw:C.win;}
function confDesc(c){return c==='하'?'변수 큰 접전':c==='중'?'무게 실림':'안정적';}
function dayLabel(d){const [mm,dd]=d.split('-').map(Number);
  const wd=['일','월','화','수','목','금','토'][new Date(2026,mm-1,dd).getDay()];
  return mm+'월 '+dd+'일 ('+wd+')';}
function esc(s){return (s==null?'':String(s)).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}

let sel = 0, detailOpen = false;
const isMobile = () => window.innerWidth < 860;

function bar(w,d,l,h){return `<div style="display:flex;height:${h}px;border-radius:${h>10?6:3}px;overflow:hidden;background:rgba(255,255,255,0.05);">
  <div style="width:${w}%;background:${C.win}"></div><div style="width:${d}%;background:${C.draw}"></div><div style="width:${l}%;background:${C.lose}"></div></div>`;}

function renderList(){
  const el=document.getElementById('list'); let html=''; let prevDate=null;
  DATA.forEach((m,i)=>{
    if(m.date!==prevDate){html+=`<div style="padding:14px 18px 8px;font-size:12px;font-weight:600;color:#8A93A3;position:sticky;top:0;background:${C.bg};z-index:2;">${dayLabel(m.date)}</div>`;prevDate=m.date;}
    const active=i===sel;
    const pickColor=m.pick?OC[m.pick]:C.faint;
    const topPct=m.pick?(m.pick==='승'?m.w:m.pick==='무'?m.d:m.l):Math.max(m.pubW,m.pubD,m.pubL);
    const pickBadge=m.pick?`<span style="font-size:11px;font-weight:700;color:${C.bg};background:${pickColor};padding:2px 8px;border-radius:6px;">픽 ${m.pick}</span>`
      :`<span style="font-size:10px;font-weight:600;color:${C.muted};border:1px solid ${C.border};padding:2px 7px;border-radius:6px;">대기</span>`;
    html+=`<div onclick="selectMatch(${i})" style="display:flex;align-items:center;gap:11px;padding:13px 16px 13px 15px;cursor:pointer;border-left:3px solid ${active?C.accent:'transparent'};background:${active?'rgba(199,249,78,0.06)':'transparent'};border-bottom:1px solid rgba(255,255,255,0.04);">
      <span class="mono" style="font-size:11px;font-weight:600;color:${C.faint};width:26px;flex-shrink:0;">${m.no}</span>
      <div style="min-width:0;flex:1;">
        <div style="display:flex;align-items:center;gap:7px;font-size:14px;font-weight:600;">
          <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:86px;">${esc(m.home)}</span>
          <span style="font-size:11px;color:${C.faint};">vs</span>
          <span style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:86px;">${esc(m.away)}</span>
        </div>
        <div style="margin-top:8px;width:118px;">${bar(m.w,m.d,m.l,4)}</div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:5px;flex-shrink:0;">
        ${pickBadge}<span class="num" style="font-size:12px;font-weight:600;color:${pickColor};">${topPct}%</span>
      </div>
    </div>`;
  });
  el.innerHTML=html;
}

function card(inner,extra){return `<div style="background:${C.surface};border:1px solid ${C.borderSoft};border-radius:14px;padding:20px 22px;margin-top:14px;${extra||''}">${inner}</div>`;}
function label(t){return `<div class="mono" style="font-size:12px;letter-spacing:0.12em;text-transform:uppercase;color:${C.muted};font-weight:600;margin-bottom:15px;">${t}</div>`;}
function miniCard(t,inner){return `<div style="flex:1;background:${C.surface};border:1px solid ${C.borderSoft};border-radius:14px;padding:17px 18px;">
  <div class="mono" style="font-size:11px;letter-spacing:0.1em;text-transform:uppercase;color:${C.muted};font-weight:600;margin-bottom:11px;">${t}</div>${inner}</div>`;}
function oddCell(lbl,odd,pct,c){return `<div style="flex:1;text-align:center;padding:10px 4px;background:rgba(255,255,255,0.03);border-radius:10px;">
  <div style="font-size:11px;color:${c};font-weight:600;margin-bottom:4px;">${lbl}</div>
  <div class="num" style="font-size:18px;font-weight:700;color:${C.text};">${odd?odd.toFixed(2):'-'}</div>
  <div class="num" style="font-size:11px;color:${C.muted};margin-top:2px;">${pct}%</div></div>`;}
function disclaimer(){return `<div style="margin-top:22px;font-size:11px;color:#4A5261;line-height:1.6;">${C.disclaimer}</div>`;}

function renderDetail(){
  const m=DATA[sel]; const el=document.getElementById('detail');
  const pickColor=m.pick?OC[m.pick]:C.faint;
  let html='';
  if(isMobile()) html+=`<div onclick="goBack()" style="display:inline-flex;gap:6px;font-size:13px;color:#8A93A3;cursor:pointer;margin-bottom:16px;font-weight:500;">← 리스트로</div>`;
  html+=`<div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;font-size:12px;color:#8A93A3;">
    <span class="mono" style="font-weight:600;color:${C.accent};background:rgba(199,249,78,0.10);padding:3px 9px;border-radius:6px;">${m.no}</span>
    <span style="padding:3px 9px;border-radius:6px;background:rgba(255,255,255,0.06);color:${C.dim};">${esc(m.league)}</span>
    <span>${m.date} ${m.time}</span>${m.venue?`<span style="color:${C.faint};">·</span><span>${esc(m.venue)}</span>`:''}</div>`;
  html+=`<div style="display:flex;align-items:center;gap:16px;margin:24px 0 6px;">
    <div style="flex:1;text-align:right;min-width:0;"><div class="mono" style="font-size:11px;letter-spacing:0.14em;color:${C.faint};margin-bottom:5px;font-weight:600;">HOME</div>
      <div style="font-size:27px;font-weight:700;letter-spacing:-0.025em;line-height:1.1;">${esc(m.home)}</div></div>
    <div class="mono" style="font-size:15px;font-weight:600;color:#4A5261;flex-shrink:0;">VS</div>
    <div style="flex:1;min-width:0;"><div class="mono" style="font-size:11px;letter-spacing:0.14em;color:${C.faint};margin-bottom:5px;font-weight:600;">AWAY</div>
      <div style="font-size:27px;font-weight:700;letter-spacing:-0.025em;line-height:1.1;">${esc(m.away)}</div></div></div>`;

  if(!m.analyzed){
    html+=card(label('대중 투표 분포')+bar(m.pubW,m.pubD,m.pubL,12)+
      `<div style="margin-top:12px;font-size:13px;color:${C.dim};">아직 AI 분석이 생성되지 않았습니다. 마감 12시간 전에 자동 생성됩니다. 위 막대는 배트맨 이용자 투표(승 ${m.pubW}% / 무 ${m.pubD}% / 패 ${m.pubL}%)입니다.</div>`);
    html+=disclaimer(); el.innerHTML=html; return;
  }

  const bigCell=(c,lbl,v)=>`<div style="flex:1;text-align:center;padding:14px 4px;background:${c}12;border:1px solid ${c}2e;border-radius:11px;">
    <div style="font-size:12px;color:${c};font-weight:600;margin-bottom:5px;">${lbl}</div>
    <div class="num" style="font-size:29px;font-weight:700;color:${c};letter-spacing:-0.02em;">${v}%</div></div>`;
  html+=card(label('AI 예측 확률')+bar(m.w,m.d,m.l,12)+
    `<div style="display:flex;gap:10px;margin-top:16px;">${bigCell(C.win,'승 · 홈',m.w)}${bigCell(C.draw,'무',m.d)}${bigCell(C.lose,'패 · 원정',m.l)}</div>`);
  html+=`<div style="display:flex;gap:10px;margin-top:14px;">
    ${miniCard('AI 픽',`<div style="display:inline-flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;color:${C.bg};background:${pickColor};min-width:44px;height:38px;padding:0 12px;border-radius:9px;">${m.pick}</div>`)}
    ${miniCard('보조 픽',`<div style="display:inline-flex;align-items:center;justify-content:center;font-size:20px;font-weight:700;color:${C.text};background:rgba(255,255,255,0.07);border:1px solid rgba(255,255,255,0.12);min-width:44px;height:38px;padding:0 12px;border-radius:9px;">${m.sub}</div>`)}
    ${miniCard('신뢰도',`<div style="display:inline-flex;align-items:center;gap:8px;"><span style="font-size:22px;font-weight:700;color:${confColor(m.conf)};">${m.conf}</span><span style="font-size:12px;color:${C.muted};">${confDesc(m.conf)}</span></div>`)}</div>`;
  const pubMax=Math.max(m.pubW,m.pubD,m.pubL);
  const pubPick=m.pubW===pubMax?'승':m.pubD===pubMax?'무':'패';
  const pubCell=(w,c,lbl)=>`<div style="width:${w}%;background:${c}d9;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:700;color:${C.bg};">${w>=12?lbl:''}</div>`;
  let cmp=label('대중 투표 vs AI')+
    `<div style="display:flex;align-items:center;gap:12px;margin-bottom:11px;"><span style="width:44px;font-size:12px;color:#8A93A3;flex-shrink:0;">대중</span>
      <div style="flex:1;display:flex;height:26px;border-radius:7px;overflow:hidden;background:rgba(255,255,255,0.05);">${pubCell(m.pubW,C.win,'승 '+m.pubW+'%')}${pubCell(m.pubD,C.draw,'무 '+m.pubD+'%')}${pubCell(m.pubL,C.lose,'패 '+m.pubL+'%')}</div></div>
    <div style="display:flex;align-items:center;gap:12px;"><span style="width:44px;font-size:12px;color:#8A93A3;flex-shrink:0;">AI</span><div style="flex:1;">${bar(m.w,m.d,m.l,8)}</div></div>`;
  if(pubPick!==m.pick) cmp+=`<div style="display:flex;gap:9px;margin-top:15px;padding:11px 13px;background:rgba(255,93,108,0.08);border:1px solid rgba(255,93,108,0.2);border-radius:10px;"><span style="color:${C.lose};font-weight:700;">!</span><span style="font-size:13px;color:#D6A9AE;line-height:1.5;">대중은 '${pubPick}'(${pubMax}%)에 몰렸지만 AI 픽은 '${m.pick}'입니다. 여론과 엇갈리는 경기이니 신중히 판단하세요.</span></div>`;
  html+=card(cmp);
  if(m.market){
    const mk=m.market;
    html+=card(label('해외 시장 배당 (북메이커 '+mk.books+'곳 중앙값)')+bar(mk.w,mk.d,mk.l,8)+
      `<div style="display:flex;gap:10px;margin-top:14px;">${oddCell('승',mk.ow,mk.w,C.win)}${oddCell('무',mk.od,mk.d,C.draw)}${oddCell('패',mk.ol,mk.l,C.lose)}</div>`);
  } else {
    html+=card(label('해외 시장 배당')+`<div style="font-size:13px;color:${C.dim};">이 리그(K리그2 등)는 해외 배당 미커버로, 예측은 대중 투표 분포를 기준선으로 삼았습니다.</div>`);
  }
  if(m.keyFactors.length){
    html+=card(label('핵심 근거')+`<ul style="margin:0;padding-left:18px;font-size:14px;line-height:1.7;color:${C.dim};">`+
      m.keyFactors.map(f=>`<li style="margin-bottom:6px;">${esc(f)}</li>`).join('')+'</ul>');
  }
  if(m.expectedScores.length){
    html+=card(label('예상 스코어')+'<div style="display:flex;gap:8px;">'+
      m.expectedScores.map(s=>`<span class="num" style="font-size:16px;font-weight:600;color:${C.text};background:rgba(255,255,255,0.05);padding:6px 14px;border-radius:8px;">${esc(s)}</span>`).join('')+'</div>');
  }
  if(m.dataGaps.length){
    html+=card(label('데이터 결측')+`<ul style="margin:0;padding-left:18px;font-size:12px;line-height:1.6;color:${C.muted};">`+
      m.dataGaps.map(g=>`<li style="margin-bottom:4px;">${esc(g)}</li>`).join('')+'</ul>');
  }
  if(m.reportHref){
    html+=`<div style="margin-top:18px;"><a href="${m.reportHref}" style="display:inline-flex;align-items:center;gap:6px;font-size:14px;font-weight:600;color:${C.accent};background:rgba(199,249,78,0.10);border:1px solid rgba(199,249,78,0.22);padding:10px 16px;border-radius:10px;">전체 분석 리포트 보기 →</a></div>`;
  }
  html+=disclaimer(); el.innerHTML=html;
}

function selectMatch(i){sel=i;detailOpen=true;render();const mn=document.querySelector('main');if(mn)mn.scrollTop=0;}
function goBack(){detailOpen=false;render();}
function render(){
  const mob=isMobile();
  document.getElementById('aside').style.display=(mob&&detailOpen)?'none':'flex';
  document.querySelector('main').style.display=(mob&&!detailOpen)?'none':'flex';
  document.getElementById('aside').style.width=mob?'100%':'400px';
  renderList();renderDetail();
}
window.addEventListener('resize',render);
render();
"""


# ── 추천 조합(MIX) 패널 ─────────────────────────────────────────
MIX_JS = r"""
const PICKC = {'홈':C.win,'무':C.draw,'원정':C.lose};
function short(s){s=s==null?'':String(s); return s.length>4?s.slice(0,4):s;}
function pickChip(p){const c=PICKC[p]||C.muted;
  return `<span style="font-size:11px;font-weight:700;color:${C.bg};background:${c};padding:2px 6px;border-radius:5px;line-height:1.4;">${p}</span>`;}
function comboCard(cb){
  const cells = cb.picks.map((ps,i)=>{
    const m = (typeof DATA!=='undefined' && DATA[i]) ? DATA[i] : null;
    const no = m?m.no:('M'+String(i+1).padStart(2,'0'));
    const matchup = m?`${esc(short(m.home))}<span style="color:${C.faint};margin:0 1px;">·</span>${esc(short(m.away))}`:'';
    const multi = ps.length>1;
    return `<div style="background:rgba(255,255,255,0.03);border:1px solid ${multi?'rgba(199,249,78,0.22)':C.borderSoft};border-radius:9px;padding:7px 6px;text-align:center;">
      <div class="mono" style="font-size:10px;font-weight:600;color:${C.faint};">${no}</div>
      <div style="font-size:10px;color:${C.muted};margin:2px 0 5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${matchup}</div>
      <div style="display:flex;gap:3px;justify-content:center;flex-wrap:wrap;">${ps.map(pickChip).join('')}</div>
    </div>`;
  }).join('');
  return `<div style="flex:1;min-width:300px;background:${C.surface};border:1px solid ${C.borderSoft};border-radius:14px;padding:16px 18px;">
    <div style="display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-bottom:5px;">
      <span class="mono" style="font-size:14px;font-weight:800;color:${C.bg};background:${C.accent};padding:2px 9px;border-radius:7px;">${esc(cb.id)}</span>
      <span style="font-size:15px;font-weight:700;color:${C.text};">${esc(cb.method)}</span>
      <span class="num" style="margin-left:auto;font-size:12px;font-weight:700;color:${C.accent};background:rgba(199,249,78,0.10);border:1px solid rgba(199,249,78,0.22);padding:3px 10px;border-radius:999px;">기대 ${cb.expectedHits} / 14</span>
    </div>
    <div style="font-size:12px;color:${C.muted};line-height:1.5;margin-bottom:13px;">${esc(cb.subtitle)} · ${cb.cases}경우의 수</div>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(72px,1fr));gap:7px;">${cells}</div>
  </div>`;
}
function renderMixPanel(){
  const p = document.getElementById('mixpanel'); if(!p||typeof MIX==='undefined'||!MIX) return;
  const lg = `<span style="display:inline-flex;align-items:center;gap:5px;">${pickChip('홈')}<span style="color:${C.muted};">홈(승)</span></span>
    <span style="display:inline-flex;align-items:center;gap:5px;">${pickChip('무')}<span style="color:${C.muted};">무</span></span>
    <span style="display:inline-flex;align-items:center;gap:5px;">${pickChip('원정')}<span style="color:${C.muted};">원정(패)</span></span>
    <span style="color:${C.faint};">· 여러 칩 = 복수선택(더블·트리플)</span>`;
  p.innerHTML = `<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;font-size:11px;margin-bottom:13px;">${lg}</div>
    <div style="display:flex;gap:14px;flex-wrap:wrap;">${MIX.combos.map(comboCard).join('')}</div>
    <div style="margin-top:13px;font-size:11px;color:${C.faint};line-height:1.6;">${esc(MIX.note||'')}</div>`;
}
let mixOpen = false;
function toggleMix(){
  mixOpen = !mixOpen;
  const p=document.getElementById('mixpanel'), c=document.getElementById('mixcaret');
  if(!p) return;
  p.style.display = mixOpen?'block':'none';
  if(c) c.textContent = mixOpen?'접기 ▴':'펼치기 ▾';
  if(mixOpen) renderMixPanel();
}
"""


def build_round_page(r: Round, out_dir: Path):
    key = f"{r.year}-{r.round_no}"
    summaries, has_round = load_summaries(key)
    data = match_payload(r, key, summaries)
    n_analyzed = sum(1 for d in data if d["analyzed"])

    status_pill = (f"AI 분석 {n_analyzed}/14 완료" if n_analyzed == 14
                   else f"AI 분석 {n_analyzed}/14 진행" if n_analyzed
                   else "분석 대기")
    round_link = (f'<a href="round.html" class="mono" style="font-size:12px;font-weight:600;color:{T.ACCENT};'
                  f'background:rgba(199,249,78,0.10);border:1px solid rgba(199,249,78,0.22);'
                  f'padding:5px 12px;border-radius:999px;">종합 리포트</a>') if has_round else ""

    legend = "".join(
        f'<span style="display:inline-flex;align-items:center;gap:5px;">'
        f'<span style="width:9px;height:9px;border-radius:3px;background:{c};"></span>{lbl}</span>'
        for c, lbl in ((T.WIN, "승"), (T.DRAW, "무"), (T.LOSE, "패")))

    C = {
        "win": T.WIN, "draw": T.DRAW, "lose": T.LOSE, "accent": T.ACCENT,
        "bg": T.BG, "surface": T.SURFACE, "muted": T.TEXT_MUTED, "faint": T.TEXT_FAINT,
        "dim": T.TEXT_DIM, "text": T.TEXT, "border": T.BORDER, "borderSoft": T.BORDER_SOFT,
        "disclaimer": f"{T.DISCLAIMER} · 데이터 기준 {r.collected_at.strftime('%Y-%m-%d %H:%M')}",
    }
    c_json = json.dumps(C, ensure_ascii=False)
    data_json = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")

    mix = load_mix(key)
    mix_json = json.dumps(mix, ensure_ascii=False).replace("</", "<\\/") if mix else "null"
    if mix:
        chips = " · ".join(
            f'{cb["id"]} {cb["method"]} '
            f'<span class="num" style="color:{T.ACCENT};">{cb["expectedHits"]}/14</span>'
            for cb in mix["combos"])
        mix_bar = f"""  <div style="flex-shrink:0;border-bottom:1px solid {T.BORDER};background:{T.SURFACE_RAISED};">
    <div onclick="toggleMix()" style="display:flex;align-items:center;gap:11px;padding:11px 22px;cursor:pointer;">
      <span style="font-size:14px;">🎯</span>
      <span class="mono" style="font-size:12px;font-weight:700;letter-spacing:0.04em;color:{T.ACCENT};">추천 조합 · MIX</span>
      <span style="font-size:12px;color:{T.TEXT_MUTED};white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{chips}</span>
      <span id="mixcaret" class="mono" style="margin-left:auto;font-size:11px;font-weight:600;color:{T.TEXT_MUTED};flex-shrink:0;white-space:nowrap;">펼치기 ▾</span>
    </div>
    <div id="mixpanel" style="display:none;padding:2px 22px 20px;max-height:52vh;overflow-y:auto;"></div>
  </div>
"""
    else:
        mix_bar = ""

    round_css = (
        "@media (max-width:860px){"
        ".hd-legend{display:none!important;}"
        ".hd-title{font-size:15px!important;}"
        ".hd-meta{white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:52vw;}"
        "header{padding:12px 16px!important;gap:10px!important;}}"
    )

    body = f"""<div style="height:100vh;display:flex;flex-direction:column;">
  <header style="display:flex;align-items:center;gap:16px;padding:15px 22px;border-bottom:1px solid {T.BORDER};flex-shrink:0;">
    <div style="display:flex;align-items:center;gap:11px;min-width:0;">
      <div class="mono" style="width:36px;height:36px;border-radius:10px;background:{T.ACCENT};display:flex;align-items:center;justify-content:center;color:{T.BG};font-weight:800;font-size:14px;flex-shrink:0;">AI</div>
      <div style="min-width:0;"><div class="hd-title" style="font-size:17px;font-weight:700;letter-spacing:-0.015em;">승무패 {r.round_no}회차 · AI 최종 분석</div>
        <div class="hd-meta" style="font-size:12px;color:{T.TEXT_MUTED};margin-top:2px;">발매 마감 {r.sale_close.strftime('%m-%d %H:%M')} · 데이터 {r.collected_at.strftime('%m-%d %H:%M')} 기준 · <a href="../../index.html">전체 회차</a></div></div>
    </div>
    <div style="margin-left:auto;display:flex;align-items:center;gap:14px;flex-shrink:0;">
      <div class="hd-legend" style="display:flex;align-items:center;gap:12px;font-size:11px;color:{T.TEXT_MUTED};">{legend}</div>
      {round_link}
      <span class="mono" style="font-size:12px;font-weight:600;color:{T.ACCENT};background:rgba(199,249,78,0.10);border:1px solid rgba(199,249,78,0.22);padding:5px 12px;border-radius:999px;">{status_pill}</span>
    </div>
  </header>
{mix_bar}  <div style="flex:1;display:flex;min-height:0;">
    <aside id="aside" style="display:flex;flex-direction:column;width:400px;flex-shrink:0;border-right:1px solid {T.BORDER};min-height:0;">
      <div class="mono" style="padding:14px 18px 10px;font-size:11px;letter-spacing:0.16em;text-transform:uppercase;color:{T.TEXT_FAINT};font-weight:600;flex-shrink:0;">경기 리스트 · 14</div>
      <div id="list" style="flex:1;overflow-y:auto;"></div>
    </aside>
    <main style="display:flex;flex-direction:column;flex:1;overflow-y:auto;min-height:0;">
      <div id="detail" style="padding:26px 32px 64px;max-width:780px;width:100%;"></div>
    </main>
  </div>
</div>
<script>const C={c_json};const DATA={data_json};const MIX={mix_json};{ROUND_JS}{MIX_JS}</script>"""

    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(
        T.shell(f"승무패 {r.round_no}회차 · AI 분석", body, round_css), encoding="utf-8")

    for m in r.matches:
        build_match_report_page(m, key, out_dir)
    build_round_report_page(r, key, out_dir)


# ── 마크다운 리포트 페이지 (다크) ────────────────────────────────
ARTICLE_CSS = f"""
.wrap{{max-width:820px;margin:0 auto;padding:40px 24px 80px;}}
.back{{display:inline-flex;gap:6px;font-size:13px;color:{T.TEXT_MUTED};margin-bottom:20px;font-weight:500;}}
article h1{{font-size:26px;font-weight:700;letter-spacing:-0.02em;margin:24px 0 12px;}}
article h2{{font-size:20px;font-weight:700;margin:28px 0 8px;letter-spacing:-0.01em;}}
article h3{{font-size:16px;font-weight:600;margin:20px 0 8px;color:{T.TEXT_DIM};}}
article p,article li{{font-size:15px;line-height:1.75;color:{T.TEXT_DIM};margin-bottom:8px;}}
article ul,article ol{{padding-left:22px;}}
article strong{{color:{T.TEXT};font-weight:600;}}
article a{{color:{T.ACCENT};}}
article hr{{border:none;border-top:1px solid {T.BORDER};margin:24px 0;}}
article em{{color:{T.TEXT_MUTED};font-style:normal;}}
.tablewrap{{overflow-x:auto;margin:14px 0;}}
article table{{border-collapse:collapse;width:100%;font-size:13px;}}
article th,article td{{border-bottom:1px solid {T.BORDER};padding:10px 12px;text-align:left;}}
article th{{color:{T.TEXT_MUTED};font-weight:600;}}
article td{{font-variant-numeric:tabular-nums;color:{T.TEXT_DIM};}}
.foot{{margin-top:40px;padding-top:16px;border-top:1px solid {T.BORDER};font-size:12px;color:{T.TEXT_FAINT};}}
"""


def render_markdown(md_text: str) -> str:
    text = JSON_BLOCK.sub("", md_text)
    drop = ("본 분석은 통계적 참고 자료", "📊 bkit", "✅ Used", "✅ 사용", "⏭️", "⏭ ",
            "💡 Recommended", "💡 추천")
    text = "\n".join(ln for ln in text.splitlines()
                     if not any(d in ln for d in drop) and set(ln.strip()) != {"─"})
    text = re.sub(r"(\n---\s*)+$", "", text.rstrip())
    html = markdown(text, extensions=["tables", "fenced_code"])
    return html.replace("<table>", '<div class="tablewrap"><table>').replace("</table>", "</table></div>")


def build_match_report_page(m: Match, key: str, out_dir: Path):
    report = REPORTS_DIR / key / f"M{m.match_no:02d}.md"
    if not report.exists():
        return
    body = f"""<div class="wrap">
<a class="back" href="index.html">← 회차로 돌아가기</a>
<article>{render_markdown(report.read_text(encoding="utf-8"))}</article>
<div class="foot">{T.DISCLAIMER}</div></div>"""
    (out_dir / f"m{m.match_no:02d}.html").write_text(
        T.shell(f"{m.home.betman_name} vs {m.away.betman_name} · AI 분석", body, ARTICLE_CSS),
        encoding="utf-8")


def build_round_report_page(r: Round, key: str, out_dir: Path):
    report = REPORTS_DIR / key / "round.md"
    if not report.exists():
        return
    body = f"""<div class="wrap">
<a class="back" href="index.html">← 경기 카드 보기</a>
<article>{render_markdown(report.read_text(encoding="utf-8"))}</article>
<div class="foot">{T.DISCLAIMER}</div></div>"""
    (out_dir / "round.html").write_text(
        T.shell(f"승무패 {r.round_no}회차 종합 리포트", body, ARTICLE_CSS), encoding="utf-8")


# ── 아카이브 인덱스 (다크) ──────────────────────────────────────
INDEX_CSS = f"""
.wrap{{max-width:820px;margin:0 auto;padding:56px 24px 80px;}}
.hero h1{{font-size:30px;font-weight:700;letter-spacing:-0.02em;display:flex;align-items:center;gap:12px;margin:0;}}
.logo{{width:38px;height:38px;border-radius:10px;background:{T.ACCENT};color:{T.BG};display:flex;align-items:center;justify-content:center;font-weight:800;font-size:15px;}}
.hero p{{color:{T.TEXT_MUTED};margin:10px 0 0;font-size:14px;}}
.list{{margin-top:36px;display:flex;flex-direction:column;gap:12px;}}
.row{{display:flex;align-items:center;gap:14px;background:{T.SURFACE};border:1px solid {T.BORDER_SOFT};border-radius:14px;padding:18px 22px;transition:background 120ms ease;}}
.row:hover{{background:{T.SURFACE_RAISED};}}
.rno{{font-size:19px;font-weight:700;letter-spacing:-0.01em;color:{T.TEXT};}}
.meta{{margin-left:auto;text-align:right;font-size:12px;color:{T.TEXT_MUTED};line-height:1.6;}}
.pill{{display:inline-block;font-size:12px;padding:3px 11px;border-radius:999px;font-weight:600;}}
.pill.done{{color:{T.ACCENT};background:rgba(199,249,78,0.10);border:1px solid rgba(199,249,78,0.22);}}
.pill.prog{{color:{T.DRAW};background:rgba(245,196,81,0.10);border:1px solid rgba(245,196,81,0.22);}}
.pill.wait{{color:{T.TEXT_MUTED};border:1px solid {T.BORDER};}}
.foot{{margin-top:48px;font-size:12px;color:{T.TEXT_FAINT};}}
"""


def build_index(rounds: list[Round]):
    rows = []
    for r in sorted(rounds, key=lambda x: (x.year, x.round_no), reverse=True):
        key = f"{r.year}-{r.round_no}"
        summaries, has_round = load_summaries(key)
        if has_round:
            pill = '<span class="pill done">분석 완료</span>'
        elif summaries:
            pill = '<span class="pill prog">분석 진행 중</span>'
        else:
            pill = '<span class="pill wait">분석 예정</span>'
        rows.append(
            f'<a class="row" href="rounds/{key}/index.html">'
            f'<span class="rno">{r.round_no}회차</span>{pill}'
            f'<span class="meta">{r.year}년 · 축구 {len(r.matches)}경기<br>'
            f'<span class="num">마감 {r.sale_close.strftime("%m-%d %H:%M")}</span></span></a>')
    body = f"""<div class="wrap">
<div class="hero"><h1><span class="logo mono">AI</span>승무패 · AI 최종 분석</h1>
<p>회차별 경기 정보와 마감 12시간 전 AI 분석 리포트</p></div>
<div class="list">{"".join(rows) or '<div style="color:#7A8394;">아직 수집된 회차가 없습니다.</div>'}</div>
<div class="foot">{T.DISCLAIMER}</div></div>"""
    SITE_DIR.mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "index.html").write_text(T.shell("승무패 AI 분석", body, INDEX_CSS), encoding="utf-8")


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
