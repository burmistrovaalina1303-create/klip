#!/bin/bash
# Кліп: одноразове встановлення (macOS). Ставить ffmpeg, whisper.cpp, yt-dlp, Python-бібліотеку для субтитрів і модель розпізнавання мови.
set -e
echo "🎬 Встановлюю Кліп…"
if ! command -v brew >/dev/null; then
  echo "Потрібен Homebrew. Встанови його з https://brew.sh і запусти цей скрипт ще раз."; exit 1
fi
for p in ffmpeg whisper-cpp yt-dlp; do
  brew list "$p" >/dev/null 2>&1 || brew install "$p"
done
mkdir -p ~/.klip/models
[ -x ~/.klip/venv/bin/python ] || python3 -m venv ~/.klip/venv
~/.klip/venv/bin/pip install -q --upgrade pillow
M=~/.klip/models/ggml-large-v3-turbo-q5_0.bin
if [ ! -f "$M" ]; then
  echo "⬇️  Завантажую модель розпізнавання мови (~600 МБ)…"
  curl -L --fail -o "$M.part" "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo-q5_0.bin" && mv "$M.part" "$M"
fi
echo "✅ Готово. Напиши Claude: «наріж це відео на кліпи» і дай файл або посилання."
