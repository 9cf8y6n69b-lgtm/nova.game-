from common import *

from data_ar import WORDS as _W, PLURALS as _P, OPPOSITES as _O, CAPITALS as _CA, COMPANIES as _CO, FLAGS
import aiohttp

SIM = {"س": "ص", "ص": "س", "د": "ض", "ض": "د", "ذ": "ظ", "ظ": "ذ", "ت": "ط", "ط": "ت",
       "ح": "خ", "خ": "ح", "ع": "غ", "غ": "ع", "ق": "ك", "ك": "ق"}


def custom(key):
    """أسئلة أضافها الأدمن من لوحة التحكم"""
    return [tuple(x) for x in DB.d.get("custom", {}).get(key, []) if x]


def words():
    return _W + [x[0] for x in custom("words")]


def plurals():
    return _P + [x for x in custom("plurals") if len(x) >= 2]


def opposites():
    return _O + [x for x in custom("opposites") if len(x) >= 2]


def capitals():
    return _CA + [x for x in custom("capitals") if len(x) >= 2]


def companies():
    return _CO + [x for x in custom("companies") if len(x) >= 2]


LETTERS = list("ابتجحدرسشعفقكلمنهوي")
CATEGORIES = ["جماد", "اسم", "حيوان", "نبات", "بلاد"]


def exact(answers):
    acc = {norm(a) for a in answers}
    return (lambda c: norm(c) in acc), answers[0]


def corrupt(w):
    idx = [i for i, c in enumerate(w) if c in SIM]
    if idx:
        i = random.choice(idx)
        res = w[:i] + SIM[w[i]] + w[i + 1:]
    else:
        l = list(w)
        i = random.randrange(len(l) - 1)
        l[i], l[i + 1] = l[i + 1], l[i]
        res = "".join(l)
    return res if res != w else w[::-1]


# ---------------------------------------------------------------- makers -> (prompt, check, reveal, file)
async def mk_fast():
    w = random.choice(words())
    buf = await asyncio.to_thread(word_image, w)
    return "اكتب الكلمة اللي في الصورة بأسرع وقت!", *exact([w]), discord.File(buf, "word.png")


async def mk_fakk():
    w = random.choice(words())
    return f"فكّك الكلمة (حرف حرف بمسافات)، مثال: ارنب ← ا ر ن ب\n# {w}", *exact([" ".join(w)]), None


async def mk_asbk():
    w = random.choice(words())
    return f"اشبك الحروف واكتب الكلمة:\n# {' '.join(w)}", *exact([w]), None


async def mk_dmj():
    a, b = random.sample(words(), 2)
    return f"ادمج الكلمتين في كلمة وحدة بدون مسافة:\n# {a}  +  {b}", *exact([a + b]), None


async def mk_reverse():
    w = random.choice(words())
    return f"الحروف مقلوبة! اكتب الكلمة الصحيحة:\n# {' '.join(w[::-1])}", *exact([w]), None


async def mk_fix():
    w = random.choice(words())
    return f"صحّح الكلمة واكتبها صح:\n# {corrupt(w)}", *exact([w]), None


async def mk_plural():
    q = random.choice(plurals())
    return f"اكتب **جمع** الكلمة:\n# {q[0]}", *exact(list(q[1:])), None


async def mk_singular():
    q = random.choice(plurals())
    return f"اكتب **مفرد** الكلمة:\n# {q[1]}", *exact([q[0]]), None


async def mk_opposite():
    q = random.choice(opposites())
    return f"اكتب **عكس** الكلمة:\n# {q[0]}", *exact(list(q[1:])), None


async def mk_capital():
    q = random.choice(capitals())
    return f"ما هي عاصمة:\n# {q[0]}", *exact(list(q[1:])), None


async def mk_company():
    q = random.choice(companies())
    return f"ما اسم الشركة؟\n# {q[0]}", *exact(list(q[1:])), None


FLAG_DIR = os.path.join(IMG_DIR, "flags")


async def flag_bytes(code):
    """صورة العلم: من الملف المحلي، وإذا ناقص تنزّل من الانترنت وتنحفظ"""
    path = os.path.join(FLAG_DIR, code + ".png")
    if os.path.exists(path):
        with open(path, "rb") as f:
            return f.read()
    cps = "-".join(f"{0x1F1E6 + ord(c) - 65:x}" for c in code)
    for url in (f"https://flagcdn.com/w320/{code.lower()}.png",
                f"https://cdn.jsdelivr.net/gh/twitter/twemoji@14.0.2/assets/72x72/{cps}.png"):
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=6)) as ses:
                async with ses.get(url) as r:
                    if r.status == 200:
                        data = await r.read()
                        try:
                            os.makedirs(FLAG_DIR, exist_ok=True)
                            with open(path, "wb") as f:
                                f.write(data)
                        except OSError:
                            pass
                        return data
        except Exception:
            continue
    return None


async def mk_flag():
    q = random.choice(FLAGS)
    data = await flag_bytes(q[0])
    if data:
        return "ما اسم هذه الدولة؟", *exact(list(q[1:])), discord.File(io.BytesIO(data), "flag.png")
    emoji = "".join(chr(0x1F1E6 + ord(c) - 65) for c in q[0])
    return f"ما اسم هذه الدولة؟\n# {emoji}", *exact(list(q[1:])), None


async def mk_mul():
    a, b = random.randint(2, 12), random.randint(2, 12)
    return f"احسب الناتج:\n# {ar_digits(a)} × {ar_digits(b)}", *exact([str(a * b)]), None


async def mk_sub():
    a = random.randint(20, 99)
    b = random.randint(3, a - 1)
    return f"احسب الناتج:\n# {ar_digits(a)} − {ar_digits(b)}", *exact([str(a - b)]), None


async def mk_harf():
    letter, cat = random.choice(LETTERS), random.choice(CATEGORIES)
    nl = norm(letter)

    def chk(c):
        n = norm(c)
        return len(n.split()) == 1 and len(n) >= 3 and n[0] == nl and n not in reserved()

    return f"اكتب كلمة من نوع **{cat}** تبدأ بحرف:\n# {letter}", chk, f"أي {cat} تبدأ بـ {letter}", None


# ---------------------------------------------------------------- rounds
async def solo_rounds(g, title, make, n=5):
    scores = {}
    timeout = g.T()
    for r in range(1, n + 1):
        prompt, chk, reveal, file = await make()
        await say(g, f"{title} — جولة {r}/{n}", prompt, file=file)
        t0 = time.monotonic()
        m = await first_answer(g, chk, timeout)
        if m:
            dt = time.monotonic() - t0
            scores[m.author.id] = scores.get(m.author.id, 0) + 1
            reward(g, m.author, points=1)
            u = DB.user(g.gid, m.author.id)
            if u["best"] is None or dt < u["best"]:
                u["best"] = round(dt, 2)
                DB.save()
            try:
                await m.add_reaction("✅")
            except discord.HTTPException:
                pass
            await say(g, "✅ صح", f"{m.author.mention} جاوب في {dt:.1f} ثانية")
        else:
            await say(g, "⏰ انتهى الوقت", f"الجواب: **{reveal}**")
        await asyncio.sleep(2)
    top = await scoreboard(g, scores)
    if g.event_points and top:
        await finish(g, [await get_member(g, top)])


def solo(name, slug, title, make, t=20):
    async def run(g):
        await solo_rounds(g, title, make, 5)

    GAMES[name] = dict(fn=run, slug=slug, title=title, kind="solo", t=t)


solo("اسرع", "fast", "⚡ اسرع", mk_fast, 25)
solo("فكك", "fakk", "🔨 فكك", mk_fakk, 25)
solo("شركة", "company", "🏢 شركة", mk_company, 25)
solo("اشبك", "asbk", "🧷 اشبك", mk_asbk, 25)
solo("صحح", "fix", "✏️ صحح", mk_fix, 25)
solo("اعكس", "reverse", "🔄 اعكس", mk_reverse, 25)
solo("عكس", "opposite", "↔️ عكس", mk_opposite, 20)
solo("جمع", "plural", "➕ جمع", mk_plural, 20)
solo("مفرد", "singular", "1️⃣ مفرد", mk_singular, 20)
solo("حرف", "harf", "🔤 حرف", mk_harf, 25)
solo("اعلام", "flags", "🏳️ اعلام", mk_flag, 20)
solo("عواصم", "capitals", "🏛️ عواصم", mk_capital, 20)
solo("ضرب", "mul", "✖️ ضرب", mk_mul, 20)
solo("طرح", "sub", "➖ طرح", mk_sub, 20)
solo("ادمج", "dmj", "🧩 ادمج", mk_dmj, 25)
