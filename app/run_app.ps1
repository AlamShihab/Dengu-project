# Dengue Forecasting System - web app (http://127.0.0.1:5001)
Set-Location -Path $PSScriptRoot
$py = Join-Path $PSScriptRoot "..\pipeline\.venv\Scripts\python.exe"
if (-not (Test-Path $py)) { Write-Error "Python environment not found: $py"; exit 1 }
Start-Process "http://127.0.0.1:5001"
& $py app.py
