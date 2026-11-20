"""يولّد صور الألعاب + الأعلام + صور متجر الإقصاء داخل images/
(الصور جاهزة داخل المشروع، تشغيله اختياري). يحتاج Pillow مع raqm + خط Noto Color Emoji للأعلام."""
import os
import math
import random
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance, ImageOps

DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(DIR, "images")
BANNER = os.path.join(DIR, "nova_banner.jpg")
LOGO = os.path.join(DIR, "nova_logo.png")
FONT = os.path.join(DIR, "fonts", "DejaVuSans-Bold.ttf")
EMOJI_FONT = "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"
for sub in ("", "flags", "shop", "custom"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)

W, H = 800, 450
WHITE = (245, 245, 250)
DARK = (22, 22, 28)
GOLD = (255, 205, 40)


def font(size):
    return ImageFont.truetype(FONT, size)


def background(seed, accent, w=W, h=H):
    rnd = random.Random(seed)
    b = Image.open(BANNER).convert("RGB")
    bw, bh = b.size
    cw = int(bw * rnd.uniform(0.35, 0.6))
    ch = int(cw * h / w)
    x, y = rnd.randint(0, bw - cw), rnd.randint(0, bh - ch)
    img = b.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(3))
    img = ImageEnhance.Brightness(img).enhance(0.45)
    return Image.blend(img, Image.new("RGB", (w, h), accent), 0.28)


def rot(pts, ang, cx, cy):
    a = math.radians(ang)
    return [(cx + x * math.cos(a) - y * math.sin(a), cy + x * math.sin(a) + y * math.cos(a)) for x, y in pts]


def arrow(d, cx, cy, r, ang, col):
    a = math.radians(ang)
    px, py = cx + r * math.cos(a), cy + r * math.sin(a)
    tx, ty = -math.sin(a), math.cos(a)
    nx, ny = math.cos(a), math.sin(a)
    d.polygon([(px + tx * 34, py + ty * 34), (px + nx * 24, py + ny * 24), (px - nx * 24, py - ny * 24)], fill=col)


def X(d, x, y, s, col, w=12):
    d.line((x - s, y - s, x + s, y + s), fill=col, width=w)
    d.line((x - s, y + s, x + s, y - s), fill=col, width=w)


def O(d, x, y, s, col, w=12):
    d.ellipse((x - s, y - s, x + s, y + s), outline=col, width=w)


def starpoly(cx, cy, r1, r2, n):
    pts = []
    for k in range(n * 2):
        a = -math.pi / 2 + k * math.pi / n
        r = r1 if k % 2 == 0 else r2
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


# ------------------------------------------------------------------ icons
def roulette(d, cx, cy, c):
    r = 105
    for k in range(8):
        d.pieslice((cx - r, cy - r, cx + r, cy + r), k * 45 - 90, (k + 1) * 45 - 90, fill=c if k % 2 else WHITE)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), outline=DARK, width=6)
    d.ellipse((cx - 22, cy - 22, cx + 22, cy + 22), fill=DARK)
    d.polygon([(cx - 15, cy - r - 20), (cx + 15, cy - r - 20), (cx, cy - r + 12)], fill=GOLD)


def xo(d, cx, cy, c):
    s = 100
    for t in (-s / 3, s / 3):
        d.line((cx + t, cy - s, cx + t, cy + s), fill=WHITE, width=8)
        d.line((cx - s, cy + t, cx + s, cy + t), fill=WHITE, width=8)
    X(d, cx - 67, cy - 67, 20, c, 10)
    O(d, cx, cy, 22, WHITE, 10)
    X(d, cx + 67, cy + 67, 20, c, 10)
    O(d, cx + 67, cy - 67, 20, WHITE, 10)


def mafia(d, cx, cy, c):
    d.rounded_rectangle((cx - 70, cy - 80, cx + 70, cy + 25), 20, fill=(35, 35, 42), outline=WHITE, width=5)
    d.rectangle((cx - 68, cy - 8, cx + 68, cy + 18), fill=c)
    d.ellipse((cx - 125, cy + 5, cx + 125, cy + 58), fill=WHITE)


def chairs(d, cx, cy, c):
    d.rounded_rectangle((cx - 45, cy - 100, cx + 45, cy - 5), 12, outline=WHITE, width=9)
    d.rounded_rectangle((cx - 62, cy, cx + 62, cy + 30), 9, fill=c)
    d.line((cx - 50, cy + 30, cx - 62, cy + 98), fill=WHITE, width=10)
    d.line((cx + 50, cy + 30, cx + 62, cy + 98), fill=WHITE, width=10)


def rps(d, cx, cy, c):
    d.ellipse((cx - 130, cy - 40, cx - 50, cy + 40), fill=WHITE)
    d.rounded_rectangle((cx - 38, cy - 55, cx + 38, cy + 55), 8, fill=c)
    d.line((cx + 65, cy - 50, cx + 125, cy + 30), fill=WHITE, width=11)
    d.line((cx + 125, cy - 50, cx + 65, cy + 30), fill=WHITE, width=11)
    d.ellipse((cx + 52, cy + 28, cx + 80, cy + 56), outline=c, width=8)
    d.ellipse((cx + 110, cy + 28, cx + 138, cy + 56), outline=c, width=8)


def hide(d, cx, cy, c):
    d.ellipse((cx - 125, cy - 62, cx + 125, cy + 62), outline=WHITE, width=10)
    d.ellipse((cx - 46, cy - 46, cx + 46, cy + 46), fill=c)
    d.ellipse((cx - 20, cy - 20, cx + 20, cy + 20), fill=DARK)
    d.ellipse((cx + 8, cy - 32, cx + 24, cy - 16), fill=WHITE)


def fast(d, cx, cy, c):
    d.polygon([(cx + 15, cy - 115), (cx - 62, cy + 10), (cx - 5, cy + 10), (cx - 28, cy + 115),
               (cx + 68, cy - 30), (cx + 10, cy - 30)], fill=GOLD, outline=WHITE)


def fakk(d, cx, cy, c):
    zz = [(0, -60), (16, -25), (-10, 5), (10, 35), (0, 60)]
    d.polygon([(cx - 120, cy - 60)] + [(cx + x - 12, cy + y) for x, y in zz] + [(cx - 120, cy + 60)], fill=WHITE)
    d.polygon([(cx + x + 12, cy + y) for x, y in zz] + [(cx + 120, cy + 60), (cx + 120, cy - 60)], fill=c)


def dmj(d, cx, cy, c):
    d.rounded_rectangle((cx - 130, cy - 50, cx - 40, cy + 50), 14, fill=WHITE)
    d.rounded_rectangle((cx + 40, cy - 50, cx + 130, cy + 50), 14, fill=c)
    d.line((cx - 20, cy, cx + 20, cy), fill=WHITE, width=14)
    d.line((cx, cy - 20, cx, cy + 20), fill=WHITE, width=14)


def flags(d, cx, cy, c):
    d.line((cx - 80, cy - 105, cx - 80, cy + 105), fill=WHITE, width=11)
    for k, col in enumerate((c, WHITE, (40, 40, 52))):
        d.rectangle((cx - 74, cy - 100 + k * 38, cx + 100, cy - 62 + k * 38), fill=col)


def reverse(d, cx, cy, c):
    r = 78
    d.arc((cx - r, cy - r, cx + r, cy + r), 200, 335, fill=WHITE, width=16)
    arrow(d, cx, cy, r, 335, WHITE)
    d.arc((cx - r, cy - r, cx + r, cy + r), 20, 155, fill=c, width=16)
    arrow(d, cx, cy, r, 155, c)


def harf(d, cx, cy, c):
    d.rounded_rectangle((cx - 95, cy - 100, cx + 95, cy + 100), 28, outline=WHITE, width=9)
    d.text((cx, cy - 8), "ح", font=font(190), fill=c, anchor="mm")


def fix(d, cx, cy, c):
    d.ellipse((cx - 105, cy - 105, cx + 105, cy + 105), fill=c)
    d.line([(cx - 52, cy + 2), (cx - 12, cy + 44), (cx + 56, cy - 38)], fill=WHITE, width=20, joint="curve")


def company(d, cx, cy, c):
    d.rectangle((cx - 62, cy - 105, cx + 62, cy + 105), fill=WHITE)
    for r in range(4):
        for k in range(3):
            x, y = cx - 42 + k * 34, cy - 85 + r * 38
            d.rectangle((x, y, x + 20, y + 22), fill=c)
    d.rectangle((cx - 16, cy + 62, cx + 16, cy + 105), fill=DARK)


def asbk(d, cx, cy, c):
    d.rounded_rectangle((cx - 120, cy - 48, cx + 10, cy + 48), 48, outline=WHITE, width=15)
    d.rounded_rectangle((cx - 10, cy - 48, cx + 120, cy + 48), 48, outline=c, width=15)


def opposite(d, cx, cy, c):
    d.line((cx - 80, cy, cx + 80, cy), fill=WHITE, width=18)
    d.polygon([(cx - 125, cy), (cx - 70, cy - 48), (cx - 70, cy + 48)], fill=c)
    d.polygon([(cx + 125, cy), (cx + 70, cy - 48), (cx + 70, cy + 48)], fill=c)


def plural(d, cx, cy, c):
    for (x, y), col in zip(((cx - 62, cy + 35), (cx + 62, cy + 35), (cx, cy - 55)), (WHITE, c, GOLD)):
        d.ellipse((x - 48, y - 48, x + 48, y + 48), fill=col)


def singular(d, cx, cy, c):
    d.ellipse((cx - 95, cy - 95, cx + 95, cy + 95), fill=c, outline=WHITE, width=8)
    d.text((cx, cy - 4), "1", font=font(130), fill=WHITE, anchor="mm")


def capitals(d, cx, cy, c):
    d.pieslice((cx - 70, cy - 95, cx + 70, cy + 45), 180, 360, fill=c)
    d.polygon([(cx, cy - 115), (cx + 8, cy - 98), (cx - 8, cy - 98)], fill=GOLD)
    d.rectangle((cx - 110, cy + 5, cx + 110, cy + 28), fill=WHITE)
    for k in range(5):
        x = cx - 90 + k * 45
        d.rectangle((x, cy + 28, x + 20, cy + 82), fill=WHITE)
    d.rectangle((cx - 120, cy + 82, cx + 120, cy + 100), fill=WHITE)


def mul(d, cx, cy, c):
    d.ellipse((cx - 100, cy - 100, cx + 100, cy + 100), outline=WHITE, width=10)
    X(d, cx, cy, 48, c, 20)


def sub(d, cx, cy, c):
    d.ellipse((cx - 100, cy - 100, cx + 100, cy + 100), outline=WHITE, width=10)
    d.rounded_rectangle((cx - 55, cy - 13, cx + 55, cy + 13), 10, fill=c)


def mine(d, cx, cy, c):
    d.line((cx + 25, cy - 55, cx + 55, cy - 95, cx + 90, cy - 95), fill=WHITE, width=9)
    d.polygon(starpoly(cx + 100, cy - 95, 28, 11, 6), fill=GOLD)
    d.ellipse((cx - 85, cy - 65, cx + 85, cy + 105), fill=(40, 40, 48), outline=WHITE, width=7)
    d.ellipse((cx - 55, cy - 38, cx - 25, cy - 8), fill=(120, 120, 135))
    d.rectangle((cx - 12, cy - 78, cx + 38, cy - 55), fill=c)


def connect(d, cx, cy, c):
    pattern = ["RY.Y", "YR.R", ".RYR"]
    for r in range(3):
        for k in range(4):
            x, y = cx - 105 + k * 70, cy - 70 + r * 70
            ch = pattern[r][k]
            col = (235, 64, 52) if ch == "R" else (250, 204, 21) if ch == "Y" else (60, 60, 72)
            d.ellipse((x - 30, y - 30, x + 30, y + 30), fill=col)


def vote(d, cx, cy, c):
    d.polygon(rot([(-45, -62), (45, -62), (45, 28), (-45, 28)], -12, cx - 5, cy - 55), fill=WHITE)
    d.line((cx - 25, cy - 70, cx - 5, cy - 45, cx + 25, cy - 90), fill=c, width=9)
    d.rounded_rectangle((cx - 105, cy - 10, cx + 105, cy + 95), 12, fill=c)
    d.rectangle((cx - 55, cy + 5, cx + 55, cy + 17), fill=DARK)


def event(d, cx, cy, c):
    d.polygon([(cx - 72, cy - 95), (cx + 72, cy - 95), (cx + 50, cy + 12), (cx - 50, cy + 12)], fill=GOLD)
    d.arc((cx - 112, cy - 85, cx - 40, cy - 15), 90, 270, fill=GOLD, width=11)
    d.arc((cx + 40, cy - 85, cx + 112, cy - 15), 270, 90, fill=GOLD, width=11)
    d.rectangle((cx - 12, cy + 12, cx + 12, cy + 58), fill=GOLD)
    d.rectangle((cx - 55, cy + 58, cx + 55, cy + 84), fill=GOLD)
    d.polygon(starpoly(cx, cy - 45, 28, 12, 5), fill=WHITE)


# صور متجر الإقصاء
def boom(d, cx, cy, c):
    d.polygon(starpoly(cx, cy, 115, 58, 9), fill=(255, 110, 20))
    d.polygon(starpoly(cx, cy, 70, 36, 9), fill=GOLD)


def skull(d, cx, cy, c):
    d.ellipse((cx - 82, cy - 100, cx + 82, cy + 50), fill=WHITE)
    d.rounded_rectangle((cx - 48, cy + 25, cx + 48, cy + 95), 14, fill=WHITE)
    for sx in (-34, 34):
        d.ellipse((cx + sx - 22, cy - 40, cx + sx + 22, cy + 4), fill=DARK)
    d.polygon([(cx, cy + 6), (cx - 11, cy + 28), (cx + 11, cy + 28)], fill=DARK)
    for k in range(-2, 3):
        d.line((cx + k * 18, cy + 62, cx + k * 18, cy + 95), fill=DARK, width=4)


def sword(d, cx, cy, c):
    blade = [(-115, -13), (55, -13), (100, 0), (55, 13), (-115, 13)]
    d.polygon(rot(blade, -45, cx, cy), fill=(225, 230, 240), outline=WHITE)
    d.polygon(rot([(55, -42), (72, -42), (72, 42), (55, 42)], -45, cx, cy), fill=c)
    d.polygon(rot([(72, -10), (120, -10), (120, 10), (72, 10)], -45, cx, cy), fill=(120, 80, 40))


def crown(d, cx, cy, c):
    d.polygon([(cx - 100, cy + 60), (cx - 100, cy - 50), (cx - 50, cy), (cx, cy - 75), (cx + 50, cy),
               (cx + 100, cy - 50), (cx + 100, cy + 60)], fill=GOLD, outline=WHITE)
    for x, col in ((-60, (235, 64, 52)), (0, (52, 152, 219)), (60, (46, 204, 113))):
        d.ellipse((cx + x - 14, cy + 22, cx + x + 14, cy + 50), fill=col)


def fire(d, cx, cy, c):
    d.polygon([(cx, cy - 108), (cx + 44, cy - 35), (cx + 24, cy - 40), (cx + 58, cy + 20), (cx + 30, cy + 90),
               (cx - 30, cy + 90), (cx - 58, cy + 20), (cx - 24, cy - 40), (cx - 44, cy - 35)], fill=(255, 110, 20))
    d.polygon([(cx, cy - 30), (cx + 28, cy + 25), (cx + 18, cy + 82), (cx - 18, cy + 82), (cx - 28, cy + 25)], fill=GOLD)


def star(d, cx, cy, c):
    d.polygon(starpoly(cx, cy, 112, 46, 5), fill=GOLD, outline=WHITE)


# slug, عنوان, لون, أيقونة
GAMES = [
    ("fast", "اسرع", (255, 193, 7), fast),
    ("fakk", "فكّك", (96, 125, 139), fakk),
    ("company", "شركة", (63, 81, 181), company),
    ("asbk", "اشبك", (0, 150, 136), asbk),
    ("fix", "صحّح", (39, 174, 96), fix),
    ("reverse", "اعكس", (103, 58, 183), reverse),
    ("opposite", "عكس", (233, 30, 99), opposite),
    ("plural", "جمع", (76, 175, 80), plural),
    ("singular", "مفرد", (3, 169, 244), singular),
    ("harf", "حرف", (255, 87, 34), harf),
    ("flags", "أعلام", (244, 67, 54), flags),
    ("capitals", "عواصم", (121, 85, 72), capitals),
    ("mul", "ضرب", (255, 152, 0), mul),
    ("sub", "طرح", (0, 188, 212), sub),
    ("dmj", "ادمج", (76, 175, 80), dmj),
    ("roulette", "روليت", (231, 76, 60), roulette),
    ("hide", "هايد", (52, 73, 94), hide),
    ("mine", "لغم", (192, 57, 43), mine),
    ("connect", "وصل", (52, 152, 219), connect),
    ("mafia", "مافيا", (192, 57, 43), mafia),
    ("chairs", "كراسي", (230, 126, 34), chairs),
    ("xo", "اكس او", (52, 152, 219), xo),
    ("rps", "حجرة ورقة مقص", (26, 188, 156), rps),
    ("vote", "تصويت", (155, 89, 182), vote),
    ("event", "ايفنت", (241, 196, 15), event),
]
SHOP = [("boom", "الانفجار", boom), ("bomb", "القنبلة", mine), ("skull", "الجمجمة", skull), ("bolt", "الصاعقة", fast),
        ("sword", "السيف", sword), ("crown", "التاج", crown), ("fire", "النار", fire), ("star", "النجمة", star)]
from data_ar import FLAG_CODES


def make(i, slug, title, accent, fn, w=W, h=H, folder=""):
    img = background(i, accent, w, h)
    d = ImageDraw.Draw(img)
    fn(d, w // 2, int(h * 0.41), accent)
    d.rectangle((0, h - 10, w, h), fill=accent)
    d.text((w // 2, int(h * 0.855)), title, font=font(66), fill=WHITE, anchor="mm", stroke_width=4, stroke_fill=DARK)
    d.text((w - 18, h - 24), "NOVA STORE", font=font(18), fill=(210, 210, 220), anchor="rb")
    img.save(os.path.join(OUT, folder, f"{slug}.png"))
    return img



GROUP_SLUGS = {"roulette", "hide", "mine", "connect", "mafia", "chairs", "xo", "rps", "vote", "event"}
LIGHT = (175, 175, 185)


def lobby_bg(w, h):
    glow = ImageOps.invert(Image.radial_gradient("L").resize((w * 2, h * 2))).crop((w, h, 2 * w, 2 * h))
    glow = glow.point(lambda v: int(v * 0.8))
    return Image.composite(Image.new("RGB", (w, h), (92, 52, 168)), Image.new("RGB", (w, h), (18, 10, 30)), glow)


def icon_tile(fn):
    cv = Image.new("RGBA", (440, 440), (0, 0, 0, 0))
    fn(ImageDraw.Draw(cv), 220, 220, LIGHT)
    cv = cv.crop(cv.getbbox())
    s = min(96 / cv.width, 96 / cv.height)
    return cv.resize((max(1, int(cv.width * s)), max(1, int(cv.height * s))), Image.LANCZOS)


def make_lobby(slug, title, fn):
    """صورة اللوبي بنفس شكل البوت المرجعي: خلفية سوداء/حمراء + أيقونة + عنوان + شريط"""
    W, H = 1000, 540
    img = lobby_bg(W, H)
    d = ImageDraw.Draw(img)
    cx = W // 2
    d.rounded_rectangle((cx - 72, 36, cx + 72, 180), 30, outline=WHITE, width=5)
    ic = icon_tile(fn)
    img.paste(ic, (cx - ic.width // 2, 108 - ic.height // 2), ic)
    words = title.split()
    if len(words) >= 3:
        for k, (w, size) in enumerate(zip(words, (96, 72, 54))):
            d.text((cx, 268 + [0, 78, 138][k]), w, font=font(size), fill=WHITE, anchor="mm")
    else:
        size = 130
        while font(size).getlength(title) > W - 140 and size > 40:
            size -= 6
        d.text((cx, 312), title, font=font(size), fill=WHITE, anchor="mm")
    pill = "اضغط على زر دخول للإنضمام إلى اللعبة" if slug in GROUP_SLUGS else "اكتب الإجابة بأسرع وقت"
    f = font(26)
    pw = int(f.getlength(pill)) + 70
    d.rounded_rectangle((cx - pw // 2, 456, cx + pw // 2, 512), 28, outline=WHITE, width=4)
    d.text((cx, 484), pill, font=f, fill=WHITE, anchor="mm")
    lg = Image.open(LOGO).convert("RGBA")
    lg = lg.crop(lg.getbbox()).resize((40, 60), Image.LANCZOS)
    img.paste(lg, (36, 30), lg)
    d.text((88, 60), "NOVA STORE", font=font(18), fill=(214, 200, 245), anchor="lm")
    img.save(os.path.join(OUT, f"{slug}.png"))
    return img


def flag_images():
    f = ImageFont.truetype(EMOJI_FONT, 109)
    for code in FLAG_CODES:
        emoji = "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)
        im = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
        ImageDraw.Draw(im).text((10, 10), emoji, font=f, embedded_color=True)
        im = im.crop(im.getbbox())
        im = im.resize((360, int(360 * im.height / im.width)), Image.LANCZOS)
        im.save(os.path.join(OUT, "flags", f"{code}.png"))


def preview(imgs):
    tw, th = 320, 180
    cols = 5
    rows = math.ceil(len(imgs) / cols)
    sheet = Image.new("RGB", (cols * tw + (cols + 1) * 10, rows * th + (rows + 1) * 10), (14, 14, 18))
    for k, im in enumerate(imgs):
        sheet.paste(im.resize((tw, th), Image.LANCZOS), (10 + (k % cols) * (tw + 10), 10 + (k // cols) * (th + 10)))
    sheet.save(os.path.join(DIR, "games_preview.png"))


if __name__ == "__main__":
    ims = [make_lobby(slug, title, fn) for slug, title, _c, fn in GAMES]
    for j, (slug, title, fn) in enumerate(SHOP):
        make(100 + j, slug, title, (120 + j * 8, 80 + j * 6, 200 + j * 5), fn, 600, 340, "shop")
    # الأعلام تبقى كما هي (لعبة تخمين الدول تحتاج ألوانها الأصلية)
    preview(ims)
    print(f"games={len(ims)} shop={len(SHOP)} flags={len(FLAG_CODES)}")
