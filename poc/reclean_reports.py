"""생성된 리포트에서 bkit 상용구 푸터 재정리 (강화된 clean_report 적용)."""
from pathlib import Path

from analyzer.analyze import clean_report, DISCLAIMER

REPORTS = Path(__file__).parent.parent / "data" / "reports" / "2026-38"
for f in sorted(REPORTS.glob("*.md")):
    text = f.read_text(encoding="utf-8").replace(DISCLAIMER, "")
    cleaned = clean_report(text) + DISCLAIMER
    f.write_text(cleaned, encoding="utf-8")
    body = f.read_text(encoding="utf-8")
    flag = any(m in body for m in ("✅ Used", "⏭️", "💡 Recommended", "📊 bkit"))
    print(f"{f.name}: {'⚠️ 잔여' if flag else 'clean'}")
