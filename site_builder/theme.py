"""다크 네온 테마 토큰·공통 셸 (Claude Design 'Round Analysis' 참조).

design_teq.md(아이보리)의 후속 디자인 방향. 색·폰트·형태를 여기 한곳에 모은다.
"""

# 색상 토큰
BG = "#0A0D12"
SURFACE = "#12161F"
SURFACE_RAISED = "#141926"
BORDER = "rgba(255,255,255,0.07)"
BORDER_SOFT = "rgba(255,255,255,0.06)"
TEXT = "#E8ECF2"
TEXT_DIM = "#B4BCC8"
TEXT_MUTED = "#7A8394"
TEXT_FAINT = "#5D6675"
ACCENT = "#C7F94E"          # 네온 라임
WIN = "#2EE6A6"            # 승 · 홈
DRAW = "#F5C451"           # 무
LOSE = "#FF5D6C"           # 패 · 원정

FONTS_HEAD = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">'
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" '
    'rel="stylesheet">'
)

BASE_CSS = f"""
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;}}
body{{background:{BG};color:{TEXT};font-family:'Pretendard',system-ui,-apple-system,sans-serif;
  -webkit-font-smoothing:antialiased;}}
::selection{{background:{ACCENT};color:{BG};}}
a{{color:{ACCENT};text-decoration:none;}}
a:hover{{color:#dcff86;}}
.mono{{font-family:'Space Grotesk',sans-serif;}}
.num{{font-family:'Space Grotesk',sans-serif;font-variant-numeric:tabular-nums;}}
::-webkit-scrollbar{{width:9px;height:9px;}}
::-webkit-scrollbar-thumb{{background:rgba(255,255,255,0.11);border-radius:9px;}}
::-webkit-scrollbar-thumb:hover{{background:rgba(255,255,255,0.2);}}
::-webkit-scrollbar-track{{background:transparent;}}
@media (prefers-reduced-motion:reduce){{*{{transition:none!important;}}}}
"""

DISCLAIMER = "본 분석은 통계적 참고 자료이며 구매 결과를 보장하지 않습니다."


def shell(title: str, body: str, extra_css: str = "") -> str:
    return (
        '<!doctype html><html lang="ko"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex">'
        f"<title>{title}</title>{FONTS_HEAD}"
        f"<style>{BASE_CSS}{extra_css}</style></head><body>{body}</body></html>"
    )
