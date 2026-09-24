import math
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'public' / 'static'
W, H, FPS, DURATION = 960, 540, 24, 18
SCENE = 6
FADE = 0.5
SANS = '/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf'
SERIF = '/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf'
BODY = ImageFont.truetype(SANS, 20)
SMALL = ImageFont.truetype(SANS, 17)
TITLE = ImageFont.truetype(SERIF, 42)
SCENES = [
    ('Discover a lead.', 'Search by keyword, category or location.', 'A match is not a verified open application.'),
    ('Read the source.', 'Check the publisher and publication date.', 'An amount may be a budget, not your payout.'),
    ('Verify before applying.', 'Confirm deadline, eligibility and fees.', 'Use official channels to share documents.')
]


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def backdrop(t, poster):
    image = Image.new('RGB', (W, H), '#173d31')
    d = ImageDraw.Draw(image)
    for x in range(20, W, 32):
        for y in range(20, H, 32):
            d.ellipse((x, y, x+1, y+1), fill='#315344')
    for r in (130, 190, 250):
        d.ellipse((820-r, 90-r, 820+r, 90+r), outline='#365b48')
    if not poster:
        sweep = Image.new('RGBA', (W, H), (0, 0, 0, 0))
        s = ImageDraw.Draw(sweep)
        head = (t / 16) * 360 - 110
        for k in range(28):
            a = head - k * 2.2
            s.pieslice((570, -160, 1070, 340), a - 2.2, a, fill=(212, 230, 181, max(0, int(70 - k * 2.5))))
        image = Image.alpha_composite(image.convert('RGBA'), sweep).convert('RGB')
    return image


def scene_layer(index, local, poster=False):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    title, line1, line2 = ('A lead is only the beginning.', 'Discover. Read. Verify.', 'An illustrated guide to your next step.') if poster else SCENES[index]
    reveal = 1.0 if poster else ease(local / 0.7) if index else ease(0.4 + local / 0.7)
    shift = int((1 - reveal) * 18)
    alpha = int(255 * reveal)
    d.text((44 + shift, 91), title, font=TITLE, fill=(243, 247, 233, alpha))
    for i, line in enumerate((line1, line2)):
        a = 1.0 if poster else ease((local - 0.15 - i * 0.12) / 0.7)
        d.text((46 + int((1 - a) * 18), 158 + i * 30), line, font=BODY, fill=(203, 220, 195, int(255 * a)))
    return layer


def cards(t, poster):
    layer = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for i, label in enumerate(('DISCOVER', 'READ', 'VERIFY')):
        x = 46 + i * 298
        if poster:
            on, lift = 1.0, 0.0
        else:
            center = i * SCENE + SCENE / 2
            on = ease((SCENE / 2 + FADE / 2 - abs(t - center)) / FADE)
            if i == 0 and t < SCENE / 2:
                on = 1.0
            if i == 2 and t > DURATION - SCENE / 2:
                on = 1.0
            lift = on * (6 + 3 * math.sin(t / SCENE * 2 * math.pi))
        y = 267 - int(lift)
        base = ((225, 235, 196), (196, 221, 219), (237, 215, 185))[i]
        off = (41, 78, 62)
        fill = tuple(int(off[c] + (base[c] - off[c]) * on) for c in range(3))
        ink_on, ink_off = (36, 61, 50), (195, 214, 189)
        ink = tuple(int(ink_off[c] + (ink_on[c] - ink_off[c]) * on) for c in range(3))
        if on > 0.05:
            d.rounded_rectangle((x + 4, y + 10, x + 276, y + 176), radius=15, fill=(10, 30, 22, int(90 * on)))
        d.rounded_rectangle((x, y, x+272, y+166), radius=15, fill=fill)
        d.text((x+20, y+14), f'0{i+1}', font=SMALL, fill=ink)
        cx, cy = x+137, y+66
        if i == 0:
            d.ellipse((cx-24, cy-26, cx+16, cy+14), outline=ink, width=3)
            d.line((cx+12, cy+11, cx+31, cy+30), fill=ink, width=4)
        elif i == 1:
            d.rounded_rectangle((cx-24, cy-28, cx+24, cy+27), radius=3, outline=ink, width=3)
            for n, dy in enumerate((-13, 0, 13)):
                grow = 1.0 if poster or on < 1 else ease(((t - SCENE) - 0.4 - n * 0.35) / 0.6)
                d.line((cx-14, cy+dy, cx-14 + int(28 * max(grow, 0.0 if on >= 1 else 1.0)), cy+dy), fill=ink, width=3)
        else:
            d.ellipse((cx-29, cy-29, cx+29, cy+29), outline=ink, width=3)
            tick = 1.0 if poster or on < 1 else ease(((t - 2 * SCENE) - 0.5) / 0.8)
            if tick > 0:
                pts = [(cx-15, cy), (cx-3, cy+12), (cx+17, cy-12)]
                if tick < 0.4:
                    k = tick / 0.4
                    d.line((pts[0], (pts[0][0] + (pts[1][0]-pts[0][0])*k, pts[0][1] + (pts[1][1]-pts[0][1])*k)), fill=ink, width=4)
                else:
                    k = (tick - 0.4) / 0.6
                    d.line((pts[0], pts[1], (pts[1][0] + (pts[2][0]-pts[1][0])*k, pts[1][1] + (pts[2][1]-pts[1][1])*k)), fill=ink, width=4)
        d.text((x+20, y+124), label, font=SMALL, fill=ink)
    return layer


def frame(t=0, poster=False):
    image = backdrop(t, poster).convert('RGBA')
    d = ImageDraw.Draw(image)
    d.text((44, 28), 'radar.  /  THE RESEARCH PATH', font=SMALL, fill='#dcebad')
    if poster:
        image = Image.alpha_composite(image, scene_layer(0, 0, True))
    else:
        index = min(2, int(t // SCENE))
        local = t - index * SCENE
        text = scene_layer(index, local)
        if index < 2 and local > SCENE - FADE / 2:
            fade = ease((SCENE - local) / (FADE / 2))
            r, g, b, a = text.split()
            text = Image.merge('RGBA', (r, g, b, a.point(lambda v: int(v * fade))))
        image = Image.alpha_composite(image, text)
    image = Image.alpha_composite(image, cards(t, poster))
    d = ImageDraw.Draw(image)
    d.text((46, 464), 'Research leads, not guaranteed awards.', font=SMALL, fill='#dcebad')
    d.text((46, 493), 'Original illustration / No institution endorsement', font=SMALL, fill='#c0d3b3')
    if not poster:
        d.rectangle((0, H-4, W, H), fill='#294e3e')
        d.rectangle((0, H-4, int(W*t/DURATION), H), fill='#dcebad')
    return image.convert('RGB')


def main():
    frame(poster=True).save(OUT/'research-guide.webp', quality=90)
    command = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-', '-an', '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-preset', 'fast', '-crf', '25', '-movflags', '+faststart', str(OUT/'research-guide.mp4')]
    p = subprocess.Popen(command, stdin=subprocess.PIPE)
    try:
        for n in range(FPS*DURATION):
            p.stdin.write(frame(n/FPS).tobytes())
    finally:
        p.stdin.close()
    if p.wait():
        raise SystemExit('Video encoding failed')
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(OUT/'research-guide.mp4'), '-an', '-c:v', 'libvpx-vp9', '-threads', '2', '-b:v', '0', '-crf', '35', str(OUT/'research-guide.webm')], check=True)
    for name in ('research-guide.webp', 'research-guide.mp4', 'research-guide.webm'):
        print(name, (OUT/name).stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
