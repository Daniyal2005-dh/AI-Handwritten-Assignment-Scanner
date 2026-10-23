# Starts the scanner server + a public HTTPS tunnel, then prints and QRs the URL.
# Anything run from this project folder:  powershell -File scripts\start_public.ps1
$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = "$root\.venv\Scripts\python.exe"
$cloudflared = "$root\tools\cloudflared.exe"

Write-Host "Starting scanner server on 0.0.0.0:8000 ..."
$server = Start-Process -FilePath $py -ArgumentList "-m","uvicorn","backend.app:app","--host","0.0.0.0","--port","8000" -WorkingDirectory $root -PassThru -WindowStyle Hidden

Write-Host "Opening public tunnel (Cloudflare quick tunnel, no account needed) ..."
$tunnel = Start-Process -FilePath $cloudflared -ArgumentList "tunnel","--url","http://localhost:8000","--protocol","http2" -PassThru -WindowStyle Hidden -RedirectStandardOutput "$root\tools\tunnel.out" -RedirectStandardError "$root\tools\tunnel.err"

$url = $null
for ($i = 0; $i -lt 60 -and -not $url; $i++) {
    Start-Sleep 2
    if (Test-Path "$root\tools\tunnel.err") { $url = (Select-String -Path "$root\tools\tunnel.err" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1).Matches.Value; break }
    if (Test-Path "$root\tools\tunnel.out") { $url = (Select-String -Path "$root\tools\tunnel.out" -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -First 1).Matches.Value }
}

if ($url) {
    & $py -c "import qrcode; qrcode.make('$url').save('$root\tools\public-url-qr.png')"
    Write-Host ""
    Write-Host "============================================================"
    Write-Host " PUBLIC URL (use in any browser, any device, anywhere):"
    Write-Host "   $url"
    Write-Host " QR code saved at tools\public-url-qr.png"
    Write-Host " Local URL: http://localhost:8000"
    Write-Host " Keep this window open. Close to take the site offline."
    Write-Host "============================================================"
    Write-Host ""
} else {
    Write-Host "Tunnel did not come up yet; check tools\tunnel.err — retry later or rerun the script."
}

Read-Host "Press ENTER to stop both server and tunnel"
if ($server) Stop-Process -Id $server.Id -Force -ErrorAction SilentlyContinue
if ($tunnel) Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
