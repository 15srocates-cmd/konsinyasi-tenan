#!/usr/bin/env bash
# Jalankan di Bash console PythonAnywhere setelah saya push perubahan ke GitHub.
# Mengambil source terbaru lalu menyentuh wsgi.py agar PythonAnywhere reload.
set -e

cd "$(dirname "$0")"
git pull origin main
touch web/wsgi.py

echo "Source terbaru sudah di-pull. Web app PythonAnywhere akan di-reload."
