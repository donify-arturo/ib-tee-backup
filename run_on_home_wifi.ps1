# Opens IB TEE to your phone or tablet, only on a Wi-Fi you have confirmed is your home network. Anywhere else it stays on this computer.
# Started by "Open IB TEE on home Wi-Fi.bat". The -Simulated options and -DryRun are for testing: nothing is started or saved with -DryRun.
param([string]$SimulatedNetwork = "", [string]$SimulatedAnswer = "", [switch]$DryRun)

Set-Location $PSScriptRoot
$trustedFile = "data\trusted_wifi.txt"
$port = 8501
$streamlit = ".venv\Scripts\streamlit.exe"

$network = $SimulatedNetwork
$ip = "192.0.2.1"
if (-not $SimulatedNetwork) {
    $config = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq "Up" } | Select-Object -First 1
    if ($config) {
        $network = (Get-NetConnectionProfile -InterfaceIndex $config.InterfaceIndex | Select-Object -First 1).Name
        $ip = $config.IPv4Address.IPAddress
    }
}

$trusted = @()
if (Test-Path $trustedFile) { $trusted = @(Get-Content $trustedFile -Encoding UTF8 | Where-Object { $_.Trim() }) }

$open = $false
if (-not $network) {
    Write-Host "No network found."
} elseif ($network -match "school|college|campus|university|eduroam|guest|public|cafe|hotel|airport") {
    Write-Host "'$network' does not look like a private home network, so IB TEE stays on this computer."
} elseif ($trusted -contains $network) {
    $open = $true
} else {
    Write-Host ""
    Write-Host "You are connected to: $network"
    Write-Host "Everyone on this Wi-Fi will be able to open IB TEE, your books and your progress, with no password."
    $answer = $SimulatedAnswer
    if (-not $SimulatedAnswer) { $answer = Read-Host "Is this your own home Wi-Fi? Type yes or no" }
    if ($answer.Trim().ToLower() -eq "yes") {
        $open = $true
        if (-not $DryRun) { Add-Content -Path $trustedFile -Value $network -Encoding UTF8 }
    }
}

if ($DryRun) { Write-Host "RESULT network='$network' open=$open"; return }

if ($open) {
    Write-Host ""
    Write-Host "On your phone or tablet, connected to '$network', open:"
    Write-Host ""
    Write-Host "    http://${ip}:$port"
    Write-Host ""
    Write-Host "If Windows asks about network access for Python, choose Allow."
    Write-Host "Keep this window open while you study. Close it to stop."
    Write-Host ""
    & $streamlit run app.py --server.headless true --server.port $port --server.address 0.0.0.0
} else {
    Write-Host "Opening IB TEE on this computer only."
    & $streamlit run app.py --server.port $port
}
