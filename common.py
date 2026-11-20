import os
import re
import io
import json
import random
import asyncio
import time
import traceback

import discord
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter, features

DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(DIR, "images")
CUSTOM_DIR = os.path.join(IMG_DIR, "custom")
BANNER = os.path.join(DIR, "nova_banner.jpg")
FONT = os.path.join(DIR, "fonts", "DejaVuSans-Bold.ttf")
DATA = os.path.join(DIR, "data.json")
COLOR = 0x2B2D31
os.makedirs(CUSTOM_DIR, exist_ok=True)

# "guild" = لعبة وحدة لكل السيرفر ، "channel" = لعبة وحدة لكل روم
LOCK_SCOPE = "guild"

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ================================================================ storage
DEFAULT_SETTINGS = {"timeouts": {}, "lobby": {}, "discussion": 60, "afk_kick": True, "daily": 5, "ping_here": True}
DEFAULT_USER = {"points": 0, "coins": 0, "daily": 0, "best": None, "rwin": 0, "rout": 0,
                "props": [], "ups": [], "imgs": [], "equip": None, "name": ""}


class Store:
    def __init__(self, path):
        self.path = path
        try:
            with open(path, encoding="utf-8") as f:
                self.d = json.load(f)
        except Exception:
            self.d = {}

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    @property
    def settings(self):
        s = self.d.setdefault("settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            s.setdefault(k, dict(v) if isinstance(v, dict) else v)
        return s

    def guild(self, gid):
        return self.d.setdefault("guilds", {}).setdefault(str(gid), {})

    def user(self, gid, uid):
        u = self.guild(gid).setdefault("users", {}).setdefault(str(uid), {})
        for k, v in DEFAULT_USER.items():
            if k not in u:
                u[k] = list(v) if isinstance(v, list) else v
        return u


DB = Store(DATA)


def can_start(m: discord.Member):
    p = m.guild_permissions
    if p.administrator or p.manage_guild:
        return True
    rid = DB.guild(m.guild.id).get("role")
    return rid is None or any(r.id == rid for r in m.roles)


# ================================================================ text
_TASHKEEL = re.compile("[\u064B-\u0652\u0640\u200b]")
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "0123456789" * 2)
_ARDIG = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")


def norm(s):
    s = _TASHKEEL.sub("", s).translate(_DIGITS)
    s = re.sub("[أإآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    return " ".join(s.lower().split())


def ar_digits(n):
    return str(n).translate(_ARDIG)


# ================================================================ registry
GAMES = {}  # name -> dict(fn, slug, title, kind, t)
RESERVED = set()  # كلمات أوامر لا تُحسب كإجابات


def game(name, slug, title, kind, t=30):
    def deco(fn):
        GAMES[name] = dict(fn=fn, slug=slug, title=title, kind=kind, t=t)
        return fn

    return deco


def resolve(text):
    n = norm(text)
    for k in GAMES:
        if norm(k) == n:
            return k
    return None


def reserved():
    return RESERVED | {norm(k) for k in GAMES}


# ================================================================ images / embeds
def game_image(slug):
    for p in (os.path.join(CUSTOM_DIR, slug + ".png"), os.path.join(IMG_DIR, slug + ".png")):
        if os.path.exists(p):
            return p
    return BANNER


def banner_file():
    return discord.File(BANNER, filename="banner.jpg")


def gfile(g):
    return discord.File(game_image(g.slug), filename="banner.jpg")


def mk(title, desc="", big=False):
    e = discord.Embed(title=title, description=desc, color=COLOR)
    if big:
        e.set_image(url="attachment://banner.jpg")
    e.set_footer(text="NOVA STORE")
    return e


RAQM = features.check("raqm")
try:
    import arabic_reshaper
    from bidi.algorithm import get_display

    _SHAPER = True
except Exception:
    _SHAPER = False


def ar(t):
    """تجهيز النص العربي للرسم بـ Pillow"""
    if RAQM or not _SHAPER:
        return t
    return get_display(arabic_reshaper.reshape(t))


def font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def banner_bg(w, h, bright=0.42, blur=3, accent=None):
    b = Image.open(BANNER).convert("RGB")
    bw, bh = b.size
    cw = int(bw * random.uniform(0.3, 0.6))
    ch = int(cw * h / w)
    if ch > bh:
        ch = bh
        cw = int(ch * w / h)
    x, y = random.randint(0, bw - cw), random.randint(0, bh - ch)
    img = b.crop((x, y, x + cw, y + ch)).resize((w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(blur))
    img = ImageEnhance.Brightness(img).enhance(bright)
    if accent:
        img = Image.blend(img, Image.new("RGB", (w, h), accent), 0.25)
    return img


def to_buf(img):
    buf = io.BytesIO()
    img.save(buf, "PNG")
    buf.seek(0)
    return buf


def circle_avatar(avatar_bytes, size):
    if avatar_bytes:
        av = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA").resize((size, size))
    else:
        av = Image.new("RGBA", (size, size), (90, 90, 100, 255))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    return av, mask


def word_image(text):
    """مربع صورة فيه كلمة (للعبة اسرع)"""
    W, H = 640, 340
    img = banner_bg(W, H, 0.4, 4, (40, 90, 160))
    d = ImageDraw.Draw(img)
    for _ in range(7):
        g = random.randint(90, 160)
        d.line((random.randint(0, W), random.randint(0, H), random.randint(0, W), random.randint(0, H)), fill=(g, g, g), width=1)
    t = ar(text)
    size = 110
    f = font(size)
    while d.textlength(t, font=f) > W - 70 and size > 30:
        size -= 6
        f = font(size)
    d.text((W // 2, H // 2), t, font=f, fill=(255, 255, 255), anchor="mm", stroke_width=5, stroke_fill=(0, 0, 0))
    return to_buf(img)


def winner_card(img_path, avatar_bytes):
    bg = Image.open(img_path).convert("RGB").resize((800, 450))
    bg = ImageEnhance.Brightness(bg).enhance(0.55)
    av, mask = circle_avatar(avatar_bytes, 220)
    d = ImageDraw.Draw(bg)
    cx, cy = 400, 245
    d.ellipse((cx - 124, cy - 124, cx + 124, cy + 124), fill=(255, 205, 40))
    bg.paste(av, (cx - 110, cy - 110), mask)
    d.polygon([(cx - 70, cy - 125), (cx - 80, cy - 185), (cx - 35, cy - 150), (cx, cy - 200),
               (cx + 35, cy - 150), (cx + 80, cy - 185), (cx + 70, cy - 125)], fill=(255, 205, 40), outline="white")
    return to_buf(bg)


def stats_card(name, avatar_bytes, points, best):
    W, H = 760, 300
    img = Image.new("RGB", (W, H), (20, 15, 10))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, W - 8, H - 8), 34, outline=(245, 245, 250), width=5)
    av, mask = circle_avatar(avatar_bytes, 190)
    d.ellipse((50, 52, 262, 264), outline=(245, 245, 250), width=4)
    img.paste(av, (61, 63), mask)
    d.line((320, 40, 320, 260), fill=(245, 245, 250), width=3)
    d.text((350, 62), ar(name)[:22], font=font(34), fill=(245, 245, 250), anchor="lm")
    d.line((350, 92, 540, 92), fill=(245, 245, 250), width=3)
    rows = [("النقاط", str(points)), ("أسرع زمن", f"{best:.2f}ث" if best else "—")]
    for k, (lab, val) in enumerate(rows):
        y = 118 + k * 74
        d.rounded_rectangle((350, y, 725, y + 56), 22, outline=(245, 245, 250), width=3)
        d.text((372, y + 28), ar(lab), font=font(26), fill=(245, 245, 250), anchor="lm")
        d.text((705, y + 28), ar(val), font=font(26), fill=(245, 245, 250), anchor="rm")
    return to_buf(img)


def leaderboard_image(rows):
    """rows: [(rank, name, points, avatar_bytes)]"""
    W = 780
    H = 110 + len(rows) * 72
    img = Image.new("RGB", (W, H), (22, 16, 10))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, W - 8, H - 8), 30, outline=(245, 245, 250), width=5)
    d.text((W // 2, 52), ar("توب النقاط"), font=font(36), fill=(245, 245, 250), anchor="mm")
    d.line((40, 90, W - 40, 90), fill=(245, 245, 250), width=3)
    for k, (rank, name, pts, avb) in enumerate(rows):
        y = 106 + k * 72
        d.rounded_rectangle((34, y, W - 34, y + 62), 20, outline=(245, 245, 250), width=4 if k == 0 else 2)
        d.text((62, y + 31), f"#{rank}", font=font(24), fill=(255, 205, 40) if k == 0 else (245, 245, 250), anchor="lm")
        av, mask = circle_avatar(avb, 46)
        img.paste(av, (118, y + 8), mask)
        d.text((184, y + 31), ar(name)[:24], font=font(24), fill=(245, 245, 250), anchor="lm")
        d.text((W - 62, y + 31), f"{pts} ★", font=font(24), fill=(245, 245, 250), anchor="rm")
    return to_buf(img)


async def avatar_bytes(member, size=256):
    try:
        return await member.display_avatar.replace(size=size, format="png").read()
    except Exception:
        return None


async def get_member(g_or_guild, uid):
    guild = g_or_guild.channel.guild if hasattr(g_or_guild, "channel") else g_or_guild
    m = guild.get_member(uid)
    if m:
        return m
    try:
        return await guild.fetch_member(uid)
    except Exception:
        return None


# ================================================================ game object / lock
class BotUser:
    """لاعب وهمي = البوت نفسه (اكس / حجره)"""
    id = -1
    display_name = "البوت"
    mention = "🤖 البوت"

    def __eq__(self, o):
        return isinstance(o, BotUser)

    def __hash__(self):
        return -1


BOT = BotUser()


class Game:
    def __init__(self, name, starter, channel, event_points=0):
        info = GAMES[name]
        self.name, self.slug, self.title = name, info["slug"], info["title"]
        self.starter, self.channel = starter, channel
        self.task = None
        self.views = []
        self.first = True
        self.event_points = event_points
        self.next = None
        self.no_replay = False

    def T(self, default=None):
        return int(DB.settings["timeouts"].get(self.slug, default if default is not None else GAMES[self.name]["t"]))

    @property
    def gid(self):
        return self.channel.guild.id


ACTIVE = {}


def key(ch):
    return ch.guild.id if LOCK_SCOPE == "guild" else ch.id


async def say(g, title, desc="", view=None, file=None):
    e = mk(title, desc)
    kw = {}
    if file is not None:
        kw["files"] = [file]
        e.set_image(url=f"attachment://{file.filename}")
    if view is not None:
        kw["view"] = view
    m = await g.channel.send(embed=e, **kw)
    if view is not None:
        g.views.append((view, m))
    return m


async def close(m, v):
    for c in v.children:
        c.disabled = True
    v.stop()
    try:
        await m.edit(view=v)
    except discord.HTTPException:
        pass


async def scoreboard(g, scores):
    """يعرض النتائج ويرجع id الفائز"""
    if not scores:
        await say(g, "🏁 انتهت اللعبة", "ما أحد جاوب 😅")
        return None
    top = sorted(scores.items(), key=lambda x: -x[1])
    medals = ["🥇", "🥈", "🥉"]
    txt = "\n".join(f"{medals[i] if i < 3 else '▫️'} <@{u}> — {s}" for i, (u, s) in enumerate(top))
    card = None
    try:
        mem = await get_member(g, top[0][0])
        av = await avatar_bytes(mem)
        buf = await asyncio.to_thread(winner_card, game_image(g.slug), av)
        card = discord.File(buf, "winner.png")
    except Exception:
        pass
    await say(g, "🏁 النتائج", f"👑 الفائز: <@{top[0][0]}>\n\n{txt}", file=card)
    return top[0][0]


async def finish(g, winners, points=1, coins=3):
    winners = [w for w in winners if getattr(w, "id", -1) > 0]
    if not winners:
        return
    lines = []
    for w in winners:
        u = DB.user(g.gid, w.id)
        u["name"] = w.display_name
        if g.event_points:
            u["points"] += g.event_points
            lines.append(f"{w.mention}: +{g.event_points} نقطة 🎁")
        else:
            u["points"] += points
            u["coins"] += coins
            lines.append(f"{w.mention}: +{points} نقطة و +{coins} عملة")
    DB.save()
    await say(g, "🎁 الجوائز", "\n".join(lines))


def reward(g, member, points=1, coins=0):
    if g.event_points:
        return
    u = DB.user(g.gid, member.id)
    u["name"] = member.display_name
    u["points"] += points
    u["coins"] += coins
    DB.save()


async def first_answer(g, check_fn, timeout=20):
    def chk(m):
        return m.channel == g.channel and not m.author.bot and check_fn(m.content)

    try:
        return await bot.wait_for("message", check=chk, timeout=timeout)
    except asyncio.TimeoutError:
        return None


# ================================================================ lobby & small views
HOOKS = {}  # تسجّلها economy: shop / bag

EXPLAIN = {
    "roulette": ("**طريقة اللعب:**\n1- شارك في اللعبة بالضغط على زر الدخول\n2- في كل جولة تدور العجلة وتقف على لاعب عشوائي\n"
                 "3- اللاعب اللي وقفت عليه العجلة يختار من يبي يطلّعه\n4- أي لاعب يقدر يستخدم خصائصه من زر ⚡ (اشتريها من المتجر)\n"
                 "5- اللي ما يتفاعل ينطرد\n6- آخر لاعب يبقى هو الفائز ويحصل على نقطة"),
    "mafia": ("**طريقة اللعب:**\n1- شارك بالضغط على زر الدخول (4 لاعبين على الأقل)\n2- توزّع الأدوار سراً: 🔪 مافيا (حد أقصى 5) • 💊 طبيب • 🕵️ محقق • 🙂 مواطنين\n"
              "3- بالليل: المافيا تختار من تقتل، الطبيب يحمي لاعب (وممكن يحمي نفسه مرة وحدة)، والمحقق يكشف لاعب\n"
              "4- بالنهار: نقاش ثم تصويت على من تشكون فيه\n5- تفوز المافيا إذا تساوى عددها مع الباقين، ويفوز المواطنين إذا انطردت المافيا كلها"),
    "mine": ("**طريقة اللعب:**\n1- شارك بالضغط على زر الدخول\n2- البوت يخفي لغم في مكان من الأزرار\n3- كل لاعب يضغط على زر في دوره\n"
             "4- اللي يضغط على اللغم يخرج من اللعبة\n5- آخر لاعب يبقى هو الفائز ويحصل على نقطة"),
    "chairs": ("**طريقة اللعب:**\n1- شارك بالضغط على زر الدخول\n2- البوت يحط كراسي أقل من عدد اللاعبين بواحد\n3- لما تقف الموسيقى اضغط على كرسي بأسرع وقت\n"
               "4- اللي ما يلحق كرسي يطلع\n5- آخر لاعب يبقى هو الفائز ويحصل على نقطة"),
    "rps": ("**طريقة اللعب:**\n1- شارك في اللعبة بالضغط على زر الدخول\n2- سيتم اختيار لاعبين عشوائياً في كل جولة\n"
            "3- كل لاعب يختار: حجر 🪨 أو ورق 📄 أو مقص ✂️\n4- قوانين الفوز:\n• الحجر يكسر المقص\n• المقص يقطع الورق\n• الورق يغطي الحجر\n"
            "5- الفائز يتقدم للجولة التالية\n6- آخر لاعب يبقى هو الفائز ويحصل على نقطة"),
    "hide": ("**طريقة لعب الاختباء:**\n\n🎯 **الهدف:** كن آخر لاعب متبقي!\n\n⚡ **القواعد:**\n• كل لاعب يختار مكان اختباء من الأزرار المتاحة\n"
             "• البوت يختار لاعب عشوائي ليكون **الباحث**\n• الباحث لديه **3 محاولات** فقط للعثور على الآخرين\n• كل محاولة تكشف عن مكان واحد فقط\n"
             "• إذا وجد لاعب، يخرج من اللعبة\n• إذا لم يجد أحد، ينتقل للجولة التالية\n\n🔄 **الجولات:**\n• بعد كل جولة، يغير الجميع أماكنهم\n"
             "• يتم اختيار باحث جديد\n• تستمر حتى يبقى لاعب واحد\n\n🏆 **الفوز:** آخر لاعب متبقي يفوز!"),
    "connect": ("**طريقة اللعب:**\n1- لاعبين اثنين\n2- كل لاعب يختار عمود ليسقط فيه قرصه\n3- أول من يجمع 4 أقراص متتالية (أفقي أو عمودي أو قطري) يفوز"),
}


class Lobby(discord.ui.View):
    def __init__(self, g, minp, maxp, end_ts, prejoin):
        super().__init__(timeout=None)
        self.g, self.minp, self.maxp, self.end = g, minp, maxp, end_ts
        self.players = [g.starter] if prejoin else []
        self.go = asyncio.Event()

        def btn(label, emoji, cb):
            b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)
            b.callback = cb
            self.add_item(b)

        btn("دخول", "➕", self.join)
        btn("خروج", "➖", self.leave)
        if g.slug == "roulette":
            btn("المتجر", "🏪", self.shop)
            btn("الحقيبة", "👜", self.bag)
        elif g.slug in EXPLAIN:
            btn("الشرح", "ℹ️", self.explain)

    def content(self):
        ping = "@here\n" if DB.settings.get("ping_here", True) else ""
        return f"{ping}__ستبدأ اللعبة خلال:__ <t:{self.end}:R>\n**({len(self.players)} / {self.maxp})**"

    async def join(self, i: discord.Interaction):
        if i.user in self.players:
            return await i.response.send_message("انت منضم أصلاً 👍", ephemeral=True)
        if len(self.players) >= self.maxp:
            return await i.response.send_message("اللوبي ممتلئ", ephemeral=True)
        self.players.append(i.user)
        await i.response.edit_message(content=self.content())
        await i.followup.send("✅ دخلت اللعبة", ephemeral=True)
        if len(self.players) >= self.maxp:
            self.go.set()

    async def leave(self, i: discord.Interaction):
        if i.user not in self.players:
            return await i.response.send_message("انت مو داخل اللعبة", ephemeral=True)
        self.players.remove(i.user)
        await i.response.edit_message(content=self.content())
        await i.followup.send("🚪 طلعت من اللعبة", ephemeral=True)

    async def shop(self, i: discord.Interaction):
        await HOOKS["shop"](i)

    async def bag(self, i: discord.Interaction):
        await HOOKS["bag"](i)

    async def explain(self, i: discord.Interaction):
        await i.response.send_message(EXPLAIN[self.g.slug], ephemeral=True)


async def lobby(g, title="", minp=2, maxp=20, wait=30, prejoin=False):
    """لوبي بنفس شكل البوت المرجعي: @here + عدّاد + صورة اللعبة + أزرار. يبدأ تلقائياً بعد المؤقت"""
    wait = int(DB.settings.get("lobby", {}).get(g.slug, wait))
    v = Lobby(g, minp, maxp, int(time.time()) + wait, prejoin)
    m = await g.channel.send(content=v.content(), view=v, file=gfile(g), allowed_mentions=discord.AllowedMentions(everyone=True))
    g.views.append((v, m))
    try:
        await asyncio.wait_for(v.go.wait(), wait)
    except asyncio.TimeoutError:
        pass
    for c in v.children:
        c.disabled = True
    v.stop()
    ok = len(v.players) >= minp
    try:
        await m.edit(content=("🎮 بدأت اللعبة!" if ok else f"❌ انلغت اللعبة — يلزم {minp} لاعبين على الأقل") + f"\n**({len(v.players)} / {maxp})**", view=v)
    except discord.HTTPException:
        pass
    return list(v.players) if ok else None


class OneBtn(discord.ui.View):
    def __init__(self, who, label, emoji):
        super().__init__(timeout=None)
        self.who, self.ev = who, asyncio.Event()
        b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.primary)
        b.callback = self.cb
        self.add_item(b)

    async def cb(self, i: discord.Interaction):
        if i.user != self.who:
            return await i.response.send_message("مو دورك ✋", ephemeral=True)
        await i.response.defer()
        self.ev.set()


async def ask_press(g, text, who, label, emoji, timeout=30):
    v = OneBtn(who, label, emoji)
    m = await say(g, "🎮", text, view=v)
    try:
        await asyncio.wait_for(v.ev.wait(), timeout)
        ok = True
    except asyncio.TimeoutError:
        ok = False
    await close(m, v)
    return ok


async def ephemeral_pick(i, members, text, on_pick):
    """قائمة اختيار لاعب (سرّية)، on_pick(interaction, member_id)"""
    sv = discord.ui.View(timeout=90)
    sel = discord.ui.Select(
        placeholder="اختر...",
        options=[discord.SelectOption(label=m.display_name[:90], value=str(m.id)) for m in members][:25],
    )

    async def cb(ii: discord.Interaction):
        await on_pick(ii, int(sel.values[0]))

    sel.callback = cb
    sv.add_item(sel)
    if i.response.is_done():
        await i.followup.send(text, view=sv, ephemeral=True)
    else:
        await i.response.send_message(text, view=sv, ephemeral=True)


# ================================================================ launch / stop
class Replay(discord.ui.View):
    def __init__(self, name):
        super().__init__(timeout=90)
        self.name, self.msg = name, None

    @discord.ui.button(label="العب مرة ثانية", emoji="🔁", style=discord.ButtonStyle.primary)
    async def again(self, i: discord.Interaction, b: discord.ui.Button):
        err = await launch(i.channel, i.user, self.name)
        await i.response.send_message(err or f"🔁 بدأت **{self.name}** من جديد", ephemeral=bool(err))
        if not err:
            self.stop()
            try:
                await self.msg.edit(view=None)
            except discord.HTTPException:
                pass

    async def on_timeout(self):
        try:
            await self.msg.edit(view=None)
        except Exception:
            pass


async def launch(channel, member, name, event_points=0):
    """يرجع نص الخطأ أو None"""
    if not getattr(channel, "guild", None):
        return "الألعاب داخل السيرفرات فقط."
    if name not in GAMES:
        return "لعبة غير معروفة."
    if not can_start(member):
        return "ما عندك الرتبة اللي تشغّل الألعاب 🚫"
    k = key(channel)
    if k in ACTIVE:
        cur = ACTIVE[k]
        return f"فيه لعبة شغالة بالفعل: **{cur.name}** في {cur.channel.mention}\nلإيقافها اكتب `ايقاف`"
    g = Game(name, member, channel, event_points)
    ACTIVE[k] = g

    async def runner():
        ok = False
        try:
            await GAMES[name]["fn"](g)
            ok = True
        except asyncio.CancelledError:
            pass
        except Exception:
            traceback.print_exc()
            try:
                await channel.send("⚠️ صار خطأ وتم إيقاف اللعبة.")
            except Exception:
                pass
        finally:
            for v, m in g.views:
                v.stop()
                try:
                    if any(not getattr(c, "disabled", True) for c in v.children):
                        for c in v.children:
                            c.disabled = True
                        await m.edit(view=v)
                except Exception:
                    pass
            if ACTIVE.get(k) is g:
                ACTIVE.pop(k, None)
        if not ok:
            return
        if g.next:
            err = await launch(channel, g.starter, g.next)
            if err:
                await channel.send(err)
        elif not g.no_replay:
            try:
                rv = Replay(name)
                rv.msg = await channel.send("🔁 تبون جولة ثانية؟", view=rv)
            except Exception:
                pass

    g.task = asyncio.create_task(runner())
    return None


async def stop_game(channel, member):
    g = ACTIVE.get(key(channel))
    if not g:
        return "ما فيه لعبة شغالة."
    p = member.guild_permissions
    if not (member == g.starter or p.administrator or p.manage_guild or p.manage_messages):
        return "بس اللي شغّل اللعبة أو الإدارة يقدر يوقفها."
    ACTIVE.pop(key(channel), None)
    g.task.cancel()
    return f"⛔ تم إيقاف لعبة **{g.name}**"


# ================================================================ command context (نص أو سلاش)
class Ctx:
    def __init__(self, src):
        self.src = src
        self.is_slash = isinstance(src, discord.Interaction)
        self.sent = False

    @property
    def author(self):
        return self.src.user if self.is_slash else self.src.author

    @property
    def guild(self):
        return self.src.guild

    @property
    def channel(self):
        return self.src.channel

    async def defer(self):
        if self.is_slash and not self.src.response.is_done():
            await self.src.response.defer()
            self.sent = True

    async def send(self, **kw):
        if self.is_slash:
            if not self.src.response.is_done():
                await self.src.response.send_message(**kw)
                return
            await self.src.followup.send(**kw)
        else:
            await self.src.reply(mention_author=False, **kw)
