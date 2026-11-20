import os
import html
import hmac
import time
import hashlib
import secrets
from urllib.parse import quote

from aiohttp import web
from PIL import Image, ImageOps

from common import DB, GAMES, CUSTOM_DIR, game_image, bot, norm

DEFAULT_LOBBY = {"roulette": 60, "mafia": 60, "mine": 30, "chairs": 30, "rps": 10, "hide": 30, "connect": 30, "xo": 30}
INVITE_PERMS = 248896
QTYPES = {
    "words": ("كلمات (فكك/اشبك/اعكس/صحح/ادمج/اسرع)", "كلمة"),
    "opposites": ("عكس", "الكلمة | عكسها | بديل (اختياري)"),
    "plurals": ("جمع / مفرد", "المفرد | الجمع | بديل (اختياري)"),
    "capitals": ("عواصم", "الدولة | العاصمة | بديل (اختياري)"),
    "companies": ("شركة", "وصف الشركة | الاسم | بديل (اختياري)"),
}
esc = html.escape
CSS = """
*{box-sizing:border-box}body{font-family:system-ui,Segoe UI,Tahoma,sans-serif;background:#14141a;color:#eee;margin:0;direction:rtl}
.wrap{max-width:900px;margin:auto;padding:14px}nav{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
nav a,.btn,button{background:#5865f2;color:#fff;text-decoration:none;padding:9px 13px;border-radius:9px;border:0;font:inherit;cursor:pointer;display:inline-block}
nav a{background:#262634}button.red,.btn.red{background:#c0392b}button.gray{background:#444}
h1{margin:4px 0 12px}h2{margin:20px 0 8px;color:#9ad}.card{background:#1e1e28;border-radius:14px;padding:14px;margin:10px 0}
.row{display:flex;gap:12px;align-items:center;flex-wrap:wrap}img{width:160px;height:90px;object-fit:cover;border-radius:8px}
input,select,textarea{font:inherit;padding:9px 10px;border-radius:8px;border:1px solid #444;background:#2a2a36;color:#eee;max-width:100%}
label{display:block;margin:8px 0}small{color:#9a9}.ok{background:#1f3d2a;padding:10px;border-radius:10px;margin-bottom:10px}
table{width:100%;border-collapse:collapse}td,th{padding:6px;border-bottom:1px solid #333;text-align:right}code{background:#2a2a36;padding:2px 6px;border-radius:6px}
"""


def password():
    pw = os.getenv("DASH_PASSWORD")
    if pw:
        return pw
    s = DB.settings
    if not s.get("dash_password"):
        s["dash_password"] = secrets.token_urlsafe(9)
        DB.save()
        print("DASHBOARD PASSWORD (auto-generated):", s["dash_password"])
    return s["dash_password"]


def base_url():
    return os.getenv("RENDER_EXTERNAL_URL") or f"http://localhost:{os.getenv('PORT', '10000')}"


def invite_url():
    cid = bot.user.id if bot.user else "CLIENT_ID"
    return f"https://discord.com/oauth2/authorize?client_id={cid}&permissions={INVITE_PERMS}&scope=bot%20applications.commands"


def _sig(exp):
    return hmac.new(password().encode(), exp.encode(), hashlib.sha256).hexdigest()


def make_token():
    exp = str(int(time.time()) + 7 * 86400)
    return f"{exp}.{_sig(exp)}"


def authed(request):
    t = request.cookies.get("bl_session", "")
    try:
        exp, sig = t.split(".")
        return int(exp) > time.time() and hmac.compare_digest(sig, _sig(exp))
    except Exception:
        return False


def guard(fn):
    async def w(request):
        if not authed(request):
            raise web.HTTPFound("/login")
        return await fn(request)

    return w


def go(path, msg=""):
    raise web.HTTPFound(path + (("?msg=" + quote(msg)) if msg else ""))


def layout(body, request=None):
    msg = esc(request.query.get("msg", "")) if request else ""
    nav = ('<a href="/dashboard">🏠 الرئيسية</a><a href="/dashboard/settings">⚙️ الإعدادات</a>'
           '<a href="/dashboard/games">🎮 الألعاب والصور</a><a href="/dashboard/questions">❓ الأسئلة</a><a href="/logout">🚪 خروج</a>')
    return web.Response(text=f"""<!doctype html><html lang="ar"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NOVA STORE Dashboard</title><style>{CSS}</style></head>
<body><div class="wrap"><h1>🎮 لوحة تحكم NOVA STORE</h1><nav>{nav}</nav>{f'<div class="ok">✅ {msg}</div>' if msg else ''}{body}</div></body></html>""",
                        content_type="text/html")


# ------------------------------------------------------------------ login
async def index(request):
    return web.Response(text="NOVA STORE bot is running ✅")


async def login_page(request):
    bad = "<p style='color:#e66'>كلمة السر غلط</p>" if request.query.get("bad") else ""
    return web.Response(text=f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>دخول</title><style>{CSS}</style></head><body><div class="wrap"><div class="card"><h1>🔐 دخول لوحة التحكم</h1>{bad}
<form method="post" action="/login"><label>كلمة السر<br><input type="password" name="password" autofocus style="width:100%"></label><button>دخول</button></form>
<p><small>كلمة السر = متغير DASH_PASSWORD، أو اكتب /dashboard في ديسكورد (للأدمن) وتجيك.</small></p></div></div></body></html>""",
                        content_type="text/html")


async def login_post(request):
    f = await request.post()
    if hmac.compare_digest(str(f.get("password", "")), password()):
        r = web.HTTPFound("/dashboard")
        r.set_cookie("bl_session", make_token(), max_age=7 * 86400, httponly=True, samesite="Lax")
        raise r
    go("/login?bad=1")


async def logout(request):
    r = web.HTTPFound("/login")
    r.del_cookie("bl_session")
    raise r


# ------------------------------------------------------------------ home / servers
@guard
async def home(request):
    cards = []
    for g in sorted(bot.guilds, key=lambda x: -x.member_count if x.member_count else 0):
        cards.append(f'<div class="card row"><div style="flex:1"><b>{esc(g.name)}</b><br><small>{g.member_count or "?"} عضو</small></div>'
                     f'<a class="btn" href="/dashboard/server/{g.id}">إدارة السيرفر</a></div>')
    body = (f'<h2>🌐 السيرفرات</h2>{"".join(cards) or "<div class=card>البوت مو في أي سيرفر</div>"}'
            f'<div class="card"><b>➕ دعوة البوت لسيرفر (مع صلاحيات السلاش)</b><br><br><a class="btn" href="{esc(invite_url())}">رابط الدعوة</a></div>')
    return layout(body, request)


def _roles(guild):
    return [r for r in sorted(guild.roles, key=lambda r: -r.position) if not r.is_default() and not r.managed]


@guard
async def server_page(request):
    gid = int(request.match_info["gid"])
    guild = bot.get_guild(gid)
    if not guild:
        go("/dashboard", "السيرفر مو موجود")
    cfg = DB.guild(gid)
    opts = '<option value="0">— الكل يقدر —</option>' + "".join(
        f'<option value="{r.id}" {"selected" if cfg.get("role") == r.id else ""}>{esc(r.name)}</option>' for r in _roles(guild))
    users = DB.guild(gid).get("users", {})
    top = sorted(((int(u), d) for u, d in users.items()), key=lambda x: -x[1].get("points", 0))[:15]
    rows = "".join(
        f'<tr><td>{(guild.get_member(uid).display_name if guild.get_member(uid) else d.get("name") or "—")}</td><td><code>{uid}</code></td>'
        f'<td>{d.get("points", 0)}</td><td>{d.get("coins", 0)}</td></tr>' for uid, d in top)
    body = f"""<h2>🏠 {esc(guild.name)}</h2>
<div class="card"><form method="post" action="/dashboard/server/{gid}/save">
<label>🔣 بادئة الأوامر (فاضي = بدون بادئة) <input name="prefix" value="{esc(cfg.get('prefix', ''))}" maxlength="5" placeholder="مثال: !"></label>
<label>🎭 الرتبة اللي تقدر تشغّل الألعاب <select name="role">{opts}</select></label>
<button>💾 حفظ</button></form></div>
<h2>⭐ النقاط والعملات</h2>
<div class="card"><form method="post" action="/dashboard/server/{gid}/points">
<label>النوع <select name="kind"><option value="points">نقاط</option><option value="coins">عملات</option></select></label>
<label>العملية <select name="action"><option value="add">إضافة</option><option value="remove">خصم</option><option value="set">تعيين</option></select></label>
<label>آيدي اللاعب <input name="uid" inputmode="numeric" placeholder="اضغط مطولاً على اللاعب ← نسخ المعرّف"></label>
<label>المبلغ <input name="amount" type="number" min="0" value="5"></label><button>تنفيذ</button></form>
<form method="post" action="/dashboard/server/{gid}/reset" onsubmit="return confirm('تصفير نقاط كل السيرفر؟')" style="margin-top:12px"><button class="red">تصفير نقاط كل السيرفر</button></form></div>
<div class="card"><table><tr><th>اللاعب</th><th>المعرّف</th><th>النقاط</th><th>العملات</th></tr>{rows or '<tr><td colspan=4>ما فيه بيانات</td></tr>'}</table></div>"""
    return layout(body, request)


@guard
async def server_save(request):
    gid = int(request.match_info["gid"])
    f = await request.post()
    cfg = DB.guild(gid)
    cfg["prefix"] = str(f.get("prefix", "")).strip()[:5]
    rid = int(f.get("role", 0) or 0)
    if rid:
        cfg["role"] = rid
    else:
        cfg.pop("role", None)
    DB.save()
    go(f"/dashboard/server/{gid}", "تم الحفظ")


@guard
async def server_points(request):
    gid = int(request.match_info["gid"])
    f = await request.post()
    try:
        uid, amount = int(f.get("uid", "")), int(f.get("amount", 0))
    except ValueError:
        go(f"/dashboard/server/{gid}", "آيدي أو مبلغ غير صحيح")
    kind = "coins" if f.get("kind") == "coins" else "points"
    u = DB.user(gid, uid)
    act = f.get("action")
    u[kind] = max(0, amount if act == "set" else u[kind] + (amount if act == "add" else -amount))
    DB.save()
    go(f"/dashboard/server/{gid}", f"تم — {kind}: {u[kind]}")


@guard
async def server_reset(request):
    gid = int(request.match_info["gid"])
    for u in DB.guild(gid).get("users", {}).values():
        u["points"] = 0
    DB.save()
    go(f"/dashboard/server/{gid}", "تم تصفير النقاط")


# ------------------------------------------------------------------ global settings
@guard
async def settings_page(request):
    s = DB.settings
    body = f"""<h2>⚙️ إعدادات عامة</h2><div class="card"><form method="post" action="/dashboard/settings">
<label>💬 وقت النقاش في المافيا (ثواني) <input type="number" min="10" max="600" name="discussion" value="{s['discussion']}"></label>
<label>🪙 مكافأة اليومي (عملات) <input type="number" min="1" max="1000" name="daily" value="{s['daily']}"></label>
<label><input type="checkbox" name="ping_here" {'checked' if s.get('ping_here', True) else ''}> منشن @here عند فتح لوبي</label>
<label><input type="checkbox" name="afk_kick" {'checked' if s['afk_kick'] else ''}> طرد اللاعب اللي ما يتفاعل من اللعبة</label>
<button>💾 حفظ</button></form></div>"""
    return layout(body, request)


@guard
async def settings_save(request):
    f = await request.post()
    s = DB.settings
    try:
        s["discussion"] = max(10, min(600, int(f.get("discussion", 60))))
        s["daily"] = max(1, min(1000, int(f.get("daily", 5))))
    except ValueError:
        pass
    s["afk_kick"] = "afk_kick" in f
    s["ping_here"] = "ping_here" in f
    DB.save()
    go("/dashboard/settings", "تم الحفظ")


# ------------------------------------------------------------------ games: time + lobby + images
@guard
async def games_page(request):
    s = DB.settings
    rows = []
    for name, info in GAMES.items():
        slug = info["slug"]
        cur = s["timeouts"].get(slug, info["t"])
        lob = ""
        if slug in DEFAULT_LOBBY:
            lob = (f'<label>⏳ وقت اللوبي (ثواني) <input form="main" type="number" min="5" max="300" name="l_{slug}" '
                   f'value="{s["lobby"].get(slug, DEFAULT_LOBBY[slug])}"></label>')
        rows.append(f"""<div class="card"><div class="row"><img src="/img/{slug}?v={os.path.getmtime(game_image(slug)):.0f}">
<div style="flex:1"><b>{esc(info['title'])}</b> <small>({esc(name)})</small>
<label>⏱️ الوقت (ثواني) <input form="main" type="number" min="5" max="600" name="t_{slug}" value="{cur}"></label>{lob}</div>
<form method="post" action="/dashboard/upload" enctype="multipart/form-data"><input type="hidden" name="slug" value="{slug}">
<input type="file" name="file" accept="image/*" required><button>رفع صورة</button></form>
<form method="post" action="/dashboard/reset"><input type="hidden" name="slug" value="{slug}"><button class="red">حذف المخصصة</button></form></div></div>""")
    body = ('<form id="main" method="post" action="/dashboard/games"><button>💾 حفظ كل الأوقات</button></form>'
            + "".join(rows) + "<small>الصور المرفوعة تنحفظ في images/custom — على الاستضافة المجانية قد تنمسح عند إعادة النشر.</small>")
    return layout(body, request)


@guard
async def games_save(request):
    f = await request.post()
    s = DB.settings
    for info in GAMES.values():
        v = f.get("t_" + info["slug"])
        if v and str(v).isdigit():
            s["timeouts"][info["slug"]] = max(5, min(600, int(v)))
    for slug in DEFAULT_LOBBY:
        v = f.get("l_" + slug)
        if v and str(v).isdigit():
            s["lobby"][slug] = max(5, min(300, int(v)))
    DB.save()
    go("/dashboard/games", "تم الحفظ")


@guard
async def upload(request):
    f = await request.post()
    slug, file = f.get("slug"), f.get("file")
    if slug not in {i["slug"] for i in GAMES.values()} or not hasattr(file, "file"):
        go("/dashboard/games", "ملف غير صالح")
    try:
        ImageOps.fit(Image.open(file.file).convert("RGB"), (1000, 540)).save(os.path.join(CUSTOM_DIR, slug + ".png"))
    except Exception:
        go("/dashboard/games", "الصورة غير صالحة")
    go("/dashboard/games", "تم رفع الصورة")


@guard
async def reset_img(request):
    f = await request.post()
    p = os.path.join(CUSTOM_DIR, str(f.get("slug", "")).replace("/", "").replace("\\", "") + ".png")
    if os.path.exists(p):
        os.remove(p)
    go("/dashboard/games", "رجعت الصورة الأصلية")


async def img(request):
    slug = request.match_info["slug"]
    if slug not in {i["slug"] for i in GAMES.values()}:
        raise web.HTTPNotFound()
    return web.FileResponse(game_image(slug))


# ------------------------------------------------------------------ custom questions
@guard
async def questions_page(request):
    custom = DB.d.get("custom", {})
    opts = "".join(f'<option value="{k}">{esc(t)}</option>' for k, (t, _) in QTYPES.items())
    hints = "<br>".join(f"<small>• {esc(t)}: <code>{esc(h)}</code></small>" for t, h in QTYPES.values())
    lists = []
    for k, (title, _) in QTYPES.items():
        items = custom.get(k, [])
        li = "".join(
            f'<tr><td>{esc(" | ".join(x))}</td><td><form method="post" action="/dashboard/q/del"><input type="hidden" name="type" value="{k}">'
            f'<input type="hidden" name="idx" value="{i}"><button class="red">حذف</button></form></td></tr>' for i, x in enumerate(items))
        lists.append(f'<div class="card"><b>{esc(title)}</b> <small>({len(items)} مضافة)</small><table>{li}</table></div>')
    body = f"""<h2>❓ إضافة أسئلة</h2><div class="card"><form method="post" action="/dashboard/q/add">
<label>النوع <select name="type">{opts}</select></label>
<label>السؤال <input name="text" style="width:100%" placeholder="افصل بين الأجزاء بـ |"></label>{hints}<br><br><button>➕ إضافة</button></form></div>{''.join(lists)}"""
    return layout(body, request)


@guard
async def q_add(request):
    f = await request.post()
    t = f.get("type")
    parts = [p.strip() for p in str(f.get("text", "")).split("|") if p.strip()]
    need = 1 if t == "words" else 2
    if t not in QTYPES or len(parts) < need:
        go("/dashboard/questions", "اكتب السؤال بالشكل الصحيح")
    if t == "words":
        parts = parts[:1]
    DB.d.setdefault("custom", {}).setdefault(t, []).append(parts)
    DB.save()
    go("/dashboard/questions", "تمت الإضافة")


@guard
async def q_del(request):
    f = await request.post()
    t, items = f.get("type"), DB.d.get("custom", {})
    try:
        items[t].pop(int(f.get("idx")))
        DB.save()
    except Exception:
        pass
    go("/dashboard/questions", "تم الحذف")


# ------------------------------------------------------------------ server start
async def start_web():
    app = web.Application(client_max_size=10 * 1024 * 1024)
    r = app.router
    r.add_get("/", index)
    r.add_get("/login", login_page)
    r.add_post("/login", login_post)
    r.add_get("/logout", logout)
    r.add_get("/dashboard", home)
    r.add_get("/dashboard/server/{gid}", server_page)
    r.add_post("/dashboard/server/{gid}/save", server_save)
    r.add_post("/dashboard/server/{gid}/points", server_points)
    r.add_post("/dashboard/server/{gid}/reset", server_reset)
    r.add_get("/dashboard/settings", settings_page)
    r.add_post("/dashboard/settings", settings_save)
    r.add_get("/dashboard/games", games_page)
    r.add_post("/dashboard/games", games_save)
    r.add_post("/dashboard/upload", upload)
    r.add_post("/dashboard/reset", reset_img)
    r.add_get("/dashboard/questions", questions_page)
    r.add_post("/dashboard/q/add", q_add)
    r.add_post("/dashboard/q/del", q_del)
    r.add_get("/img/{slug}", img)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "10000"))
    await web.TCPSite(runner, "0.0.0.0", port).start()
    password()
    print(f"WEB SERVER STARTED on port {port}")
