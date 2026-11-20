from common import *
from shopdata import PROPS

# ================================================================ XO
LINES = [
    [(0, 0), (1, 0), (2, 0)], [(0, 1), (1, 1), (2, 1)], [(0, 2), (1, 2), (2, 2)],
    [(0, 0), (0, 1), (0, 2)], [(1, 0), (1, 1), (1, 2)], [(2, 0), (2, 1), (2, 2)],
    [(0, 0), (1, 1), (2, 2)], [(2, 0), (1, 1), (0, 2)],
]


def _winner(c):
    for L in LINES:
        t = c.get(L[0])
        if t is not None and all(c.get(p) == t for p in L):
            return t
    return None


def _mm(c, turn):
    """نتيجة اللعب المثالي من منظور البوت (1): +1 فوز / 0 تعادل / -1 خسارة"""
    w = _winner(c)
    if w == 1:
        return 1
    if w == 0:
        return -1
    if len(c) == 9:
        return 0
    scores = []
    for pos in [(x, y) for x in range(3) for y in range(3) if (x, y) not in c]:
        c[pos] = turn
        scores.append(_mm(c, 1 - turn))
        del c[pos]
    return max(scores) if turn == 1 else min(scores)


class Cell(discord.ui.Button):
    def __init__(self, x, y):
        super().__init__(label="\u200b", style=discord.ButtonStyle.secondary, row=y)
        self.pos = (x, y)

    async def callback(self, i: discord.Interaction):
        v: "TTT" = self.view
        if i.user != v.p[v.turn]:
            return await i.response.send_message("مو دورك ✋", ephemeral=True)
        v.play(self.pos)
        if v.result is None and v.p[v.turn] == BOT:
            v.play(v.bot_pos())
        v.refresh()
        await i.response.edit_message(embed=v.emb(), view=v)
        v.moved.set()


class TTT(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=None)
        self.p, self.turn, self.cells, self.result = [p1, p2], 0, {}, None
        self.moved = asyncio.Event()
        self.btn = {}
        for y in range(3):
            for x in range(3):
                b = Cell(x, y)
                self.btn[(x, y)] = b
                self.add_item(b)

    def play(self, pos):
        t = self.turn
        self.cells[pos] = t
        if any(all(self.cells.get(c) == t for c in L) for L in LINES):
            self.result = t
        elif len(self.cells) == 9:
            self.result = -1
        else:
            self.turn = 1 - t

    def bot_pos(self):
        free = [(x, y) for x in range(3) for y in range(3) if (x, y) not in self.cells]
        best, cand = None, []
        for pos in free:
            c = dict(self.cells)
            c[pos] = 1
            sc = _mm(c, 0)
            if best is None or sc > best:
                best, cand = sc, [pos]
            elif sc == best:
                cand.append(pos)
        return random.choice(cand)

    def refresh(self):
        for pos, b in self.btn.items():
            if pos in self.cells:
                t = self.cells[pos]
                b.label = "X" if t == 0 else "O"
                b.style = discord.ButtonStyle.danger if t == 0 else discord.ButtonStyle.success
                b.disabled = True
        if self.result is not None:
            for b in self.btn.values():
                b.disabled = True

    def emb(self):
        p0, p1 = self.p
        if self.result is None:
            st = f"دور: {self.p[self.turn].mention} ({'❌' if self.turn == 0 else '⭕'})"
        elif self.result == -1:
            st = "🤝 تعادل!"
        else:
            st = f"🏆 الفائز: {self.p[self.result].mention}"
        return mk("❌⭕ اكس او", f"{p0.mention} ❌  🆚  {p1.mention} ⭕\n\n{st}")


async def turn_loop(g, v, m):
    """ينتظر الحركات؛ اللي ما يتحرك خلال الوقت ينسحب"""
    while v.result is None:
        v.moved.clear()
        try:
            await asyncio.wait_for(v.moved.wait(), g.T())
        except asyncio.TimeoutError:
            loser = v.turn
            v.result = 1 - loser
            v.refresh()
            await m.edit(embed=v.emb(), view=v)
            await say(g, "⏰ انسحاب", f"{v.p[loser].mention} ما تفاعل فخسر.")
            break


class XOMode(discord.ui.View):
    def __init__(self, owner):
        super().__init__(timeout=None)
        self.owner, self.mode, self.ev = owner, None, asyncio.Event()

    async def interaction_check(self, i: discord.Interaction):
        if i.user != self.owner:
            await i.response.send_message("بس اللي شغّل اللعبة يختار الوضع", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="لعب ضد شخص", emoji="👥", style=discord.ButtonStyle.secondary)
    async def person(self, i: discord.Interaction, b: discord.ui.Button):
        self.mode = "person"
        await i.response.defer()
        self.ev.set()

    @discord.ui.button(label="لعب ضد ذكاء اصطناعي", emoji="🤖", style=discord.ButtonStyle.primary)
    async def ai(self, i: discord.Interaction, b: discord.ui.Button):
        self.mode = "ai"
        await i.response.defer()
        self.ev.set()


@game("اكس", "xo", "❌⭕ اكس او", "group", 60)
async def g_xo(g):
    v = XOMode(g.starter)
    e = discord.Embed(title="🎮 لعبة XO - اختر وضع اللعب", description="اختر كيف تريد أن تلعب:", color=COLOR)
    e.set_footer(text="اختر الوضع المناسب لك!")
    if bot.user:
        e.set_thumbnail(url=bot.user.display_avatar.url)
    m = await g.channel.send(embed=e, view=v)
    g.views.append((v, m))
    try:
        await asyncio.wait_for(v.ev.wait(), 60)
    except asyncio.TimeoutError:
        return await close(m, v)
    await close(m, v)
    if v.mode == "ai":
        pl = [g.starter, BOT]
    else:
        pl = await lobby(g, "", 2, 2, 30, prejoin=True)
        if not pl:
            return
    v = TTT(pl[0], pl[1])
    m = await g.channel.send(embed=v.emb(), view=v)
    g.views.append((v, m))
    await turn_loop(g, v, m)
    if v.result in (0, 1):
        await finish(g, [v.p[v.result]], 1, 3)
    elif v.result == -1:
        await say(g, "🤝 تعادل", "ما فيه فائز.")


# ================================================================ حجره ورقه مقص (بطولة إقصائية)
RPS = {"🪨": "حجر", "📄": "ورقة", "✂️": "مقص"}
BEATS = {"🪨": "✂️", "📄": "🪨", "✂️": "📄"}


class RoundBtn(discord.ui.Button):
    def __init__(self, e):
        super().__init__(emoji=e, label=RPS[e], style=discord.ButtonStyle.primary)
        self.pick = e

    async def callback(self, i: discord.Interaction):
        v: "RoundView" = self.view
        if i.user.id not in v.ids:
            return await i.response.send_message("انت مو في هالجولة", ephemeral=True)
        if i.user.id in v.picks:
            return await i.response.send_message("اخترت أصلاً", ephemeral=True)
        v.picks[i.user.id] = self.pick
        await i.response.send_message(f"اخترت {self.pick}", ephemeral=True)
        if len(v.picks) >= len(v.ids):
            v.ev.set()


class RoundView(discord.ui.View):
    def __init__(self, ids):
        super().__init__(timeout=None)
        self.ids, self.picks, self.ev = ids, {}, asyncio.Event()
        for e in RPS:
            self.add_item(RoundBtn(e))


@game("حجره", "rps", "✊ حجرة ورقة مقص", "group", 20)
async def g_rps(g):
    pl = await lobby(g, "", 2, 10, 10)
    if not pl:
        return
    alive, rnd = pl[:], 1
    while len(alive) > 1:
        random.shuffle(alive)
        bye = alive.pop() if len(alive) % 2 else None
        pairs = [(alive[i], alive[i + 1]) for i in range(0, len(alive), 2)]
        winners = [bye] if bye else []
        for attempt in range(1, 4):
            if not pairs:
                break
            v = RoundView({p.id for pr in pairs for p in pr})
            lines = "\n".join(f"• {a.mention} 🆚 {b.mention}" for a, b in pairs)
            if bye and attempt == 1:
                lines += f"\n🎁 {bye.mention} تأهل تلقائياً"
            title = f"✊ الجولة {rnd}" + (f" (إعادة {attempt - 1})" if attempt > 1 else "")
            m = await say(g, title, f"{lines}\n\nكل لاعب يختار ({g.T()} ثانية)", view=v)
            try:
                await asyncio.wait_for(v.ev.wait(), g.T())
            except asyncio.TimeoutError:
                pass
            await close(m, v)
            tied, res = [], []
            for a, b in pairs:
                pa, pb = v.picks.get(a.id), v.picks.get(b.id)
                if pa is None and pb is None:
                    if DB.settings["afk_kick"]:
                        res.append(f"🚪 {a.mention} و {b.mention} ما تفاعلوا — طلعوا الاثنين")
                    else:
                        w = random.choice([a, b])
                        winners.append(w)
                        res.append(f"⏰ ما تفاعلوا — تأهل {w.mention} بالقرعة")
                elif pa is None:
                    winners.append(b)
                    res.append(f"🚪 {a.mention} ما تفاعل → تأهل {b.mention}")
                elif pb is None:
                    winners.append(a)
                    res.append(f"🚪 {b.mention} ما تفاعل → تأهل {a.mention}")
                elif pa == pb:
                    tied.append((a, b))
                    res.append(f"🤝 {a.mention} {pa} = {pb} {b.mention} (تعادل)")
                else:
                    w = a if BEATS[pa] == pb else b
                    winners.append(w)
                    res.append(f"{a.mention} {pa} 🆚 {pb} {b.mention} → 🏆 {w.mention}")
            await say(g, "📊 النتائج", "\n".join(res))
            pairs = tied
            await asyncio.sleep(2)
        for a, b in pairs:
            winners.append(random.choice([a, b]))
        alive, rnd = winners, rnd + 1
    if not alive:
        return await say(g, "🏁", "ما بقي أحد!")
    await say(g, "🏆 الفائز", f"{alive[0].mention} آخر لاعب بقي!")
    await finish(g, [alive[0]], 1, 3)


# ================================================================ وصل (أربعة في صف)
ROWS, COLS = 6, 7


class ColBtn(discord.ui.Button):
    def __init__(self, c):
        super().__init__(label=str(c + 1), style=discord.ButtonStyle.primary, row=c // 4)
        self.c = c

    async def callback(self, i: discord.Interaction):
        v: "C4" = self.view
        if i.user != v.p[v.turn]:
            return await i.response.send_message("مو دورك ✋", ephemeral=True)
        if not v.drop(self.c):
            return await i.response.send_message("العمود ممتلئ", ephemeral=True)
        await i.response.edit_message(embed=v.emb(), view=v)
        v.moved.set()


class C4(discord.ui.View):
    def __init__(self, p1, p2):
        super().__init__(timeout=None)
        self.p, self.turn, self.result = [p1, p2], 0, None
        self.board = [[None] * COLS for _ in range(ROWS)]
        self.moved = asyncio.Event()
        for c in range(COLS):
            self.add_item(ColBtn(c))

    def won(self, r, c, t):
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            cnt = 1
            for s in (1, -1):
                rr, cc = r + dr * s, c + dc * s
                while 0 <= rr < ROWS and 0 <= cc < COLS and self.board[rr][cc] == t:
                    cnt += 1
                    rr, cc = rr + dr * s, cc + dc * s
            if cnt >= 4:
                return True
        return False

    def drop(self, c):
        for r in range(ROWS - 1, -1, -1):
            if self.board[r][c] is None:
                t = self.turn
                self.board[r][c] = t
                if self.won(r, c, t):
                    self.result = t
                elif all(self.board[0][k] is not None for k in range(COLS)):
                    self.result = -1
                else:
                    self.turn = 1 - t
                if self.board[0][c] is not None:
                    self.children[c].disabled = True
                if self.result is not None:
                    for ch in self.children:
                        ch.disabled = True
                return True
        return False

    def emb(self):
        sym = {None: "⚫", 0: "🔴", 1: "🟡"}
        grid = "\n".join("".join(sym[x] for x in row) for row in self.board)
        grid += "\n" + "".join(["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"])
        if self.result is None:
            st = f"دور: {self.p[self.turn].mention} ({sym[self.turn]})"
        elif self.result == -1:
            st = "🤝 تعادل!"
        else:
            st = f"🏆 الفائز: {self.p[self.result].mention}"
        return mk("🔴🟡 وصل", f"{self.p[0].mention} 🔴  🆚  {self.p[1].mention} 🟡\n\n{grid}\n\n{st}")


@game("وصل", "connect", "🔴🟡 وصل", "group", 60)
async def g_connect(g):
    pl = await lobby(g, "", 2, 2, 30, prejoin=True)
    if not pl:
        return
    v = C4(pl[0], pl[1])
    m = await g.channel.send(embed=v.emb(), view=v)
    g.views.append((v, m))
    await turn_loop(g, v, m)
    if v.result in (0, 1):
        await finish(g, [v.p[v.result]], 1, 3)
    elif v.result == -1:
        await say(g, "🤝 تعادل", "ما فيه فائز.")


# ================================================================ لغم
class MineBtn(discord.ui.Button):
    def __init__(self, k):
        super().__init__(label="❓", style=discord.ButtonStyle.secondary, row=k // 5)
        self.k = k

    async def callback(self, i: discord.Interaction):
        v: "MineView" = self.view
        if i.user != v.cur:
            return await i.response.send_message("مو دورك ✋", ephemeral=True)
        if self.k == v.mine:
            v.boom = True
            self.label, self.style = "💣", discord.ButtonStyle.danger
        else:
            self.label, self.style = "✅", discord.ButtonStyle.success
        self.disabled = True
        if v.boom:
            for c in v.children:
                c.disabled = True
        await i.response.edit_message(view=v)
        v.ev.set()


class MineView(discord.ui.View):
    def __init__(self, mine):
        super().__init__(timeout=None)
        self.mine, self.cur, self.boom, self.ev = mine, None, False, asyncio.Event()
        self.btns = [MineBtn(k) for k in range(20)]
        for b in self.btns:
            self.add_item(b)


@game("لغم", "mine", "💣 لغم", "group", 30)
async def g_mine(g):
    pl = await lobby(g, "", 2, 15, 30)
    if not pl:
        return
    alive = pl[:]
    random.shuffle(alive)
    rnd = 1
    while len(alive) > 1:
        v = MineView(random.randrange(20))
        m = await say(g, f"💣 الجولة {rnd}", "جاهزين...", view=v)
        idx, skips = 0, 0
        while True:
            cur = alive[idx % len(alive)]
            v.cur = cur
            v.ev.clear()
            await m.edit(embed=mk(f"💣 الجولة {rnd}", f"دور {cur.mention} — اختر مربع ({g.T()} ثانية)"))
            try:
                await asyncio.wait_for(v.ev.wait(), g.T())
            except asyncio.TimeoutError:
                if DB.settings["afk_kick"]:
                    out, reason = cur, "ما تفاعل 🚪"
                    break
                skips += 1
                if skips >= len(alive) * 2:
                    return await say(g, "⏰", "ما أحد تفاعل، انتهت اللعبة.")
                idx += 1
                continue
            skips = 0
            if v.boom:
                out, reason = cur, "داس على اللغم 💥"
                break
            idx += 1
        v.btns[v.mine].label, v.btns[v.mine].style = "💣", discord.ButtonStyle.danger
        await close(m, v)
        alive.remove(out)
        await say(g, "💥 إقصاء", f"{out.mention} {reason}\nالباقين: {len(alive)}")
        rnd += 1
        await asyncio.sleep(2)
    await finish(g, [alive[0]], 1, 3)


# ================================================================ روليت
@game("روليت", "roulette", "🎡 روليت", "group", 30)
async def g_roulette(g):
    pl = await lobby(g, "", 3, 20, 60)
    if not pl:
        return
    gid = g.gid
    alive = {p.id: p for p in pl}
    dead = {}
    nums = {p.id: k + 1 for k, p in enumerate(random.sample(pl, len(pl)))}
    prof = {p.id: DB.user(gid, p.id) for p in pl}
    owned = {p.id: set(prof[p.id]["props"]) for p in pl}
    ups = {p.id: set(prof[p.id]["ups"]) for p in pl}
    used = {p.id: set() for p in pl}
    shield = {p.id for p in pl if "shield" in ups[p.id]}
    hidden, blocked, pending, links, hack = set(), {}, {}, {}, [None]
    S = {"done": None, "chooser": None}

    def kill(uid, pierce=False, by=None):
        if uid not in alive:
            return None
        if uid in shield and not pierce:
            shield.discard(uid)
            return f"🛡️ درع {alive[uid].mention} صدّ الإقصاء!"
        m = alive.pop(uid)
        dead[uid] = m
        if by in prof:
            prof[by]["rout"] += 1
        txt = f"💥 طلع {m.mention}"
        lk = links.pop(uid, None)
        if lk is not None and lk in alive:
            m2 = alive.pop(lk)
            dead[lk] = m2
            txt += f" وسحب معه {m2.mention} 🔗"
        return txt

    def chk_done():
        if S["done"] and S["chooser"] not in alive:
            S["done"].set()

    def run_prop(uid, k, t):
        used[uid].add(k)
        me = alive[uid].mention
        if k == "bomb":
            n = 3 if "bomb_up" in ups[uid] else 2
            pool = [x for x in alive if x != uid]
            out = [kill(v, by=uid) for v in random.sample(pool, min(n, len(pool)))]
            return f"💣 {me} فجّر قنبلة!\n" + "\n".join(o for o in out if o)
        if k == "revive":
            n = 2 if "revive_up" in ups[uid] else 1
            back = random.sample(list(dead), min(n, len(dead)))
            if not back:
                used[uid].discard(k)
                return "💓 ما فيه أحد مطرود يرجع!"
            for x in back:
                alive[x] = dead.pop(x)
            return f"💓 {me} أنعش " + "، ".join(alive[x].mention for x in back)
        if k == "swap":
            nums[uid], nums[t] = nums[t], nums[uid]
            return f"🔁 {me} بدّل مكانه مع {alive[t].mention}"
        if k == "block":
            pending[t] = 2 if "block_up" in ups[uid] else 1
            return f"🔒 {me} منع {alive[t].mention} من استخدام خصائصه!"
        if k == "attack":
            return f"⚔️ {me} هجم!\n" + (kill(t, pierce=True, by=uid) or "")
        if k == "hide":
            hidden.add(uid)
            return f"🙈 {me} اختفى من العجلة بهالجولة"
        if k == "link":
            links[uid] = t
            return f"🔗 {me} ربط مصيره بـ {alive[t].mention}"
        if k == "hack":
            hack[0] = uid
            return f"💻 {me} هكّر العجلة!"
        if k == "snipe":
            return f"🎯 {me} قنص!\n" + (kill(t, pierce=True, by=uid) or "")
        return None

    TARGET = {"swap", "block", "attack", "link", "snipe"}

    async def apply_prop(ii: discord.Interaction, k):
        uid = ii.user.id
        if uid not in alive or k in used[uid] or uid in blocked:
            return await ii.response.edit_message(content="❌ غير متاح", view=None)
        if k == "reveal":
            used[uid].add(k)
            hid = "، ".join(alive[x].display_name for x in hidden if x in alive) or "ما فيه"
            shl = "، ".join(alive[x].display_name for x in shield if x in alive) or "ما فيه"
            lnk = "، ".join(f"{alive[a].display_name}→{alive[b].display_name}" for a, b in links.items() if a in alive and b in alive) or "ما فيه"
            return await ii.response.edit_message(content=f"👁️ **المخفيين:** {hid}\n🛡️ **الدروع:** {shl}\n🔗 **الروابط:** {lnk}", view=None)
        if k in TARGET:
            opts = [alive[x] for x in alive if x != uid and (k == "snipe" or x not in hidden)]
            if not opts:
                return await ii.response.edit_message(content="ما فيه أهداف متاحة", view=None)

            async def tpick(i3: discord.Interaction, tid):
                if tid not in alive or k in used[uid]:
                    return await i3.response.edit_message(content="❌ غير متاح", view=None)
                txt = run_prop(uid, k, tid)
                await i3.response.edit_message(content="✅ تم", view=None)
                if txt:
                    await g.channel.send(txt)
                chk_done()

            return await ephemeral_pick(ii, opts, f"اختر الهدف لـ {PROPS[k][0]}", tpick)
        txt = run_prop(uid, k, None)
        await ii.response.edit_message(content="✅ تم", view=None)
        if txt:
            await g.channel.send(txt)
        chk_done()

    async def open_props(i: discord.Interaction):
        uid = i.user.id
        if uid not in alive:
            return await i.response.send_message("انت طالع من اللعبة 💀", ephemeral=True)
        if uid in blocked:
            return await i.response.send_message("🔒 خصائصك ممنوعة بهالجولة", ephemeral=True)
        avail = [k for k in owned.get(uid, ()) if k not in used[uid]]
        if not avail:
            return await i.response.send_message("ما عندك خصائص متاحة (اشتر من `متجر`)", ephemeral=True)
        sv = discord.ui.View(timeout=90)
        sel = discord.ui.Select(
            placeholder="اختر خاصية",
            options=[discord.SelectOption(label=PROPS[k][0], value=k, emoji=PROPS[k][2], description=PROPS[k][3][:90]) for k in avail],
        )

        async def chosen(ii: discord.Interaction):
            await apply_prop(ii, sel.values[0])

        sel.callback = chosen
        sv.add_item(sel)
        await i.response.send_message("خصائصك المتاحة:", view=sv, ephemeral=True)

    rnd = 1
    while len(alive) > 1:
        pool = [u for u in alive if u not in hidden] or list(alive)
        if hack[0] in alive:
            chooser, hack[0] = hack[0], None
        else:
            chooser = random.choice(pool)
        cm = alive[chooser]
        m = await say(g, f"🎡 الجولة {rnd}", "العجلة تدور...")
        for _ in range(8):
            x = random.choice(list(alive))
            await m.edit(embed=mk(f"🎡 الجولة {rnd}", f"العجلة تدور...\n# {nums[x]} • {alive[x].display_name}"))
            await asyncio.sleep(0.45)
        await m.edit(embed=mk(f"🎡 الجولة {rnd}", f"وقفت على **{nums[chooser]}** — {cm.mention}!"))

        targets = [alive[x] for x in alive if x != chooser and x not in hidden] or [alive[x] for x in alive if x != chooser]
        done, choice = asyncio.Event(), [None]
        S["done"], S["chooser"] = done, chooser
        view = discord.ui.View(timeout=None)
        sel = discord.ui.Select(
            placeholder="اختر من تبي تطلّعه",
            options=[discord.SelectOption(label=f"{nums[t.id]} • {t.display_name}"[:90], value=str(t.id)) for t in targets][:25],
        )

        async def pick(i: discord.Interaction, chooser=chooser, choice=choice, done=done, sel=sel):
            if i.user.id != chooser:
                return await i.response.send_message("مو دورك ✋", ephemeral=True)
            choice[0] = int(sel.values[0])
            await i.response.defer()
            done.set()

        sel.callback = pick
        view.add_item(sel)
        pb = discord.ui.Button(label="خصائصي", emoji="⚡", style=discord.ButtonStyle.secondary)
        pb.callback = open_props
        view.add_item(pb)
        pm = await say(g, "🎯 اختيار الإقصاء", f"{cm.mention} اختر من تبي تطلّعه ({g.T()} ثانية)\n⚡ أي لاعب يقدر يستخدم خصائصه من الزر.", view=view)
        try:
            await asyncio.wait_for(done.wait(), g.T())
        except asyncio.TimeoutError:
            pass
        await close(pm, view)

        txt, show_img = None, False
        if chooser not in alive:
            txt = f"{cm.mention} انطرد قبل ما يختار!"
        elif choice[0] is None:
            if DB.settings["afk_kick"]:
                txt = (kill(chooser) or "") + " (ما تفاعل 🚪)"
            else:
                tgt = random.choice([x for x in alive if x != chooser])
                txt, show_img = kill(tgt, by=chooser), True
        elif choice[0] in alive:
            txt, show_img = kill(choice[0], by=chooser), True
        else:
            txt = "الهدف طلع قبل كذا."
        eq = prof[chooser]["equip"] if show_img else None
        path = os.path.join(IMG_DIR, "shop", f"{eq}.png") if eq else None
        file = discord.File(path, "elim.png") if path and os.path.exists(path) else None
        await say(g, "💥 إقصاء", txt or "—", file=file)

        hidden.clear()
        for u in list(blocked):
            blocked[u] -= 1
            if blocked[u] <= 0:
                del blocked[u]
        blocked.update(pending)
        pending.clear()
        rnd += 1
        await asyncio.sleep(2.5)

    if alive:
        w = next(iter(alive.values()))
        prof[w.id]["rwin"] += 1
        DB.save()
        await finish(g, [w], 1, 10)
    else:
        await say(g, "🏁", "ما بقي أحد!")


# ================================================================ مافيا
AR = {"mafia": "🔪 مافيا", "doctor": "💊 طبيب", "cop": "🕵️ محقق", "citizen": "🙂 مواطن"}


@game("مافيا", "mafia", "🕵️ مافيا", "group", 45)
async def g_mafia(g):
    pl = await lobby(g, "", 4, 20, 60)
    if not pl:
        return
    random.shuffle(pl)
    n = len(pl)
    nm = min(5, max(1, n // 4))
    role = {}
    for i, p in enumerate(pl):
        role[p.id] = "mafia" if i < nm else "doctor" if i == nm else "cop" if i == nm + 1 else "citizen"
    alive = {p.id: p for p in pl}
    miss = {p.id: 0 for p in pl}
    doc_self = [False]

    rv = discord.ui.View(timeout=None)
    rb = discord.ui.Button(label="اعرف دورك", emoji="🎭", style=discord.ButtonStyle.primary)

    async def reveal(i: discord.Interaction):
        r = role.get(i.user.id)
        if not r:
            return await i.response.send_message("انت مو باللعبة", ephemeral=True)
        extra = ""
        if r == "mafia":
            mates = "، ".join(p.display_name for p in pl if role[p.id] == "mafia" and p.id != i.user.id)
            extra = f"\nزملاؤك: {mates or 'ما عندك'}"
        await i.response.send_message(f"دورك: **{AR[r]}**{extra}", ephemeral=True)

    rb.callback = reveal
    rv.add_item(rb)
    rm = await say(g, "🕵️ مافيا — تم توزيع الأدوار", f"اللاعبين: {n} | المافيا: {nm} | طبيب: 1 | محقق: 1\nاضغط الزر لمعرفة دورك (سري).", view=rv)
    await asyncio.sleep(20)
    await close(rm, rv)

    def winner():
        m = sum(role[p] == "mafia" for p in alive)
        if m == 0:
            return "citizens"
        return "mafia" if m >= len(alive) - m else None

    def kick_afk(ids):
        lines = []
        for u in ids:
            if u not in alive:
                continue
            miss[u] += 1
            if DB.settings["afk_kick"] and miss[u] >= 2:
                lines.append(f"🚪 انطرد {alive.pop(u).mention} لعدم التفاعل")
        return lines

    night, text = 1, ""
    while True:
        acts = {"mafia": {}, "doctor": None, "cop": None}
        ev = asyncio.Event()

        def check_done():
            mafias = [p for p in alive if role[p] == "mafia"]
            ok = all(x in acts["mafia"] for x in mafias)
            ok = ok and (acts["doctor"] is not None or not any(role[p] == "doctor" for p in alive))
            ok = ok and (acts["cop"] is not None or not any(role[p] == "cop" for p in alive))
            if ok:
                ev.set()

        async def act(i: discord.Interaction, r):
            if i.user.id not in alive or role[i.user.id] != r:
                return await i.response.send_message("هذا مو دورك 😉", ephemeral=True)
            uid = i.user.id
            opts = [p for p in alive.values() if not (r == "mafia" and role[p.id] == "mafia")]
            if r == "doctor" and doc_self[0]:
                opts = [p for p in opts if p.id != uid]

            async def pick(ii: discord.Interaction, t):
                if r == "mafia":
                    acts["mafia"][uid] = t
                else:
                    acts[r] = t
                if r == "doctor" and t == uid:
                    doc_self[0] = True
                miss[uid] = 0
                msg = "✅ تم"
                if r == "cop":
                    rr = role[t]
                    msg = f"{alive[t].display_name}: " + ("🔪 مافيا!" if rr == "mafia" else "🕵️ محقق" if rr == "cop" else "🙂 مواطن")
                await ii.response.edit_message(content=msg, view=None)
                check_done()

            await ephemeral_pick(i, opts, "اختر:", pick)

        def mkcb(r):
            async def cb(i):
                await act(i, r)

            return cb

        nv = discord.ui.View(timeout=None)
        for r, label in (("mafia", "🔪 مافيا"), ("doctor", "💊 طبيب"), ("cop", "🕵️ محقق")):
            bt = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary)
            bt.callback = mkcb(r)
            nv.add_item(bt)
        nmsg = await say(g, f"🌙 الليل {night}", f"الأحياء: {len(alive)}\nالمافيا والطبيب والمحقق: اضغطوا زر دوركم واختاروا ({g.T()} ثانية).", view=nv)
        try:
            await asyncio.wait_for(ev.wait(), g.T())
        except asyncio.TimeoutError:
            pass
        await close(nmsg, nv)

        missing = [p for p in alive if (role[p] == "mafia" and p not in acts["mafia"])
                   or (role[p] == "doctor" and acts["doctor"] is None) or (role[p] == "cop" and acts["cop"] is None)]
        afk_lines = kick_afk(missing)

        votes = list(acts["mafia"].values())
        victim = max(set(votes), key=lambda x: (votes.count(x), random.random())) if votes else None
        if victim is not None and victim == acts["doctor"]:
            text = "💊 الطبيب أنقذ ضحية المافيا! ما مات أحد."
        elif victim is not None and victim in alive:
            dead = alive.pop(victim)
            text = f"🔪 المافيا قتلوا {dead.mention} (كان {AR[role[victim]]})"
        else:
            text = "الليل مرّ بهدوء."
        text += ("\n" + "\n".join(afk_lines)) if afk_lines else ""
        w = winner()
        if w:
            break

        # ---- نقاش ثم تصويت
        disc = int(DB.settings["discussion"])
        await say(g, f"☀️ النهار {night}", f"{text}\n\n💬 وقت النقاش: **{disc}** ثانية")
        await asyncio.sleep(disc)
        votes_d, ev2 = {}, asyncio.Event()
        vv = discord.ui.View(timeout=None)
        sel = discord.ui.Select(
            placeholder="صوّت لطرد مشتبه",
            options=[discord.SelectOption(label=p.display_name[:90], value=str(p.id)) for p in alive.values()][:25],
        )

        async def vote(i: discord.Interaction):
            if i.user.id not in alive:
                return await i.response.send_message("الأموات ما يصوتون 💀", ephemeral=True)
            votes_d[i.user.id] = int(sel.values[0])
            miss[i.user.id] = 0
            await i.response.send_message("✅ تم تسجيل صوتك", ephemeral=True)
            if len(votes_d) >= len(alive):
                ev2.set()

        sel.callback = vote
        vv.add_item(sel)
        dm = await say(g, f"🗳️ التصويت {night}", f"صوّتوا على من تشكون فيه ({g.T()} ثانية).", view=vv)
        try:
            await asyncio.wait_for(ev2.wait(), g.T())
        except asyncio.TimeoutError:
            pass
        await close(dm, vv)

        afk_lines = kick_afk([p for p in alive if p not in votes_d])
        tally = {}
        for t in votes_d.values():
            tally[t] = tally.get(t, 0) + 1
        out_text = "ما أحد انطرد (تعادل أو ما فيه أصوات)."
        if tally:
            top = max(tally.values())
            tops = [t for t, c in tally.items() if c == top]
            if len(tops) == 1 and tops[0] in alive:
                out = alive.pop(tops[0])
                out_text = f"🗳️ انطرد {out.mention} وكان {AR[role[out.id]]}"
        if afk_lines:
            out_text += "\n" + "\n".join(afk_lines)
        await say(g, "🗳️ نتيجة التصويت", out_text)
        w = winner()
        if w:
            text = out_text
            break
        night += 1
        await asyncio.sleep(3)

    roles_txt = "\n".join(f"{p.mention}: {AR[role[p.id]]}" for p in pl)
    head = "🏆 فاز **المواطنين**!" if w == "citizens" else "😈 فازت **المافيا**!"
    await say(g, "🕵️ انتهت المافيا", f"{text}\n\n{head}\n\n{roles_txt}")
    winners = [p for p in pl if (role[p.id] == "mafia") == (w == "mafia")]
    await finish(g, winners, 1, 3)


# ================================================================ كراسي
class ChairBtn(discord.ui.Button):
    def __init__(self):
        super().__init__(label="🪑", style=discord.ButtonStyle.secondary, disabled=True)

    async def callback(self, i: discord.Interaction):
        v: "Chairs" = self.view
        if i.user not in v.alive:
            return await i.response.send_message("انت مو داخل اللعبة", ephemeral=True)
        if i.user in v.seated:
            return await i.response.send_message("انت جالس أصلاً 😎", ephemeral=True)
        v.seated.append(i.user)
        self.label, self.style, self.disabled = i.user.display_name[:12], discord.ButtonStyle.success, True
        if len(v.seated) >= v.n:
            v.ev.set()
        await i.response.edit_message(view=v)


class Chairs(discord.ui.View):
    def __init__(self, alive, n):
        super().__init__(timeout=None)
        self.alive, self.n, self.seated, self.ev = alive, n, [], asyncio.Event()
        for _ in range(n):
            self.add_item(ChairBtn())


@game("كراسي", "chairs", "🪑 كراسي", "group", 10)
async def g_chairs(g):
    pl = await lobby(g, "", 3, 20, 30)
    if not pl:
        return
    alive, rnd = pl[:], 1
    while len(alive) > 1:
        v = Chairs(alive, len(alive) - 1)
        m = await say(g, f"🪑 الجولة {rnd}", f"🎵 الموسيقى شغالة...\nاللاعبين: {len(alive)} | الكراسي: {len(alive) - 1}", view=v)
        await asyncio.sleep(random.uniform(3, 8))
        for c in v.children:
            c.disabled = False
        await m.edit(embed=mk(f"🪑 الجولة {rnd}", "⏸️ **وقفت الموسيقى! اجلس بسرعة!**"), view=v)
        try:
            await asyncio.wait_for(v.ev.wait(), g.T())
        except asyncio.TimeoutError:
            pass
        seated = list(v.seated)
        await close(m, v)
        if not seated:
            return await say(g, "😴", "ما أحد جلس! انتهت اللعبة بدون فائز.")
        out = [p for p in alive if p not in seated]
        await say(g, "💥 طلعوا", "، ".join(p.mention for p in out))
        alive, rnd = seated, rnd + 1
        await asyncio.sleep(2)
    await finish(g, [alive[0]], 1, 3)


# ================================================================ هايد (اختباء بالجولات)
SPOT_EMOJIS = ["🛋️", "🚪", "🛏️", "🌳", "🚗", "🛁", "📦", "🪟", "🧺", "🪴", "🗄️", "🏠", "⛺", "🛖", "🪑", "🧰", "🎪", "🚿", "🕳️", "🪜"]


@game("هايد", "hide", "🙈 هايد", "group", 30)
async def g_hide(g):
    pl = await lobby(g, "", 3, 10, 30)
    if not pl:
        return
    alive, rnd = pl[:], 0
    while len(alive) > 1 and rnd < 20:
        rnd += 1
        seeker = random.choice(alive)
        hiders = [p for p in alive if p != seeker]
        n = min(20, len(hiders) + 3)
        spots = random.sample(SPOT_EMOJIS, n)
        hide, ev = {}, asyncio.Event()
        hv = discord.ui.View(timeout=None)
        hb = discord.ui.Button(label="اختبئ", emoji="🙈", style=discord.ButtonStyle.primary)

        async def hb_cb(i: discord.Interaction, hiders=hiders, hide=hide, ev=ev, spots=spots):
            if i.user not in hiders:
                return await i.response.send_message("انت الباحث أو مو باللعبة 😅", ephemeral=True)
            if i.user.id in hide:
                return await i.response.send_message("اخترت مكانك أصلاً ✅", ephemeral=True)
            free = [k for k in range(len(spots)) if k not in hide.values()]
            sv = discord.ui.View(timeout=60)
            sel = discord.ui.Select(placeholder="اختر مكان اختبائك", options=[
                discord.SelectOption(label=f"مكان {k + 1}", value=str(k), emoji=spots[k]) for k in free][:25])

            async def pick(ii: discord.Interaction):
                k = int(sel.values[0])
                if ii.user.id in hide:
                    return await ii.response.edit_message(content="اخترت أصلاً", view=None)
                if k in hide.values():
                    return await ii.response.edit_message(content="المكان انأخذ، اختر غيره", view=None)
                hide[ii.user.id] = k
                await ii.response.edit_message(content=f"✅ اختبأت في {spots[k]}", view=None)
                if len(hide) == len(hiders):
                    ev.set()

            sel.callback = pick
            sv.add_item(sel)
            await i.response.send_message("وين تختبئ؟", view=sv, ephemeral=True)

        hb.callback = hb_cb
        hv.add_item(hb)
        m = await say(g, f"🙈 الجولة {rnd}", f"🔎 الباحث: {seeker.mention}\nالمختبئين ({len(hiders)}): اضغطوا **اختبئ** واختاروا مكانكم ({g.T()} ثانية)\nاللاعبين المتبقين: {len(alive)}", view=hv)
        try:
            await asyncio.wait_for(ev.wait(), g.T())
        except asyncio.TimeoutError:
            pass
        await close(m, hv)
        kicked = []
        for h in list(hiders):
            if h.id not in hide:
                if DB.settings["afk_kick"]:
                    alive.remove(h)
                    hiders.remove(h)
                    kicked.append(f"🚪 انطرد {h.mention} (ما اختبأ)")
                else:
                    hide[h.id] = random.choice([k for k in range(n) if k not in hide.values()])
        if kicked:
            await say(g, "🚪 طرد", "\n".join(kicked))
        if len(alive) <= 1 or not hiders:
            break

        found, st, ev2 = [], {"left": 3, "used": 0}, asyncio.Event()
        sv = discord.ui.View(timeout=None)

        def mkcb(k, btn, hiders=hiders, hide=hide, found=found, st=st, ev2=ev2, sv=sv, seeker=seeker, spots=spots):
            async def cb(i: discord.Interaction):
                if i.user != seeker:
                    return await i.response.send_message("الباحث فقط 🔎", ephemeral=True)
                hits = [h for h in hiders if hide[h.id] == k]
                found.extend(hits)
                st["left"] -= 1
                st["used"] += 1
                btn.disabled = True
                btn.style = discord.ButtonStyle.success if hits else discord.ButtonStyle.danger
                btn.label = "، ".join(h.display_name for h in hits)[:60] if hits else "فاضي"
                done = len(found) == len(hiders) or st["left"] == 0
                if done:
                    for c in sv.children:
                        c.disabled = True
                await i.response.edit_message(
                    embed=mk(f"🔎 البحث — الجولة {rnd}", f"الباحث: {seeker.mention}\nلقى: {len(found)}/{len(hiders)} | محاولات باقية: {st['left']}"), view=sv)
                if done:
                    ev2.set()

            return cb

        for k in range(n):
            b = discord.ui.Button(emoji=spots[k], style=discord.ButtonStyle.secondary, row=k // 5)
            b.callback = mkcb(k, b)
            sv.add_item(b)
        sm = await say(g, f"🔎 البحث — الجولة {rnd}", f"{seeker.mention} عندك **3 محاولات** تدوّر على {len(hiders)} مختبئين!", view=sv)
        try:
            await asyncio.wait_for(ev2.wait(), 60)
        except asyncio.TimeoutError:
            pass
        await close(sm, sv)
        if st["used"] == 0 and DB.settings["afk_kick"]:
            alive.remove(seeker)
            await say(g, "🚪 طرد", f"انطرد الباحث {seeker.mention} (ما تفاعل)")
        for h in found:
            if h in alive:
                alive.remove(h)
        if found:
            await say(g, "💥 طلعوا", "، ".join(h.mention for h in found) + f"\nالباقين: {len(alive)}")
        else:
            await say(g, "😅 ما لقى أحد", "ننتقل للجولة التالية!")
        await asyncio.sleep(2)
    if not alive:
        return await say(g, "🏁", "ما بقي أحد!")
    await say(g, "🏆 الفائز" if len(alive) == 1 else "🏆 الفائزين", "، ".join(p.mention for p in alive))
    await finish(g, alive, 1, 3)


# ================================================================ تصويت
VOTE_GAMES = ["روليت", "مافيا", "لغم", "هايد", "حجره", "كراسي", "وصل"]


@game("تصويت", "vote", "🗳️ تصويت", "group", 60)
async def g_vote(g):
    names = [n for n in VOTE_GAMES if n in GAMES]
    votes = {}
    end = int(time.time()) + g.T()

    def emb():
        cnt = {n: 0 for n in names}
        for n in votes.values():
            cnt[n] += 1
        lines = "\n".join(f"🎮 {n} : {cnt[n]}" for n in names)
        e = discord.Embed(title="Game Vote", description=f"**التصويت على اللعبة**\n{lines}\n⏰ **ينتهي التصويت** <t:{end}:R>", color=COLOR)
        if bot.user:
            e.set_thumbnail(url=bot.user.display_avatar.url)
        return e

    v = discord.ui.View(timeout=None)
    sel = discord.ui.Select(placeholder="اختر اللعبة التي تريد التصويت لها",
                            options=[discord.SelectOption(label=n, emoji="🎮") for n in names])

    async def cb(i: discord.Interaction):
        votes[i.user.id] = sel.values[0]
        await i.response.edit_message(embed=emb())

    sel.callback = cb
    v.add_item(sel)
    m = await g.channel.send(embed=emb(), view=v)
    g.views.append((v, m))
    await asyncio.sleep(g.T())
    await close(m, v)
    g.no_replay = True
    if not votes:
        return await say(g, "🗳️", "ما أحد صوّت، انلغى التصويت.")
    cnt = {}
    for n in votes.values():
        cnt[n] = cnt.get(n, 0) + 1
    top = max(cnt.values())
    win = random.choice([n for n, c in cnt.items() if c == top])
    await say(g, "🏆 اللعبة الفائزة", f"**{win}** بـ {top} صوت — تبدأ الحين!")
    g.next = win
