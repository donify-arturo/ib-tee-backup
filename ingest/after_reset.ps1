# Waits for the 5-hour window to reset, builds Foundations for every sub-topic that hasn't got them, then fills the missing decks.
# One copy only: check nothing else is building first. Safe to stop (Ctrl-C) and rerun: finished work is skipped.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File ingest\after_reset.ps1 [-StartUtc "2026-11-06T00:42:00"]
param([string]$StartUtc = "", [double]$DeckBudget = 5)
Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONUTF8 = '1'; $env:PYTHONPATH = (Get-Location).Path
$py = ".\.venv\Scripts\python.exe"
Get-ChildItem Env: | Where-Object { $_.Name -match '^(ANTHROPIC|CLAUDE)' } | ForEach-Object { Remove-Item "Env:$($_.Name)" -ErrorAction SilentlyContinue }
$env:PATH = "$env:USERPROFILE\.local\bin;$env:PATH"
$log = "data\reports\foundations_all_20261106.log"

if ($StartUtc) {
    $wait = ([DateTime]::Parse($StartUtc) - [DateTime]::UtcNow).TotalSeconds
    if ($wait -gt 0) { "waiting until $StartUtc UTC for the usage window to reset"; Start-Sleep -Seconds ([int]$wait) }
}

$codes = "R1.3", "R1.4", "R2.1", "R2.2", "R2.3", "R3.1", "R3.2", "R3.3", "R3.4", "S1.1", "S1.2", "S1.3", "S1.4", "S1.5",
         "S2.1", "S2.2", "S2.3", "S2.4", "S3.1", "S3.2"
for ($try = 0; $try -lt 12; $try++) {
    "=== Foundations " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    & $py -m engine.foundations_builder @codes 2>&1 | Tee-Object -FilePath $log -Append
    if ($LASTEXITCODE -ne 3) { break }               # 3 = the plan's usage limit: wait and continue where it stopped
    "limit reached; trying again in 30 minutes"
    Start-Sleep -Seconds 1800
}

"=== Decks " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
& powershell -NoProfile -ExecutionPolicy Bypass -File ingest\fill_decks.ps1 -FirstBudget $DeckBudget 2>&1 | Tee-Object -FilePath data\reports\fill_decks_20261106.log -Append
"ALL DONE " + (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
