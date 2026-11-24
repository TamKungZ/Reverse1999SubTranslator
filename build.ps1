$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Get-Process R1999Translator, r1999-engine -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --noconsole --name r1999-engine `
    --paths engine `
    --collect-all rapidocr_onnxruntime --collect-all ctranslate2 --collect-all sentencepiece `
    --collect-data pythainlp `
    --add-data "engine\r1999engine\data;r1999engine\data" `
    engine\run_engine.py

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --noconsole --name R1999Translator `
    --paths ui `
    --add-data "ui\r1999ui\assets;r1999ui\assets" `
    --add-data "ui\r1999ui\locales;r1999ui\locales" `
    ui\run_ui.py

$target = "dist\R1999Translator\engine"
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Copy-Item dist\r1999-engine $target -Recurse
Write-Host "Done: dist\R1999Translator\R1999Translator.exe"
