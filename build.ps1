param([switch]$SkipInstaller)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Get-Process R1999Translator, r1999-engine -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Seconds 1

if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.22.3

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --noconsole --name r1999-engine `
    --icon ui\r1999ui\assets\icon.ico `
    --paths engine `
    --collect-all rapidocr_onnxruntime --collect-all ctranslate2 --collect-all sentencepiece `
    --collect-data pythainlp `
    --add-data "engine\r1999engine\data;r1999engine\data" `
    engine\run_engine.py

$fontArgs = @()
if (Test-Path ui\r1999ui\fonts) {
    $fontArgs = @("--add-data", "ui\r1999ui\fonts;r1999ui\fonts")
} else {
    Write-Warning "ui\r1999ui\fonts is missing, so no font is bundled and Thai text uses a system font."
}

& .\.venv\Scripts\pyinstaller.exe --noconfirm --clean --noconsole --name R1999Translator `
    --icon ui\r1999ui\assets\icon.ico `
    --paths ui `
    --add-data "ui\r1999ui\assets;r1999ui\assets" `
    --add-data "ui\r1999ui\locales;r1999ui\locales" `
    @fontArgs `
    ui\run_ui.py

$target = "dist\R1999Translator\engine"
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Copy-Item dist\r1999-engine $target -Recurse
Write-Host "Done: dist\R1999Translator\R1999Translator.exe"

if ($SkipInstaller) { return }
$makensis = (Get-Command makensis -ErrorAction SilentlyContinue).Source
if (-not $makensis) {
    $makensis = @("${env:ProgramFiles(x86)}\NSIS\makensis.exe", "$env:ProgramFiles\NSIS\makensis.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $makensis) {
    Write-Warning "NSIS was not found, the installer was skipped. Install NSIS 3 or pass -SkipInstaller."
    return
}
$version = (Select-String -Path engine\r1999engine\__init__.py -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
& $makensis /V2 "/DVERSION=$version" installer\R1999Translator.nsi
if ($LASTEXITCODE -ne 0) { throw "makensis failed" }
Write-Host "Done: dist\R1999Translator-Setup-$version.exe"
