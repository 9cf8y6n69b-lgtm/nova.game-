import os
import asyncio

import discord
from discord import app_commands

from common import *
import games_solo  # noqa: F401  (يسجّل الألعاب الفردية)
import games_group  # noqa: F401  (يسجّل ألعاب السيرفر)
from economy import (cmd_points, cmd_top, cmd_coins, cmd_daily, cmd_transfer, cmd_give, cmd_shop, cmd_bag, cmd_event)
from dashboard import start_web, password, base_url, invite_url

TOKEN = os.getenv("DISCORD_TOKEN")
SOLO_ORDER = ["اسرع", "فكك", "شركة", "اشبك", "صحح", "اعكس", "عكس", "جمع", "مفرد", "حرف", "اعلام", "عواصم", "ضرب", "طرح", "ادمج"]
GROUP_ORDER = ["روليت", "هايد", "لغم", "وصل", "مافيا", "كراسي", "اكس", "حجره", "تصويت"]
SOLO = [n for n in SOLO_ORDER if n in GAMES]
GROUP = [n for n in GROUP_ORDER if n in GAMES]
NOMENTION = discord.AllowedMentions.none()


# ================================================================ status
STATES = {"online": discord.Status.online, "idle": discord.Status.idle,
          "dnd": discord.Status.dnd, "invisible": discord.Status.invisible}


async def apply_status():
    s = DB.d.get("status", {"text": "NOVA STORE Games 🎮", "state": "online", "activity": "playing"})
    AT = discord.ActivityType
    kinds = {
        "playing": discord.Game(s["text"]),
        "watching": discord.Activity(type=AT.watching, name=s["text"]),
        "listening": discord.Activity(type=AT.listening, name=s["text"]),
        "competing": discord.Activity(type=AT.competing, name=s["text"]),
    }
    await bot.change_presence(status=STATES[s["state"]], activity=kinds[s["activity"]])


# ================================================================ help
def games_text():
    other = ["متجر", "عملات", "يومي", "توب", "نقاطي", "تحويل", "اعطاء", "ايفنت", "ايقاف"]
    return ("## الألعاب الفردية\n" + "\n".join(f"-{n}" for n in SOLO)
            + "\n## الألعاب الجماعية\n" + "\n".join(f"-{n}" for n in GROUP)
            + "\n## أوامر أخرى\n" + "\n".join(f"-{n}" for n in other))


# ================================================================ text commands
def parse_amount(args):
    for a in args:
        n = norm(a)
        if n.isdigit():
            return int(n)
    return None


async def t_points(ctx, msg, args):
    await cmd_points(ctx, msg.mentions[0] if msg.mentions else None)


async def t_transfer(ctx, msg, args):
    await cmd_transfer(ctx, msg.mentions[0] if msg.mentions else None, parse_amount(args))


async def t_give(ctx, msg, args):
    await cmd_give(ctx, msg.mentions[0] if msg.mentions else None, parse_amount(args))


async def t_stop(ctx, msg, args):
    await ctx.send(content=await stop_game(msg.channel, msg.author))


async def t_prefix(ctx, msg, args):
    if not msg.author.guild_permissions.manage_guild:
        return await ctx.send(content="تحتاج صلاحية Manage Server")
    cfg = DB.guild(msg.guild.id)
    if not args:
        return await ctx.send(content=f"البيرفكس الحالي: `{cfg.get('prefix') or 'بدون'}`\nلتغييره: `بيرفكس !` — للحذف: `بيرفكس حذف`")
    cfg["prefix"] = "" if norm(args[0]) in ("حذف", "بدون", "-", "لا") else args[0][:5]
    DB.save()
    await ctx.send(content=f"✅ البيرفكس الآن: `{cfg['prefix'] or 'بدون'}`")


async def t_dash(ctx, msg, args):
    if not msg.author.guild_permissions.manage_guild:
        return await ctx.send(content="تحتاج صلاحية Manage Server")
    try:
        await msg.author.send(f"🔗 {base_url()}/login\n🔑 كلمة السر: `{password()}`")
        await ctx.send(content="📩 أرسلت لك رابط اللوحة وكلمة السر خاص")
    except discord.HTTPException:
        await ctx.send(content="ما قدرت أرسل لك خاص، افتح الخاص أو استخدم `/dashboard`")


async def t_games(ctx, msg, args):
    await ctx.send(content=games_text())


TEXT = {
    "نقاطي": t_points, "توب": lambda c, m, a: cmd_top(c), "عملات": lambda c, m, a: cmd_coins(c),
    "يومي": lambda c, m, a: cmd_daily(c), "تحويل": t_transfer, "اعطاء": t_give,
    "متجر": lambda c, m, a: cmd_shop(c), "حقيبتي": lambda c, m, a: cmd_bag(c),
    "ايفنت": lambda c, m, a: cmd_event(c), "ايقاف": t_stop, "العاب": t_games,
    "بيرفكس": t_prefix, "بادئة": t_prefix, "لوحة": t_dash,
}
RESERVED.update(norm(k) for k in TEXT)


@bot.event
async def on_message(msg: discord.Message):
    if msg.author.bot or not msg.guild:
        return
    txt = msg.content.strip()
    mentioned = False  # منشن البوت يشتغل دائماً حتى لو نسيت البيرفكس
    if bot.user:
        for m in (f"<@{bot.user.id}>", f"<@!{bot.user.id}>"):
            if txt.startswith(m):
                txt, mentioned = txt[len(m):].strip(), True
                break
    pre = DB.guild(msg.guild.id).get("prefix", "")
    if pre and not mentioned:
        if not txt.startswith(pre):
            return
        txt = txt[len(pre):].strip()
    if not txt:
        return
    parts = txt.split()
    first = norm(parts[0])
    if len(parts) == 1:
        name = resolve(parts[0])
        if name:
            err = await launch(msg.channel, msg.author, name)
            if err:
                await msg.reply(err, mention_author=False)
            return
    handler = TEXT.get(first)
    if handler:
        try:
            await handler(Ctx(msg), msg, parts[1:])
        except Exception:
            import traceback
            traceback.print_exc()


# ================================================================ lifecycle
@bot.event
async def setup_hook():
    await start_web()
    await bot.tree.sync()


@bot.event
async def on_ready():
    await apply_status()
    flags = len(os.listdir(os.path.join(IMG_DIR, "flags"))) if os.path.isdir(os.path.join(IMG_DIR, "flags")) else 0
    print(f"Logged in as {bot.user} | flags on disk: {flags}")
    print("INVITE:", invite_url())


# ================================================================ slash: games
async def slash_launch(inter: discord.Interaction, name):
    err = await launch(inter.channel, inter.user, name)
    await inter.response.send_message(err or f"🎮 بدأت لعبة **{name}**", ephemeral=bool(err))


@bot.tree.command(name="games", description="الألعاب الجماعية")
@app_commands.choices(game=[app_commands.Choice(name=n, value=n) for n in GROUP])
async def games(inter: discord.Interaction, game: app_commands.Choice[str]):
    await slash_launch(inter, game.value)


@bot.tree.command(name="solo", description="الألعاب الفردية")
@app_commands.choices(game=[app_commands.Choice(name=n, value=n) for n in SOLO])
async def solo_cmd(inter: discord.Interaction, game: app_commands.Choice[str]):
    await slash_launch(inter, game.value)


@bot.tree.command(name="stop", description="إيقاف اللعبة الشغالة")
async def stop_cmd(inter: discord.Interaction):
    await inter.response.send_message(await stop_game(inter.channel, inter.user))


@bot.tree.command(name="help", description="قائمة الألعاب والأوامر")
async def help_cmd(inter: discord.Interaction):
    await inter.response.send_message(content=games_text())


@bot.tree.command(name="event", description="إنشاء ايفنت ألعاب")
async def event_cmd(inter: discord.Interaction):
    await cmd_event(Ctx(inter))


# ================================================================ slash: economy
@bot.tree.command(name="points", description="نقاطك وأسرع زمن")
async def points_cmd(inter: discord.Interaction, member: discord.Member = None):
    await cmd_points(Ctx(inter), member)


@bot.tree.command(name="top", description="توب النقاط")
async def top_cmd(inter: discord.Interaction):
    await cmd_top(Ctx(inter))


@bot.tree.command(name="coins", description="رصيدك من العملات")
async def coins_cmd(inter: discord.Interaction):
    await cmd_coins(Ctx(inter))


@bot.tree.command(name="daily", description="المكافأة اليومية")
async def daily_cmd(inter: discord.Interaction):
    await cmd_daily(Ctx(inter))


@bot.tree.command(name="shop", description="متجر الروليت")
async def shop_cmd(inter: discord.Interaction):
    await cmd_shop(Ctx(inter))


@bot.tree.command(name="bag", description="حقيبتي")
async def bag_cmd(inter: discord.Interaction):
    await cmd_bag(Ctx(inter))


@bot.tree.command(name="transfer", description="تحويل نقاط للاعب")
async def transfer_cmd(inter: discord.Interaction, member: discord.Member, amount: int):
    await cmd_transfer(Ctx(inter), member, amount)


@bot.tree.command(name="give", description="إعطاء عملات للاعب")
async def give_cmd(inter: discord.Interaction, member: discord.Member, amount: int):
    await cmd_give(Ctx(inter), member, amount)


# ================================================================ slash: admin
def is_admin(inter):
    return inter.user.guild_permissions.manage_guild


async def need_admin(inter):
    await inter.response.send_message("تحتاج صلاحية Manage Server", ephemeral=True)


@bot.tree.command(name="setprefix", description="حدد بادئة أوامر الألعاب (فاضي = بدون بادئة)")
async def setprefix(inter: discord.Interaction, prefix: str = ""):
    if not is_admin(inter):
        return await need_admin(inter)
    DB.guild(inter.guild_id)["prefix"] = prefix.strip()
    DB.save()
    await inter.response.send_message(f"✅ البادئة: `{prefix.strip() or 'بدون'}`")


@bot.tree.command(name="setrole", description="حدد الرتبة اللي تقدر تشغّل الألعاب")
async def setrole(inter: discord.Interaction, role: discord.Role):
    if not is_admin(inter):
        return await need_admin(inter)
    DB.guild(inter.guild_id)["role"] = role.id
    DB.save()
    await inter.response.send_message(f"✅ الحين بس {role.mention} (والإدارة) يشغّلون الألعاب", allowed_mentions=NOMENTION)


@bot.tree.command(name="clearrole", description="السماح للجميع بتشغيل الألعاب")
async def clearrole(inter: discord.Interaction):
    if not is_admin(inter):
        return await need_admin(inter)
    DB.guild(inter.guild_id).pop("role", None)
    DB.save()
    await inter.response.send_message("✅ الكل يقدر يشغّل الألعاب")


@bot.tree.command(name="addpoints", description="إضافة نقاط للاعب (سالب للخصم)")
async def addpoints(inter: discord.Interaction, member: discord.Member, amount: int):
    if not is_admin(inter):
        return await need_admin(inter)
    u = DB.user(inter.guild_id, member.id)
    u["points"] = max(0, u["points"] + amount)
    u["name"] = member.display_name
    DB.save()
    await inter.response.send_message(f"✅ نقاط {member.mention} الآن: **{u['points']}**", allowed_mentions=NOMENTION)


@bot.tree.command(name="addcoins", description="إضافة عملات للاعب (سالب للخصم)")
async def addcoins(inter: discord.Interaction, member: discord.Member, amount: int):
    if not is_admin(inter):
        return await need_admin(inter)
    u = DB.user(inter.guild_id, member.id)
    u["coins"] = max(0, u["coins"] + amount)
    DB.save()
    await inter.response.send_message(f"✅ عملات {member.mention} الآن: **{u['coins']}**", allowed_mentions=NOMENTION)


@bot.tree.command(name="resetpoints", description="تصفير نقاط لاعب (أو كل السيرفر لو ما حددت)")
async def resetpoints(inter: discord.Interaction, member: discord.Member = None):
    if not is_admin(inter):
        return await need_admin(inter)
    users = DB.guild(inter.guild_id).get("users", {})
    if member:
        DB.user(inter.guild_id, member.id)["points"] = 0
        msg = f"✅ تم تصفير نقاط {member.mention}"
    else:
        for u in users.values():
            u["points"] = 0
        msg = "✅ تم تصفير نقاط كل السيرفر"
    DB.save()
    await inter.response.send_message(msg, allowed_mentions=NOMENTION)


@bot.tree.command(name="setstatus", description="غيّر حالة البوت")
@app_commands.describe(text="نص الحالة", state="الحالة", activity="نوع النشاط")
@app_commands.choices(
    state=[app_commands.Choice(name=a, value=b) for a, b in
           (("متصل", "online"), ("خامل", "idle"), ("مشغول", "dnd"), ("غير مرئي", "invisible"))],
    activity=[app_commands.Choice(name=a, value=b) for a, b in
              (("يلعب", "playing"), ("يشاهد", "watching"), ("يستمع", "listening"), ("يتنافس", "competing"))],
)
async def setstatus(inter: discord.Interaction, text: str, state: app_commands.Choice[str] = None,
                    activity: app_commands.Choice[str] = None):
    if not inter.user.guild_permissions.administrator:
        return await inter.response.send_message("للإدارة فقط", ephemeral=True)
    DB.d["status"] = {"text": text[:100], "state": state.value if state else "online",
                      "activity": activity.value if activity else "playing"}
    DB.save()
    await apply_status()
    await inter.response.send_message("✅ تم تغيير حالة البوت", ephemeral=True)


@bot.tree.command(name="dashboard", description="رابط لوحة التحكم وكلمة السر")
async def dashboard_cmd(inter: discord.Interaction):
    if not is_admin(inter):
        return await need_admin(inter)
    await inter.response.send_message(f"🔗 {base_url()}/login\n🔑 كلمة السر: `{password()}`", ephemeral=True)


if __name__ == "__main__":
    if not TOKEN:
        raise SystemExit("حط التوكن: export DISCORD_TOKEN=xxxx")
    bot.run(TOKEN)
