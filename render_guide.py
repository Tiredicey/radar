import math
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parent / 'public' / 'static'
W, H, FPS, DURATION = 960, 540, 12, 18
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


def frame(t=0, poster=False):
    active = min(2, int(t // 6))
    image = Image.new('RGB', (W, H), '#173d31')
    d = ImageDraw.Draw(image)
    for x in range(20, W, 32):
        for y in range(20, H, 32):
            d.ellipse((x, y, x+1, y+1), fill='#315344')
    for r in (130, 190, 250):
        d.ellipse((820-r, 90-r, 820+r, 90+r), outline='#365b48')
    d.text((44, 28), 'radar.  /  THE RESEARCH PATH', font=SMALL, fill='#dcebad')
    title, line1, line2 = ('A lead is only the beginning.', 'Discover. Read. Verify.', 'An illustrated guide to your next step.') if poster else SCENES[active]
    d.text((44, 91), title, font=TITLE, fill='#f3f7e9')
    for i, line in enumerate((line1, line2)):
        d.text((46, 158+i*30), line, font=BODY, fill='#cbdcc3')
    for i, label in enumerate(('DISCOVER', 'READ', 'VERIFY')):
        x = 46+i*298
        y = 267 - (int(5*math.sin((t%6)/6*math.pi)) if i == active and not poster else 0)
        on = poster or i == active
        fill = ('#e1ebc4', '#c4dddb', '#edd7b9')[i] if on else '#294e3e'
        ink = '#243d32' if on else '#c3d6bd'
        d.rounded_rectangle((x, y, x+272, y+166), radius=15, fill=fill)
        d.text((x+20, y+14), f'0{i+1}', font=SMALL, fill=ink)
        cx, cy = x+137, y+66
        if i == 0:
            d.ellipse((cx-24, cy-26, cx+16, cy+14), outline=ink, width=3)
            d.line((cx+12, cy+11, cx+31, cy+30), fill=ink, width=4)
        elif i == 1:
            d.rounded_rectangle((cx-24, cy-28, cx+24, cy+27), radius=3, outline=ink, width=3)
            for dy in (-13, 0, 13):
                d.line((cx-14, cy+dy, cx+14, cy+dy), fill=ink, width=3)
        else:
            d.ellipse((cx-29, cy-29, cx+29, cy+29), outline=ink, width=3)
            d.line((cx-15, cy, cx-3, cy+12, cx+17, cy-12), fill=ink, width=4)
        d.text((x+20, y+124), label, font=SMALL, fill=ink)
    d.text((46, 464), 'Research leads, not guaranteed awards.', font=SMALL, fill='#dcebad')
    d.text((46, 493), 'Original illustration / No institution endorsement', font=SMALL, fill='#c0d3b3')
    if not poster:
        d.rectangle((0, H-4, int(W*t/DURATION), H), fill='#dcebad')
    return image


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
