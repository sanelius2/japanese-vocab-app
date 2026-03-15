#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日语单词本 - Android版本（Kivy + 离线词典）
完全独立运行，无需任何第三方 Python 依赖。
内嵌 JMdict 词典（21万词条），查不到时联网补充。
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.core.window import Window
from kivy.metrics import dp, sp
from kivy.utils import get_color_from_hex
from kivy.clock import Clock
import json
import os
import datetime
import threading
import random
import sys

# ── 词典模块 ──
try:
    from dict_core import lookup, lookup_offline, DB_PATH
    _DICT_OK = DB_PATH is not None
except ImportError:
    _DICT_OK = False
    def lookup(kw, cb): cb([], "none", "词典模块未加载")
    def lookup_offline(kw): return []
    DB_PATH = None

# ── 数据路径 ──
try:
    from android.storage import app_storage_path  # type: ignore
    _DATA_DIR = app_storage_path()
except ImportError:
    _DATA_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(_DATA_DIR, "vocabulary.json")

INTERVALS = [1, 2, 4, 7, 15, 30, 60]

# ── 颜色 ──
C_PRI  = get_color_from_hex("#1565C0")
C_PRIL = get_color_from_hex("#42A5F5")
C_GRN  = get_color_from_hex("#388E3C")
C_RED  = get_color_from_hex("#D32F2F")
C_WHT  = get_color_from_hex("#FFFFFF")
C_BG   = get_color_from_hex("#ECEFF1")
C_TXT  = get_color_from_hex("#212121")
C_GRY  = get_color_from_hex("#9E9E9E")

# ────────────────────────────────────────
#  数据操作
# ────────────────────────────────────────
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_data(words):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

def add_word(words, entry):
    today = datetime.date.today().isoformat()
    entry.setdefault("add_date", today)
    entry.setdefault("review_stage", 0)
    entry.setdefault("review_count", 0)
    nxt = datetime.date.today() + datetime.timedelta(days=INTERVALS[0])
    entry["next_review"] = nxt.isoformat()
    words.append(entry)
    save_data(words)

def advance_stage(words, idx):
    w = words[idx]
    stage = w.get("review_stage", 0) + 1
    w["review_stage"] = stage
    w["review_count"] = w.get("review_count", 0) + 1
    if stage < len(INTERVALS):
        nxt = datetime.date.today() + datetime.timedelta(days=INTERVALS[stage])
        w["next_review"] = nxt.isoformat()
    else:
        w["next_review"] = None
    save_data(words)

def get_due(words):
    today = datetime.date.today().isoformat()
    return [(i, w) for i, w in enumerate(words)
            if w.get("next_review") and w["next_review"] <= today]

# ────────────────────────────────────────
#  UI 工具
# ────────────────────────────────────────
def mkbtn(text, bg=None, fg=None, h=dp(46), **kw):
    b = Button(
        text=text,
        size_hint_y=None, height=h,
        background_color=bg or C_PRI,
        color=fg or C_WHT,
        font_size=sp(14),
        **kw
    )
    return b

def mklbl(text, size=sp(13), color=None, bold=False, halign="left", **kw):
    color = color or C_TXT
    l = Label(
        text=text, font_size=size, color=color, bold=bold,
        halign=halign, text_size=(None, None), **kw
    )
    l.bind(size=lambda inst, v: setattr(inst, "text_size", (v[0], None)))
    return l

def show_toast(title, msg, ok_cb=None):
    box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    box.add_widget(Label(
        text=msg, font_size=sp(13), color=C_TXT,
        text_size=(dp(260), None), size_hint_y=None, height=dp(72)))
    btn = mkbtn("确定", h=dp(42))
    box.add_widget(btn)
    pop = Popup(title=title, content=box,
                size_hint=(0.88, None), height=dp(190))
    def _close(*a):
        pop.dismiss()
        if ok_cb: ok_cb()
    btn.bind(on_press=_close)
    pop.open()

# ────────────────────────────────────────
#  底部导航栏
# ────────────────────────────────────────
class NavBar(BoxLayout):
    def __init__(self, sm, **kw):
        super().__init__(orientation="horizontal",
                         size_hint_y=None, height=dp(54), **kw)
        self.sm = sm
        tabs = [
            ("search_screen", "🔍查询"),
            ("vocab_screen",  "📚生词本"),
            ("card_screen",   "🃏卡片"),
            ("review_screen", "🧠复习"),
        ]
        for sn, label in tabs:
            btn = ToggleButton(
                text=label, group="nav",
                font_size=sp(12),
                background_color=C_PRI, color=C_WHT,
            )
            btn.bind(on_press=lambda b, s=sn: self._go(s))
            self.add_widget(btn)
        # 默认选中第一个
        self.children[-1].state = "down"

    def _go(self, screen_name):
        self.sm.transition = SlideTransition()
        self.sm.current = screen_name

# ────────────────────────────────────────
#  查询页面
# ────────────────────────────────────────
class SearchScreen(Screen):
    def __init__(self, words_ref, **kw):
        super().__init__(name="search_screen", **kw)
        self.words_ref = words_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical",
                         padding=dp(10), spacing=dp(8))
        # 顶部标题
        hdr = mklbl(
            f"🈶 日语单词本  {'📖离线词典已加载' if _DICT_OK else '⚠仅联网'}",
            size=sp(15), bold=True, halign="center",
            size_hint_y=None, height=dp(40))
        root.add_widget(hdr)

        # 搜索行
        row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="输入日语单词（汉字/假名/罗马字）",
            multiline=False, font_size=sp(15), size_hint_x=0.72)
        self.search_input.bind(on_text_validate=self._do_search)
        row.add_widget(self.search_input)
        btn = mkbtn("查询", size_hint_x=0.28)
        btn.bind(on_press=self._do_search)
        row.add_widget(btn)
        root.add_widget(row)

        self.status_lbl = mklbl("", size=sp(11), color=C_GRY,
                                 size_hint_y=None, height=dp(20))
        root.add_widget(self.status_lbl)

        # 结果
        scroll = ScrollView()
        self.result_box = BoxLayout(
            orientation="vertical", spacing=dp(8),
            size_hint_y=None, padding=(0, dp(4)))
        self.result_box.bind(
            minimum_height=self.result_box.setter("height"))
        scroll.add_widget(self.result_box)
        root.add_widget(scroll)
        self.add_widget(root)

    def _do_search(self, *a):
        kw = self.search_input.text.strip()
        if not kw: return
        self.status_lbl.text = "查询中…"
        self.result_box.clear_widgets()

        def _cb(results, source, err):
            src_tag = "（离线）" if source == "offline" else "（联网）" if source == "online" else ""
            if not results:
                Clock.schedule_once(lambda dt: setattr(
                    self.status_lbl, "text", f"未找到：{err or '无结果'}"))
                return
            Clock.schedule_once(lambda dt: setattr(
                self.status_lbl, "text",
                f"找到 {len(results)} 条 {src_tag}"))
            Clock.schedule_once(lambda dt: self._show_results(results))

        lookup(kw, _cb)

    def _show_results(self, results):
        self.result_box.clear_widgets()
        for r in results:
            self._add_card(r)

    def _add_card(self, r):
        card = BoxLayout(orientation="vertical",
                         size_hint_y=None, padding=dp(10), spacing=dp(6))
        card.bind(minimum_height=card.setter("height"))

        # 单词行
        word    = r.get("word", "")
        reading = r.get("reading", "")
        tags    = (["★常用"] if r.get("is_common") else [])
        tags   += [t.upper() for t in r.get("jlpt", [])]
        if r.get("source") == "online": tags.append("🌐")

        hdr_text = (
            f"[b][size={int(sp(19))}][color=1A237E]{word}[/color][/size][/b]"
            + (f"  [size={int(sp(13))}][color=3949AB]【{reading}】[/color][/size]"
               if reading and reading != word else "")
            + (f"  [size={int(sp(11))}][color=2E7D32]{' '.join(tags)}[/color][/size]"
               if tags else "")
        )
        lbl_hdr = Label(
            text=hdr_text, markup=True,
            size_hint_y=None, height=dp(38),
            text_size=(Window.width - dp(30), None), halign="left")
        card.add_widget(lbl_hdr)

        # 释义
        senses = r.get("senses", [])
        def_lines = []
        for i, s in enumerate(senses[:4]):
            pos  = "·".join(s.get("pos", []))
            gls  = "；".join(s.get("glosses", []))
            misc = "·".join(s.get("misc", []))
            line = f"{i+1}."
            if pos: line += f" [{pos}]"
            line += f" {gls}"
            if misc: line += f"  ({misc})"
            def_lines.append(line)
            for ex in s.get("examples", [])[:1]:
                if ex.get("ja"): def_lines.append(f"   例：{ex['ja']}")
                if ex.get("zh"): def_lines.append(f"       {ex['zh']}")

        def_text = "\n".join(def_lines)
        lbl_def = Label(
            text=def_text,
            size_hint_y=None,
            text_size=(Window.width - dp(30), None),
            halign="left", font_size=sp(12), color=C_TXT)
        lbl_def.bind(texture_size=lambda inst, v: setattr(
            inst, "height", v[1] + dp(8)))
        card.add_widget(lbl_def)

        # 备注 + 添加
        row2 = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        note_inp = TextInput(
            hint_text="备注（可选）",
            multiline=False, font_size=sp(12), size_hint_x=0.55)
        row2.add_widget(note_inp)
        btn_add = mkbtn("➕ 加入生词本", size_hint_x=0.45, h=dp(44))

        def _add(inst, r=r, ni=note_inp):
            wt = r.get("word", "") or r.get("reading", "")
            words = self.words_ref[0]
            if any(w.get("word") == wt for w in words):
                show_toast("提示", f"「{wt}」已在生词本中！"); return
            meanings_save = [
                {"pos": "·".join(s.get("pos", [])),
                 "defs": "；".join(s.get("glosses", [])),
                 "defs_en": "；".join(s.get("glosses_en", []))}
                for s in r.get("senses", [])[:4]]
            entry = {
                "word":      wt,
                "reading":   r.get("reading", ""),
                "meanings":  meanings_save,
                "jlpt":      r.get("jlpt", []),
                "is_common": r.get("is_common", False),
                "note":      ni.text.strip(),
            }
            add_word(words, entry)
            show_toast("已添加", f"「{wt}」已加入生词本！")

        btn_add.bind(on_press=_add)
        row2.add_widget(btn_add)
        card.add_widget(row2)

        # 分隔线（用空白 Label 代替）
        card.add_widget(Label(size_hint_y=None, height=dp(1),
                              canvas_before=None))
        self.result_box.add_widget(card)

# ────────────────────────────────────────
#  生词本页面
# ────────────────────────────────────────
class VocabScreen(Screen):
    def __init__(self, words_ref, **kw):
        super().__init__(name="vocab_screen", **kw)
        self.words_ref = words_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical",
                         padding=dp(10), spacing=dp(8))
        tb = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        tb.add_widget(mklbl("📚 我的生词本", size=sp(16), bold=True,
                             size_hint_x=0.6))
        btn_r = mkbtn("🔄", size_hint_x=0.2)
        btn_r.bind(on_press=lambda *a: self._refresh())
        tb.add_widget(btn_r)
        root.add_widget(tb)

        scroll = ScrollView()
        self.vbox = BoxLayout(orientation="vertical", spacing=dp(4),
                              size_hint_y=None, padding=(0, dp(4)))
        self.vbox.bind(minimum_height=self.vbox.setter("height"))
        scroll.add_widget(self.vbox)
        root.add_widget(scroll)
        self.add_widget(root)
        self._refresh()

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        words = load_data()
        self.words_ref[0] = words
        self.vbox.clear_widgets()
        if not words:
            self.vbox.add_widget(mklbl(
                "生词本为空，先去查询添加单词吧！",
                color=C_GRY, halign="center"))
            return
        for i, w in enumerate(words):
            self._add_row(i, w)

    def _add_row(self, idx, w):
        row = BoxLayout(size_hint_y=None, height=dp(70), spacing=dp(6))
        wt   = w.get("word") or w.get("reading", "")
        rdng = w.get("reading", "")
        d0   = (w.get("meanings") or [{}])[0]
        defs = (d0.get("defs") or "")[:32]
        next_rev = w.get("next_review") or "已掌握"
        stage = w.get("review_stage", 0)

        info = BoxLayout(orientation="vertical", size_hint_x=0.78)
        lbl_w = Label(
            text=(f"[b][size={int(sp(16))}][color=1A237E]{wt}[/color][/size][/b]"
                  + (f"  [size={int(sp(12))}][color=5C6BC0]【{rdng}】[/color][/size]"
                     if rdng and rdng != wt else "")),
            markup=True, halign="left",
            text_size=(Window.width * 0.70, None), size_hint_y=0.5)
        info.add_widget(lbl_w)
        lbl_d = Label(text=defs, font_size=sp(11), color=C_GRY,
                      halign="left",
                      text_size=(Window.width * 0.70, None), size_hint_y=0.3)
        info.add_widget(lbl_d)
        lbl_r = Label(
            text=f"下次：{next_rev}  第{stage+1}阶",
            font_size=sp(10), color=C_GRY, halign="left",
            text_size=(Window.width * 0.70, None), size_hint_y=0.2)
        info.add_widget(lbl_r)
        row.add_widget(info)

        btn_del = mkbtn("🗑", bg=C_RED, size_hint_x=0.22)
        btn_del.bind(on_press=lambda inst, i=idx: self._delete(i))
        row.add_widget(btn_del)
        self.vbox.add_widget(row)

    def _delete(self, idx):
        words = self.words_ref[0]
        if idx < len(words):
            wt = words[idx].get("word", "")
            words.pop(idx)
            save_data(words)
            self.words_ref[0] = words
            show_toast("已删除", f"「{wt}」已从生词本删除")
            self._refresh()

# ────────────────────────────────────────
#  单词卡片页面
# ────────────────────────────────────────
class CardScreen(Screen):
    def __init__(self, words_ref, **kw):
        super().__init__(name="card_screen", **kw)
        self.words_ref = words_ref
        self.card_deck = []
        self.card_idx  = 0
        self.card_revealed = False
        self.card_mode = "jp2cn"
        self._answer   = ""
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical",
                         padding=dp(12), spacing=dp(10))

        # 模式 + 开始
        mrow = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        b1 = ToggleButton(text="日→中", group="cmode",
                          state="down", font_size=sp(13))
        b2 = ToggleButton(text="中→日", group="cmode", font_size=sp(13))
        b1.bind(on_press=lambda *a: setattr(self, "card_mode", "jp2cn"))
        b2.bind(on_press=lambda *a: setattr(self, "card_mode", "cn2jp"))
        btn_start = mkbtn("🔀 随机开始")
        btn_start.bind(on_press=lambda *a: self._start())
        mrow.add_widget(b1); mrow.add_widget(b2); mrow.add_widget(btn_start)
        root.add_widget(mrow)

        self.prog_lbl = mklbl("", size=sp(11), color=C_GRY,
                               halign="center",
                               size_hint_y=None, height=dp(20))
        root.add_widget(self.prog_lbl)

        # 卡片
        self.card_area = BoxLayout(orientation="vertical",
                                    size_hint=(1, 0.52))
        self.lbl_hint = mklbl("", size=sp(11), color=C_GRY, halign="center")
        self.lbl_main = mklbl("点击「随机开始」", size=sp(24),
                               color=C_PRI, bold=True, halign="center")
        self.lbl_sub  = mklbl("", size=sp(14), color=C_TXT, halign="center")
        self.card_area.add_widget(self.lbl_hint)
        self.card_area.add_widget(self.lbl_main)
        self.card_area.add_widget(self.lbl_sub)
        root.add_widget(self.card_area)

        brow = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        btn_prev = mkbtn("⬅ 上一张", bg=get_color_from_hex("#607D8B"))
        btn_prev.bind(on_press=lambda *a: self._prev())
        self.btn_reveal = mkbtn("翻面查看答案")
        self.btn_reveal.bind(on_press=lambda *a: self._reveal())
        btn_next = mkbtn("下一张 ➡", bg=get_color_from_hex("#607D8B"))
        btn_next.bind(on_press=lambda *a: self._next())
        brow.add_widget(btn_prev)
        brow.add_widget(self.btn_reveal)
        brow.add_widget(btn_next)
        root.add_widget(brow)
        self.add_widget(root)

    def on_enter(self):
        pass  # 保留当前状态

    def _start(self):
        words = load_data()
        self.words_ref[0] = words
        if not words:
            show_toast("提示", "生词本为空，请先添加单词！"); return
        self.card_deck = list(range(len(words)))
        random.shuffle(self.card_deck)
        self.card_idx = 0
        self._show()

    def _show(self):
        words = self.words_ref[0]
        if not self.card_deck: return
        idx = self.card_deck[self.card_idx]
        w   = words[idx]
        self.card_revealed = False
        self.prog_lbl.text = f"第 {self.card_idx+1} / {len(self.card_deck)} 张"

        wt   = w.get("word") or w.get("reading", "")
        rdng = w.get("reading", "")
        m    = w.get("meanings", [])
        defs = "\n".join(
            f"{i+1}. [{s.get('pos','')}] {s.get('defs','')}"
            for i, s in enumerate(m[:3]))
        note = w.get("note", "")

        if self.card_mode == "jp2cn":
            self.lbl_hint.text = "▼ 日语单词"
            self.lbl_main.text = wt
            self.lbl_main.color = C_PRI
            self.lbl_sub.text = f"【{rdng}】" if rdng and rdng != wt else ""
            self._answer = defs + (f"\n备注：{note}" if note else "")
        else:
            self.lbl_hint.text = "▼ 中文释义"
            self.lbl_main.text = defs[:90] if defs else "（无释义）"
            self.lbl_main.color = C_GRN
            self.lbl_sub.text = ""
            self._answer = wt + (f"\n【{rdng}】" if rdng else "")
        self.btn_reveal.text = "翻面查看答案"

    def _reveal(self):
        if not self.card_revealed:
            self.card_revealed = True
            self.lbl_sub.text = self._answer
            self.lbl_sub.color = C_PRI if self.card_mode == "cn2jp" else C_TXT
            self.btn_reveal.text = "已翻面 ✓"

    def _next(self):
        if not self.card_deck: return
        self.card_idx = (self.card_idx + 1) % len(self.card_deck)
        self._show()

    def _prev(self):
        if not self.card_deck: return
        self.card_idx = (self.card_idx - 1) % len(self.card_deck)
        self._show()

# ────────────────────────────────────────
#  艾宾浩斯复习页面
# ────────────────────────────────────────
class ReviewScreen(Screen):
    def __init__(self, words_ref, **kw):
        super().__init__(name="review_screen", **kw)
        self.words_ref = words_ref
        self.rev_queue = []
        self.rev_pos   = 0
        self._rev_revealed = False
        self._rev_answer   = ""
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical",
                         padding=dp(12), spacing=dp(8))

        trow = BoxLayout(size_hint_y=None, height=dp(46))
        trow.add_widget(mklbl("🧠 艾宾浩斯复习",
                               size=sp(16), bold=True, size_hint_x=0.6))
        btn_load = mkbtn("刷新今日任务", size_hint_x=0.4)
        btn_load.bind(on_press=lambda *a: self._load())
        trow.add_widget(btn_load)
        root.add_widget(trow)

        root.add_widget(mklbl("间隔：1→2→4→7→15→30→60天",
                               size=sp(11), color=C_GRY,
                               size_hint_y=None, height=dp(18)))

        self.prog_lbl = mklbl("", size=sp(11), color=C_GRY,
                               halign="center",
                               size_hint_y=None, height=dp(20))
        root.add_widget(self.prog_lbl)

        # 卡片区
        self.card_area = BoxLayout(orientation="vertical",
                                    size_hint=(1, 0.48))
        self.lbl_status  = mklbl("点击「刷新今日任务」",
                                  size=sp(14), color=C_GRY, halign="center")
        self.lbl_word    = mklbl("", size=sp(24), bold=True,
                                  color=C_PRI, halign="center")
        self.lbl_reading = mklbl("", size=sp(14), color=C_PRIL, halign="center")
        self.lbl_stage   = mklbl("", size=sp(11), color=C_GRY, halign="center")
        self.lbl_ans     = mklbl("", size=sp(13), color=C_TXT, halign="center")
        for w in [self.lbl_status, self.lbl_word, self.lbl_reading,
                  self.lbl_stage, self.lbl_ans]:
            self.card_area.add_widget(w)
        root.add_widget(self.card_area)

        brow = BoxLayout(size_hint_y=None, height=dp(50), spacing=dp(6))
        self.btn_show = mkbtn("显示答案")
        self.btn_show.bind(on_press=lambda *a: self._reveal())
        btn_ok   = mkbtn("✅ 已记住", bg=C_GRN)
        btn_ok.bind(on_press=lambda *a: self._known())
        btn_fail = mkbtn("❌ 没记住", bg=C_RED)
        btn_fail.bind(on_press=lambda *a: self._unknown())
        brow.add_widget(self.btn_show)
        brow.add_widget(btn_ok)
        brow.add_widget(btn_fail)
        root.add_widget(brow)
        self.add_widget(root)

    def on_enter(self):
        self._load()

    def _load(self):
        words = load_data()
        self.words_ref[0] = words
        due = get_due(words)
        if not due:
            self._clear()
            self.lbl_status.text = "🎉 今天没有需要复习的单词！"
            self.prog_lbl.text   = ""
            return
        self.rev_queue = due
        self.rev_pos   = 0
        self._show_card()

    def _clear(self):
        for l in [self.lbl_word, self.lbl_reading, self.lbl_stage, self.lbl_ans]:
            l.text = ""

    def _show_card(self):
        self._clear()
        if self.rev_pos >= len(self.rev_queue):
            self.lbl_status.text = "🎉 今日复习完成！加油！"
            self.prog_lbl.text   = ""
            return

        self.lbl_status.text = ""
        total = len(self.rev_queue)
        self.prog_lbl.text = f"今日待复习：{self.rev_pos+1} / {total}"

        idx, w = self.rev_queue[self.rev_pos]
        wt     = w.get("word") or w.get("reading", "")
        rdng   = w.get("reading", "")
        stage  = w.get("review_stage", 0)
        intv   = INTERVALS[stage] if stage < len(INTERVALS) else "已掌握"

        self.lbl_word.text    = wt
        self.lbl_reading.text = f"【{rdng}】" if rdng and rdng != wt else ""
        self.lbl_stage.text   = f"第 {stage+1} 阶段 | 下次间隔 {intv} 天"

        m    = w.get("meanings", [])
        defs = "\n".join(
            f"{i+1}. [{s.get('pos','')}] {s.get('defs','')}"
            for i, s in enumerate(m[:3]))
        note = w.get("note", "")
        if note: defs += f"\n备注：{note}"
        self._rev_answer    = defs
        self.lbl_ans.text   = ""
        self._rev_revealed  = False
        self.btn_show.text  = "显示答案"

    def _reveal(self):
        if not self._rev_revealed:
            self._rev_revealed = True
            self.lbl_ans.text  = self._rev_answer
            self.btn_show.text = "已显示 ✓"

    def _known(self):
        if not self.rev_queue or self.rev_pos >= len(self.rev_queue): return
        idx, _ = self.rev_queue[self.rev_pos]
        words  = self.words_ref[0]
        advance_stage(words, idx)
        self.words_ref[0] = words
        self.rev_pos += 1
        self._show_card()

    def _unknown(self):
        if not self.rev_queue or self.rev_pos >= len(self.rev_queue): return
        idx, w = self.rev_queue[self.rev_pos]
        words  = self.words_ref[0]
        words[idx]["review_stage"] = 0
        words[idx]["next_review"]  = (
            datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        save_data(words)
        self.words_ref[0] = words
        self.rev_pos += 1
        self._show_card()

# ────────────────────────────────────────
#  主 App
# ────────────────────────────────────────
class JapaneseVocabApp(App):
    def build(self):
        Window.clearcolor = C_BG
        words_ref = [load_data()]

        root = BoxLayout(orientation="vertical")
        sm = ScreenManager()
        sm.add_widget(SearchScreen(words_ref))
        sm.add_widget(VocabScreen(words_ref))
        sm.add_widget(CardScreen(words_ref))
        sm.add_widget(ReviewScreen(words_ref))

        nav = NavBar(sm)
        root.add_widget(sm)
        root.add_widget(nav)
        return root

    def get_application_name(self):
        return "日语单词本"


if __name__ == "__main__":
    JapaneseVocabApp().run()
