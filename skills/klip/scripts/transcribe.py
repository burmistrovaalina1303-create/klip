#!/usr/bin/env python3
"""Кліп: розшифровка довгого відео в слова з таймінгами.

python3 transcribe.py <відео> [--out папка] [--lang uk|ru|en|auto]
Результат у папці: words.json (кожне слово з часом) і transcript.txt (речення з таймкодами — для Claude).
Працює локально через whisper.cpp (whisper-cli), нічого не відправляє в інтернет.
"""
import json, os, re, shutil, subprocess, sys, argparse
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # Windows-консоль не ламається на кирилиці
except Exception: pass

HOME = os.path.expanduser('~/.klip')
WHISPER = shutil.which('whisper-cli') or next((p for p in [os.path.join(HOME, 'bin', 'whisper-cli.exe'), os.path.join(HOME, 'bin', 'whisper-cli')] if os.path.exists(p)), 'whisper-cli')
MODEL = os.environ.get('KLIP_MODEL') or next((os.path.join(d, f) for d in [os.path.join(HOME, 'models'), os.path.expanduser('~/whisper-models')]
                                             if os.path.isdir(d) for f in sorted(os.listdir(d)) if f.startswith('ggml-') and f.endswith('.bin')), None)


def ts(sec):
    m, s = divmod(sec, 60); h, m = divmod(int(m), 60)
    return f'{h}:{m:02d}:{s:04.1f}' if h else f'{m:02d}:{s:04.1f}'


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('--out', default=None); ap.add_argument('--lang', default='auto')
    a = ap.parse_args()
    if not MODEL: sys.exit('Немає моделі whisper. Запусти scripts/setup.sh (Mac) або scripts/setup.ps1 (Windows)')
    out = a.out or os.path.splitext(a.video)[0] + '-klip'; os.makedirs(out, exist_ok=True)
    wav = os.path.join(out, 'audio16k.wav')
    print('1/2 витягую звук…', flush=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', a.video, '-vn', '-ac', '1', '-ar', '16000', wav], check=True)
    print('2/2 розшифровую мову (на довгому відео це кілька хвилин)…', flush=True)
    base = os.path.join(out, 'whisper')
    cmd = [WHISPER, '-m', MODEL, '-f', wav, '-l', a.lang, '-ml', '1', '-sow', '-oj', '-of', base, '-np']
    r = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if r.returncode != 0:   # відеокарта не підійшла — рахую на процесорі (повільніше, але завжди працює)
        print('   (рахую на процесорі)', flush=True)
        subprocess.run(cmd + ['-ng'], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    raw = json.load(open(base + '.json', encoding='utf-8'))
    words = []
    for seg in raw.get('transcription', []):
        w = seg['text'].strip()
        if not w or w.startswith('['): continue
        s, e = seg['offsets']['from'] / 1000, seg['offsets']['to'] / 1000
        if words and not re.match(r'^[\w«"(]', w):   # розділові знаки приклеюю до попереднього слова
            words[-1]['w'] += w; words[-1]['e'] = e; continue
        words.append({'w': w, 's': round(s, 2), 'e': round(e, 2)})
    json.dump(words, open(os.path.join(out, 'words.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    # речення для читання: розрив на . ! ? або паузі > 0.8 с
    lines, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        gap = words[i + 1]['s'] - w['e'] if i + 1 < len(words) else 9
        if re.search(r'[.!?…]$', w['w']) or gap > 0.8 or len(cur) > 28:
            lines.append(f'[{ts(cur[0]["s"])}–{ts(cur[-1]["e"])}] ' + ' '.join(x['w'] for x in cur)); cur = []
    open(os.path.join(out, 'transcript.txt'), 'w', encoding='utf-8').write('\n'.join(lines) + '\n')
    os.remove(wav)
    dur = words[-1]['e'] if words else 0
    print(f'Готово: {len(words)} слів, {ts(dur)} мови → {out}/transcript.txt')


if __name__ == '__main__': main()
