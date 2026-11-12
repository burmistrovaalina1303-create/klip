#!/usr/bin/env python3
"""Кліп: нарізка вертикальних кліпів 9:16 з великими субтитрами.

python3 cut.py <відео> <clips.json> [--words words.json] [--out папка] [--mode blur|crop] [--color "#FFD23F"]
clips.json — список від Claude: [{"start": 125.4, "end": 171.0, "hook": "Він не знав, що камера ввімкнена",
                                   "title": "...", "description": "...", "hashtags": ["#..."]}]
На виході: clip-01.mp4 … і clip-01.txt з назвою, описом і хештегами.
"""
import json, os, re, subprocess, sys, argparse, shutil, tempfile
try: sys.stdout.reconfigure(encoding='utf-8', errors='replace')   # Windows-консоль не ламається на кирилиці
except Exception: pass
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONTS = ['/System/Library/Fonts/Supplemental/Arial Black.ttf', '/System/Library/Fonts/Supplemental/Arial Bold.ttf',
         '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'C:/Windows/Fonts/ariblk.ttf', 'C:/Windows/Fonts/arialbd.ttf']
FONT = next((f for f in FONTS if os.path.exists(f)), None)


def font(size): return ImageFont.truetype(FONT, size) if FONT else ImageFont.load_default()


def chunks(words):
    out, cur = [], []
    for w in words:
        if cur and (len(' '.join(x['w'] for x in cur + [w])) > 18 or len(cur) >= 3 or w['s'] - cur[-1]['e'] > 0.6):
            out.append(cur); cur = []
        cur.append(w)
        if re.search(r'[.!?…,]$', w['w']): out.append(cur); cur = []
    if cur: out.append(cur)
    return out


def caption_png(words, hi, path, color):
    """Кадр субтитру 1080x420 з прозорим фоном: поточне слово кольором, решта білі, жирний чорний контур."""
    img = Image.new('RGBA', (W, 420), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    text = [w['w'].upper() for w in words]
    size = 92
    while size > 40:
        f = font(size); sp = d.textlength(' ', font=f)
        total = sum(d.textlength(t, font=f) for t in text) + sp * (len(text) - 1)
        if total <= W - 100: break
        size -= 4
    x = (W - total) / 2; y = 210 - size / 2
    for i, t in enumerate(text):
        d.text((x, y), t, font=f, fill=color if i == hi else '#FFFFFF', stroke_width=max(6, size // 11), stroke_fill='#000000')
        x += d.textlength(t, font=f) + sp
    img.save(path)


def hook_png(text, path):
    img = Image.new('RGBA', (W, 520), (0, 0, 0, 0)); d = ImageDraw.Draw(img)
    words, lines, size = text.upper().split(), [], 78
    f = font(size)
    for w in words:
        if lines and d.textlength(lines[-1] + ' ' + w, font=f) < W - 160: lines[-1] += ' ' + w
        else: lines.append(w)
    y = 260 - len(lines) * (size + 14) / 2
    for ln in lines:
        tw = d.textlength(ln, font=f); x = (W - tw) / 2
        d.rounded_rectangle((x - 26, y - 10, x + tw + 26, y + size + 18), radius=22, fill='#FFFFFF')
        d.text((x, y), ln, font=f, fill='#111111'); y += size + 30
    img.save(path)


def captions_track(words, dur, tmp, color):
    """Субтитри однією прозорою доріжкою (.mov з альфою) — швидко навіть на хвилинних кліпах."""
    blank = os.path.join(tmp, 'blank.png'); Image.new('RGBA', (W, 420), (0, 0, 0, 0)).save(blank)
    seq, t, n = [], 0.0, 0
    for ch in chunks(words):
        for i, w in enumerate(ch):
            s = max(w['s'], t); e = ch[i + 1]['s'] if i + 1 < len(ch) else w['e'] + 0.15
            if s - t > 0.02: seq.append((blank, s - t))
            if e - s > 0.02:
                p = os.path.join(tmp, f'c{n:04d}.png'); caption_png(ch, i, p, color); seq.append((p, e - s)); n += 1
            t = max(t, e)
    if dur - t > 0.02: seq.append((blank, dur - t))
    lst = os.path.join(tmp, 'caps.txt')
    fwd = lambda q: q.replace(os.sep, '/')   # Windows: ffmpeg concat любить прямі слеші
    with open(lst, 'w', encoding='utf-8') as fh:
        for p, d in seq: fh.write(f"file '{fwd(p)}'\nduration {d:.3f}\n")
        fh.write(f"file '{fwd(seq[-1][0])}'\n")
    out = os.path.join(tmp, 'caps.mov')
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', lst, '-vf', 'fps=30,format=rgba',
                    '-c:v', 'qtrle', '-t', f'{dur:.3f}', out], check=True)
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('video'); ap.add_argument('clips')
    ap.add_argument('--words'); ap.add_argument('--out'); ap.add_argument('--mode', default='blur'); ap.add_argument('--color', default='#FFD23F')
    a = ap.parse_args()
    clips = json.load(open(a.clips, encoding='utf-8'))
    wpath = a.words or os.path.join(os.path.dirname(os.path.abspath(a.clips)), 'words.json')
    allw = json.load(open(wpath, encoding='utf-8'))
    out = a.out or os.path.dirname(os.path.abspath(a.clips)); os.makedirs(out, exist_ok=True)
    for k, c in enumerate(clips, 1):
        s, e = float(c['start']), float(c['end']); dur = e - s
        ws = [{'w': w['w'], 's': w['s'] - s, 'e': min(w['e'], e) - s} for w in allw if w['s'] >= s - 0.05 and w['s'] < e]
        tmp = tempfile.mkdtemp(prefix='klip-')
        try:
            caps = captions_track(ws, dur, tmp, a.color)
            hook = os.path.join(tmp, 'hook.png'); hook_png(c.get('hook') or c.get('title', ''), hook)
            if a.mode == 'crop':
                base = f'[0:v]scale=-2:{H},crop={W}:{H}[bg]'
            else:
                base = (f'[0:v]split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:2,eq=brightness=-0.15[bgb];'
                        f'[b]scale={W}:-2[fg];[bgb][fg]overlay=0:(H-h)/2[bg]')
            fc = (base + f';[bg][1:v]overlay=0:1250:shortest=1[v1];[v1][2:v]overlay=0:120:enable=\'lt(t,4)\'[v]')
            dst = os.path.join(out, f'clip-{k:02d}.mp4')
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', f'{s:.3f}', '-t', f'{dur:.3f}', '-i', a.video, '-i', caps, '-loop', '1', '-t', f'{dur:.3f}', '-i', hook,
                            '-filter_complex', fc, '-map', '[v]', '-map', '0:a?', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-b:a', '160k', '-r', '30', '-movflags', '+faststart', dst], check=True)
            info = f"{c.get('title', '')}\n\n{c.get('description', '')}\n\n{' '.join(c.get('hashtags', []))}\n"
            open(os.path.join(out, f'clip-{k:02d}.txt'), 'w', encoding='utf-8').write(info)
            print(f'✓ clip-{k:02d}.mp4  {dur:.0f} с  — {c.get("title", "")}', flush=True)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__': main()
