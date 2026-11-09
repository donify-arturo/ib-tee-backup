# Build every missing deck on the Pro plan, highest exam priority first, without using up the 5-hour limit.
# Safe to stop and rerun: finished decks are skipped. Each 5-hour window gets a spending budget; then it waits for the next window.
# Usage: powershell -File ingest\fill_decks.ps1 [-FirstBudget 1.5] [-FirstWindowEndsUtc "2026-11-04T23:21:00"]
param([double]$FirstBudget = 7.5, [string]$FirstWindowEndsUtc = "")
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'; $env:PYTHONPATH = (Get-Location).Path
$py = ".\.venv\Scripts\python.exe"
Get-ChildItem Env: | Where-Object { $_.Name -match '^(ANTHROPIC|CLAUDE)' } | ForEach-Object { Remove-Item "Env:$($_.Name)" -ErrorAction SilentlyContinue }
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"

$order = "R3.2", "S1.5", "S2.2", "S2.1", "S3.2", "R2.1", "R3.4", "R2.2", "R1.3", "S2.4", "S1.1", "S2.3", "R3.3", "S1.4", "R1.4", "R2.3", "S3.1", "S1.3"
$WindowBudget = 7.5      # dollars-equivalent, about 75% of a 5-hour window; the rest stays free for normal use
$budget = $FirstBudget
$spent = 0.0
if ($FirstWindowEndsUtc) { $windowEnd = [DateTime]::Parse($FirstWindowEndsUtc) } else { $windowEnd = [DateTime]::UtcNow.AddHours(5).AddMinutes(2) }

function Wait-Window {
    $wait = ($windowEnd - [DateTime]::UtcNow).TotalSeconds
    if ($wait -gt 0) {
        "waiting until $($windowEnd.ToString('HH:mm')) UTC for the next 5-hour window"
        Start-Sleep -Seconds ([int]$wait)
    }
    $script:spent = 0.0
    $script:budget = $WindowBudget
    $script:windowEnd = [DateTime]::UtcNow.AddHours(5).AddMinutes(2)
}

foreach ($code in $order) {
    if (Test-Path "data\techniques\$code.json") { "skip $code`: deck exists"; continue }
    if ($spent -ge $budget) { Wait-Window }
    $tries = 0
    while ($true) {
        "=== $code started " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        & $py -m engine.technique_engine $code --allow-partial --backend claude-cli --model opus 2>&1 | Select-Object -Last 4 | ForEach-Object { $s = "$_"; if ($s.Length -gt 300) { $s.Substring(0, 300) } else { $s } }
        $code_exit = $LASTEXITCODE
        if ($code_exit -ne 3) { break }                    # 3 = the plan's usage limit
        $tries++
        if ($tries -ge 12) { "giving up on $code after repeated limit stops; rerun later"; exit 3 }
        "limit reached; trying again in 30 minutes"
        Start-Sleep -Seconds 1800
    }
    if ($code_exit -eq 0) { & $py -m analysis.render_cards $code | Out-Null } else { "FAILED $code (exit $code_exit); moving on" }
    $last = Get-Content data\reports\engine_log.jsonl -Tail 1 -Encoding utf8 | ConvertFrom-Json
    if ($last.sub_topic -eq $code -and $last.cost_usd_equivalent) { $spent += [double]$last.cost_usd_equivalent }
    "$code exit $code_exit; window spend $([math]::Round($spent, 2)) of $budget; " + (Get-Date -Format "HH:mm:ss")
}
"ALL DONE " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
