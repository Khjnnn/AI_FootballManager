# 로컬 분석 트리거 폴링 (plan.md 3절)
# Windows 작업 스케줄러에 10분 간격 등록:
#   schtasks /create /tn "afm-poll" /sc minute /mo 10 /tr "powershell -NoProfile -File C:\dev\ai_football_manager\scripts\local_poll.ps1"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

git fetch origin 2>$null
git pull --ff-only 2>$null

# 입력 패키지는 있으나 종합 리포트가 없는 회차 → 분석 실행
$env:PYTHONPATH = $root
$env:PYTHONIOENCODING = 'utf-8'
Get-ChildItem "$root\data\matches" -Directory -ErrorAction SilentlyContinue | ForEach-Object {
    $key = $_.Name
    if (-not (Test-Path "$root\data\reports\$key\round.md")) {
        Write-Output "[poll] 미분석 회차 발견: $key — 분석 시작"
        python -m analyzer.analyze --round $key
        if ($LASTEXITCODE -eq 0) {
            git add data/reports
            git commit -m "analyze: $key reports"
            git push
        }
    }
}
