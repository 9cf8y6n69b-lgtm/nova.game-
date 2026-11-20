from common import *
from shopdata import PROPS, UPS, SHOP_IMGS, MAX_PROPS, MAX_IMGS

NOMENTION = discord.AllowedMentions.none()


def daily_left(u):
    return max(0, int(u["daily"] + 86400 - time.time()))


def daily_text(u):
    left = daily_left(u)
    if left <= 0:
        return "متاح الآن ✅"
    h, m = left // 3600, (left % 3600) // 60
    return f"بعد {h} ساعة و{m} دقيقة" if h else f"بعد {m} دقيقة"


# ================================================================ points / top
async def cmd_points(ctx, member=None):
    await ctx.defer()
    member = member or ctx.author
    u = DB.user(ctx.guild.id, member.id)
    av = await avatar_bytes(member)
    buf = await asyncio.to_thread(stats_card, member.display_name, av, u["points"], u["best"])
    await ctx.send(content=member.mention, file=discord.File(buf, "points.png"), allowed_mentions=NOMENTION)


async def cmd_top(ctx):
    await ctx.defer()
    users = DB.guild(ctx.guild.id).get("users", {})
    top = sorted(((int(uid), u) for uid, u in users.items() if u.get("points", 0) > 0), key=lambda x: -x[1]["points"])[:10]
    if not top:
        return await ctx.send(content="ما فيه نقاط للحين 🙂")
    members = [ctx.guild.get_member(uid) for uid, _ in top]
    avs = await asyncio.gather(*[avatar_bytes(m, 64) if m else asyncio.sleep(0, None) for m in members])
    rows = [(k + 1, (m.display_name if m else u.get("name") or str(uid)), u["points"], av)
            for k, ((uid, u), m, av) in enumerate(zip(top, members, avs))]
    buf = await asyncio.to_thread(leaderboard_image, rows)
    await ctx.send(content=ctx.author.mention, file=discord.File(buf, "top.png"), allowed_mentions=NOMENTION)


# ================================================================ coins / daily / transfer
async def cmd_coins(ctx):
    u = DB.user(ctx.guild.id, ctx.author.id)
    names = {k: n for k, n, _ in SHOP_IMGS}
    eq = names.get(u["equip"], "بدون")
    txt = (f"{ctx.author.mention}\n🪙 **العملات:** {u['coins']}\n**اليومي:** {daily_text(u)}\n"
           f"**الصور:** {len(u['imgs'])}/{MAX_IMGS} ({eq})\n**الخصائص:** {len(u['props'])} | **النقاط:** {u['points']}\n"
           f"**الروليت:** {u['rwin']} فوز • {u['rout']} إقصاء")
    await ctx.send(content=txt, allowed_mentions=NOMENTION)


def claim_daily(gid, uid):
    u = DB.user(gid, uid)
    if daily_left(u) > 0:
        return False, f"⏰ المكافأة اليومية {daily_text(u)}"
    amount = int(DB.settings["daily"])
    u["coins"] += amount
    u["daily"] = time.time()
    DB.save()
    return True, f"🎁 استلمت **{amount}** عملات! رصيدك: **{u['coins']}** 🪙"


async def cmd_daily(ctx):
    ok, msg = claim_daily(ctx.guild.id, ctx.author.id)
    await ctx.send(content=f"{ctx.author.mention} {msg}", allowed_mentions=NOMENTION)


async def _move(ctx, member, amount, field, label, unit):
    if member is None or member.bot or member.id == ctx.author.id:
        return await ctx.send(content="حدد لاعب ثاني صحيح (منشن).")
    if not isinstance(amount, int) or amount <= 0:
        return await ctx.send(content="اكتب مبلغ صحيح أكبر من صفر.")
    me = DB.user(ctx.guild.id, ctx.author.id)
    if me[field] < amount:
        return await ctx.send(content=f"رصيدك من {unit} ما يكفي ({me[field]}).")
    other = DB.user(ctx.guild.id, member.id)
    me[field] -= amount
    other[field] += amount
    other["name"] = member.display_name
    DB.save()
    await ctx.send(content=f"✅ {ctx.author.mention} {label} {member.mention} **{amount}** {unit}", allowed_mentions=NOMENTION)


async def cmd_transfer(ctx, member, amount):
    await _move(ctx, member, amount, "points", "حوّل لـ", "نقطة")


async def cmd_give(ctx, member, amount):
    await _move(ctx, member, amount, "coins", "أعطى", "عملة")


# ================================================================ shop
class ShopView(discord.ui.View):
    def __init__(self, owner, mode="props"):
        super().__init__(timeout=300)
        self.owner, self.mode = owner, mode
        self.rebuild()

    def u(self):
        return DB.user(self.owner.guild.id, self.owner.id)

    async def interaction_check(self, i: discord.Interaction):
        if i.user.id != self.owner.id:
            await i.response.send_message("هذا مو متجرك — اكتب `متجر` لفتح متجرك 🛒", ephemeral=True)
            return False
        return True

    # ---- embeds
    def embed(self, note=""):
        u = self.u()
        bal = f"• رصيدك الحالي: 🪙 `{u['coins']}`"
        if self.mode == "props":
            lines = "\n".join(f"• {e} **{n}** (🪙 {p}) — {d}{' ✅' if k in u['props'] else ''}" for k, (n, p, e, d) in PROPS.items())
            body = f"## متجر خصائص الروليت\n> خصائص دائمة تستخدمها في جولات الروليت.\n\n{bal}\n\n## قائمة الخصائص المتاحة:\n{lines}"
        elif self.mode == "ups":
            lines = "\n".join(f"• {e} **{n}** (🪙 {p}) — {d}{' ✅' if k in u['ups'] else ''}" for k, (n, p, e, d) in UPS.items())
            body = f"## متجر التطويرات\n> تطويرات تقوي خصائصك أو تعطيك درع حماية تلقائي في الروليت.\n\n{bal}\n\n## قائمة التطويرات المتاحة:\n{lines}"
        elif self.mode == "imgs":
            lines = "\n".join(f"• 🖼️ **{n}** (🪙 {p}){' ✅' if k in u['imgs'] else ''}" for k, n, p in SHOP_IMGS)
            body = f"## متجر الصور\n> صور إقصاء تظهر لما تطلّع لاعب في الروليت.\n\n{bal}\n\n## الصور المتاحة:\n{lines}"
        else:
            props = "، ".join(PROPS[k][0] for k in u["props"]) or "لا توجد"
            ups = "، ".join(UPS[k][0] for k in u["ups"]) or "لا توجد"
            names = {k: n for k, n, _ in SHOP_IMGS}
            imgs = "، ".join(names[k] for k in u["imgs"] if k in names) or "ما عندك صور للحين، تصفحها من متجر الصور."
            eq = names.get(u["equip"], "لا توجد صورة مفعلة")
            body = (f"## حقيبتي\n• رصيدك من العملات: 🪙 `{u['coins']}`\n• نقاط التصنيف: `{u['points']}`\n"
                    f"• المكافأة اليومية: {daily_text(u)}\n• صورة الإقصاء المفعلة: {eq}\n"
                    f"• إحصائيات الروليت: `{u['rwin']}` فوز • `{u['rout']}` إقصاء\n"
                    f"• الخصائص المملوكة ({len(u['props'])}/{MAX_PROPS}): {props}\n• التطويرات المفعلة: {ups}\n\n"
                    f"## الصور المملوكة ({len(u['imgs'])}/{MAX_IMGS}):\n> {imgs}")
        return discord.Embed(color=COLOR, description=(note + "\n\n" if note else "") + body)

    # ---- components
    def rebuild(self):
        self.clear_items()
        u = self.u()
        if self.mode in ("props", "ups", "imgs"):
            if self.mode == "props":
                items = [(k, n, p, e, d) for k, (n, p, e, d) in PROPS.items() if k not in u["props"]]
                ph = "اختر خاصية للشراء المباشر..."
            elif self.mode == "ups":
                items = [(k, n, p, e, d) for k, (n, p, e, d) in UPS.items() if k not in u["ups"]]
                ph = "اختر تطويراً للشراء والتفعيل..."
            else:
                items = [(k, n, p, "🖼️", "") for k, n, p in SHOP_IMGS if k not in u["imgs"]]
                ph = "اختر صورة للشراء..."
            if items:
                sel = discord.ui.Select(placeholder=ph, options=[
                    discord.SelectOption(label=f"{n} ({p} عملة)", value=k, emoji=e, description=(d or None) and d[:90]) for k, n, p, e, d in items][:25])

                async def buy_cb(i: discord.Interaction, sel=sel):
                    note = self.buy(sel.values[0])
                    self.rebuild()
                    await i.response.edit_message(embed=self.embed(note), view=self)

                sel.callback = buy_cb
                self.add_item(sel)
        else:
            names = {k: n for k, n, _ in SHOP_IMGS}
            opts = [discord.SelectOption(label="بدون صورة", value="none", emoji="❌")] + [
                discord.SelectOption(label=names[k], value=k, emoji="🖼️") for k in u["imgs"] if k in names]
            sel = discord.ui.Select(placeholder="اختر صورة الإقصاء المفعلة...", options=opts[:25])

            async def equip_cb(i: discord.Interaction, sel=sel):
                v = sel.values[0]
                self.u()["equip"] = None if v == "none" else v
                DB.save()
                self.rebuild()
                await i.response.edit_message(embed=self.embed("✅ تم تغيير الصورة المفعلة"), view=self)

            sel.callback = equip_cb
            self.add_item(sel)
            if daily_left(u) <= 0:
                b = discord.ui.Button(label=f"استلام المكافأة (+{DB.settings['daily']})", emoji="⭐", style=discord.ButtonStyle.success)

                async def daily_cb(i: discord.Interaction):
                    ok, msg = claim_daily(self.owner.guild.id, self.owner.id)
                    self.rebuild()
                    await i.response.edit_message(embed=self.embed(msg), view=self)

                b.callback = daily_cb
                self.add_item(b)
        for mode, label, emoji in (("imgs", "متجر الصور", "🏬"), ("props", "متجر الخصائص", "⚔️"),
                                   ("ups", "التطويرات", "🛡️"), ("bag", f"حقيبتي ({len(u['props']) + len(u['ups']) + len(u['imgs'])})", "👜")):
            if mode == self.mode:
                continue
            b = discord.ui.Button(label=label, emoji=emoji, style=discord.ButtonStyle.secondary)

            async def go(i: discord.Interaction, mode=mode):
                self.mode = mode
                self.rebuild()
                await i.response.edit_message(embed=self.embed(), view=self)

            b.callback = go
            self.add_item(b)

    def buy(self, key):
        u = self.u()
        if self.mode == "props":
            name, price = PROPS[key][0], PROPS[key][1]
            owned, limit = u["props"], MAX_PROPS
        elif self.mode == "ups":
            name, price = UPS[key][0], UPS[key][1]
            owned, limit = u["ups"], 99
        else:
            _, name, price = next(x for x in SHOP_IMGS if x[0] == key)
            owned, limit = u["imgs"], MAX_IMGS
        if key in owned:
            return "عندك هالعنصر أصلاً."
        if len(owned) >= limit:
            return "وصلت للحد الأقصى."
        if u["coins"] < price:
            return f"❌ رصيدك ما يكفي لشراء **{name}** (يلزم {price} 🪙)"
        u["coins"] -= price
        owned.append(key)
        DB.save()
        return f"✅ اشتريت **{name}** بـ {price} 🪙"


async def cmd_shop(ctx, mode="props"):
    v = ShopView(ctx.author, mode)
    await ctx.send(content=ctx.author.mention, embed=v.embed(), view=v, allowed_mentions=NOMENTION)


async def cmd_bag(ctx):
    await cmd_shop(ctx, "bag")


# ================================================================ event
class PointsModal(discord.ui.Modal, title="نقاط الفائز"):
    pts = discord.ui.TextInput(label="عدد النقاط (5 على الأقل)", default="5", max_length=5)

    def __init__(self, view):
        super().__init__()
        self.v = view

    async def on_submit(self, i: discord.Interaction):
        try:
            n = int(norm(self.pts.value))
        except ValueError:
            return await i.response.send_message("اكتب رقم صحيح", ephemeral=True)
        if n < 5:
            return await i.response.send_message("الحد الأدنى 5 نقاط", ephemeral=True)
        self.v.points = n
        await i.response.edit_message(embed=self.v.embed(), view=self.v)


class EventView(discord.ui.View):
    def __init__(self, owner, channel):
        super().__init__(timeout=300)
        self.owner, self.channel, self.game, self.points = owner, channel, None, 5
        names = [n for n in GAMES if n != "تصويت"][:25]
        sel = discord.ui.Select(placeholder="اختر اللعبة الفعالية...",
                                options=[discord.SelectOption(label=n, description=GAMES[n]["title"][:90]) for n in names])

        async def pick(i: discord.Interaction):
            self.game = sel.values[0]
            await i.response.edit_message(embed=self.embed(), view=self)

        sel.callback = pick
        self.add_item(sel)

    async def interaction_check(self, i: discord.Interaction):
        if i.user.id != self.owner.id:
            await i.response.send_message("هذي فعالية غيرك", ephemeral=True)
            return False
        return True

    def embed(self):
        return discord.Embed(
            title="🎮 إنشاء ايفنت ألعاب", color=COLOR,
            description=(f"يرجى اختيار اللعبة التي تريد تشغيلها ايفنت\nالحد الأدنى للنقاط **5** نقاط\n\n"
                         f"🕹️ اللعبة: **{self.game or 'لم تُحدد'}**\n⭐ نقاط الفائز: **{self.points}**"))

    @discord.ui.button(label="تحديد النقاط", emoji="⭐", style=discord.ButtonStyle.secondary)
    async def set_points(self, i: discord.Interaction, b: discord.ui.Button):
        await i.response.send_modal(PointsModal(self))

    @discord.ui.button(label="بدء الفعالية", emoji="🚀", style=discord.ButtonStyle.success)
    async def start(self, i: discord.Interaction, b: discord.ui.Button):
        if not self.game:
            return await i.response.send_message("اختر اللعبة أولاً", ephemeral=True)
        err = await launch(self.channel, self.owner, self.game, event_points=self.points)
        if err:
            return await i.response.send_message(err, ephemeral=True)
        for c in self.children:
            c.disabled = True
        self.stop()
        await i.response.edit_message(embed=discord.Embed(
            title="🎉 بدأت الفعالية", color=COLOR,
            description=f"🕹️ **{self.game}** — الفائز يحصل على **{self.points}** نقطة"), view=self)


async def cmd_event(ctx):
    if not can_start(ctx.author):
        return await ctx.send(content="ما عندك صلاحية تسوي ايفنت 🚫")
    v = EventView(ctx.author, ctx.channel)
    await ctx.send(embed=v.embed(), view=v)


# ================================================================ أزرار اللوبي (المتجر / الحقيبة) من لوبي الروليت
async def _hook_shop(i, mode="props"):
    v = ShopView(i.user, mode)
    await i.response.send_message(embed=v.embed(), view=v, ephemeral=True)


async def _hook_bag(i):
    await _hook_shop(i, "bag")


HOOKS["shop"] = _hook_shop
HOOKS["bag"] = _hook_bag
