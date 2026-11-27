param(
  [string]$Pesan = "Update aplikasi konsinyasi Tenan"
)

# Jalankan dari folder proyek:
#   powershell -ExecutionPolicy Bypass -File .\sync-github.ps1 -Pesan "Perbaikan popup edit Tenan"

git add -A

$adaPerubahan = git diff --cached --name-only
if (-not $adaPerubahan) {
  Write-Host "Tidak ada perubahan untuk di-commit."
} else {
  git commit -m $Pesan
}

if (git remote | Select-String -SimpleMatch "origin") {
  git push origin HEAD
  Write-Host "Sinkron ke GitHub selesai."
} else {
  Write-Host "Remote 'origin' belum ada. Tambahkan dengan: git remote add origin <URL_REPO_GITHUB>"
}
