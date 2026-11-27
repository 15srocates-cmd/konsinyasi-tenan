# Menjalankan aplikasi Konsinyasi Tenan + Cloudflare Tunnel.
# URL internet sementara akan tampil di jendela cloudflared.
# Tutup jendela tersebut untuk menghentikan tunnel.

$web = Join-Path $PSScriptRoot "web"

# Hentikan Flask/tunnel lama supaya tidak ada beberapa proses di port 5000.
$flaskLama = Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
  Where-Object { $_.CommandLine -match '\bapp\.py$' -and $_.CommandLine -notmatch 'streamlit' }
foreach ($p in $flaskLama) {
  Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
}
Get-CimInstance Win32_Process -Filter "Name = 'cloudflared.exe'" | ForEach-Object {
  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
}
if ($flaskLama) { Start-Sleep -Seconds 2 }

Write-Host "Menjalankan Flask di http://127.0.0.1:5000 ..."
Start-Process -FilePath "python" -ArgumentList "app.py" -WorkingDirectory $web
Start-Sleep -Seconds 2

$cf = Get-Command cloudflared -ErrorAction SilentlyContinue
if (-not $cf) {
  $kandidat = @(
    "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe",
    "$env:ProgramFiles\cloudflared\cloudflared.exe"
  ) | Where-Object { Test-Path $_ } | Select-Object -First 1
  if ($kandidat) {
    $cf = @{ Source = $kandidat }
  } else {
    Write-Host "cloudflared belum terpasang. Pasang dengan: winget install Cloudflare.cloudflared"
    exit 1
  }
}

Write-Host "Membuka Cloudflare Tunnel..."
Write-Host "Lihat jendela cloudflared untuk URL https://xxxx.trycloudflare.com"
Start-Process -FilePath $cf.Source -ArgumentList "tunnel --url http://127.0.0.1:5000"
