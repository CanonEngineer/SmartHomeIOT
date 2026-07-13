# SmartHome IoT — start no Windows (PowerShell)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$Root\python_server"

if (-not (Test-Path ".venv")) {
  Write-Host "Criando ambiente virtual..."
  python -m venv .venv
}

Write-Host "Ativando venv e instalando dependencias..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt

Write-Host ""
Write-Host "Servidor em http://127.0.0.1:8000"
Write-Host "Abra o navegador e use o simulador visual."
Write-Host ""
& .\.venv\Scripts\python.exe app.py
