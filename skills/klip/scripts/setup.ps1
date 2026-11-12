# Кліп: одноразове встановлення для Windows 10/11.
# Ставить ffmpeg, yt-dlp, Python (якщо немає), whisper.cpp, бібліотеку для субтитрів і модель розпізнавання мови.
# Запуск: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Host "Встановлюю Кліп..."

$K = Join-Path $env:USERPROFILE ".klip"
$Bin = Join-Path $K "bin"; $Models = Join-Path $K "models"
New-Item -ItemType Directory -Force -Path $Bin, $Models | Out-Null

function Has($c) { $null -ne (Get-Command $c -ErrorAction SilentlyContinue) }
function Refresh-Path { $env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User") + ";" + $Bin }

if (-not (Has "winget")) { Write-Host "Потрібен winget (App Installer з Microsoft Store). Встанови його і запусти скрипт ще раз."; exit 1 }

if (-not (Has "ffmpeg")) { winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements }
if (-not (Has "yt-dlp")) { winget install --id yt-dlp.yt-dlp -e --accept-source-agreements --accept-package-agreements }
$Py = $null
foreach ($c in @("py","python")) { if (Has $c) { try { & $c -c "import sys; assert sys.version_info >= (3,9)" 2>$null; if ($LASTEXITCODE -eq 0) { $Py = $c; break } } catch {} } }
if (-not $Py) { winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements; Refresh-Path; $Py = "py" }
Refresh-Path

# whisper.cpp (готова збірка для Windows)
$WCli = Join-Path $Bin "whisper-cli.exe"
if (-not (Test-Path $WCli)) {
  Write-Host "Завантажую whisper.cpp..."
  $zip = Join-Path $K "whisper.zip"; $tmp = Join-Path $K "whisper-tmp"
  # Беремо найновіший реліз, де є готова збірка для Windows; якщо GitHub не відповів — перевірену версію
  $url = "https://github.com/ggml-org/whisper.cpp/releases/download/b5454/whisper-bin-x64.zip"
  try {
    $rel = Invoke-RestMethod -UseBasicParsing "https://api.github.com/repos/ggml-org/whisper.cpp/releases?per_page=10"
    $asset = $rel | ForEach-Object { $_.assets } | Where-Object { $_.name -eq "whisper-bin-x64.zip" } | Select-Object -First 1
    if ($asset) { $url = $asset.browser_download_url }
  } catch {}
  Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $zip
  Expand-Archive -Force $zip $tmp
  $exe = Get-ChildItem $tmp -Recurse -Filter "whisper-cli.exe" | Select-Object -First 1
  if (-not $exe) { Write-Host "Не знайшов whisper-cli.exe в архіві whisper.cpp."; exit 1 }
  Copy-Item (Join-Path $exe.DirectoryName "*") $Bin -Recurse -Force
  Remove-Item $zip, $tmp -Recurse -Force
}

# Python-середовище для субтитрів
$VPy = Join-Path $K "venv\Scripts\python.exe"
if (-not (Test-Path $VPy)) { & $Py -m venv (Join-Path $K "venv") }
& $VPy -m pip install -q --upgrade pillow

# Модель розпізнавання мови (~600 МБ)
$M = Join-Path $Models "ggml-large-v3-turbo-q5_0.bin"
if (-not (Test-Path $M)) {
  Write-Host "Завантажую модель розпізнавання мови (~600 МБ)..."
  $ProgressPreference = "SilentlyContinue"
  Invoke-WebRequest -UseBasicParsing -Uri "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin" -OutFile "$M.part"
  Move-Item "$M.part" $M -Force
}

Write-Host "Готово. Напиши Claude: «наріж це відео на кліпи» і дай файл або посилання."
