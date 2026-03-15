#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日语单词本 - Android版本（Kivy）
功能与 py 版本相同，使用 Kivy UI 框架适配移动端
"""

from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, SlideTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
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
import urllib.request
import urllib.parse
import datetime
import threading
import random

# ─────────────────────────────────────────
#  数据文件路径（Android 可写目录）
# ─────────────────────────────────────────
try:
    from android.storage import app_storage_path
    DATA_FILE = os.path.join(app_storage_path(), "vocabulary.json")
except ImportError:
    DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vocabulary.json")

EBBINGHAUS_INTERVALS = [1, 2, 4, 7, 15, 30, 60]

# 颜色
C_PRIMARY   = get_color_from_hex("#2196F3")
C_PRIMARY_D = get_color_from_hex("#1565C0")
C_GREEN     = get_color_from_hex("#4CAF50")
C_RED       = get_color_from_hex("#F44336")
C_WHITE     = get_color_from_hex("#FFFFFF")
C_CARD      = get_color_from_hex("#F8F9FA")
C_TEXT      = get_color_from_hex("#212121")
C_GRAY      = get_color_from_hex("#9E9E9E")
C_BG        = get_color_from_hex("#ECEFF1")

# ─────────────────────────────────────────
#  数据管理
# ─────────────────────────────────────────
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
    entry["add_date"] = today
    entry["review_stage"] = 0
    nxt = datetime.date.today() + datetime.timedelta(days=EBBINGHAUS_INTERVALS[0])
    entry["next_review"] = nxt.isoformat()
    entry["review_count"] = 0
    words.append(entry)
    save_data(words)

def advance_review_stage(words, index):
    w = words[index]
    stage = w.get("review_stage", 0) + 1
    w["review_stage"] = stage
    w["review_count"] = w.get("review_count", 0) + 1
    if stage < len(EBBINGHAUS_INTERVALS):
        nxt = datetime.date.today() + datetime.timedelta(days=EBBINGHAUS_INTERVALS[stage])
        w["next_review"] = nxt.isoformat()
    else:
        w["next_review"] = None
    save_data(words)

def get_due_words(words):
    today = datetime.date.today().isoformat()
    return [(i, w) for i, w in enumerate(words)
            if w.get("next_review") and w["next_review"] <= today]

# ─────────────────────────────────────────
#  网络查询
# ─────────────────────────────────────────
def query_word_online(keyword, callback):
    def _fetch():
        try:
            encoded = urllib.parse.quote(keyword)
            url = f"https://jisho.org/api/v1/search/words?keyword={encoded}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            Clock.schedule_once(lambda dt: callback(data, None))
        except Exception as e:
            Clock.schedule_once(lambda dt: callback(None, str(e)))
    threading.Thread(target=_fetch, daemon=True).start()

def parse_jisho_result(data):
    results = []
    if not data or "data" not in data:
        return results
    for item in data["data"][:5]:
        japanese = item.get("japanese", [])
        word = japanese[0].get("word", "") if japanese else ""
        reading = japanese[0].get("reading", "") if japanese else ""
        senses = item.get("senses", [])
        meanings = []
        for sense in senses:
            meanings.append({
                "definitions": sense.get("english_definitions", []),
                "parts_of_speech": sense.get("parts_of_speech", []),
                "info": sense.get("info", []),
            })
        results.append({
            "word": word,
            "reading": reading,
            "meanings": meanings,
            "is_common": item.get("is_common", False),
            "jlpt": item.get("jlpt", []),
        })
    return results

# ─────────────────────────────────────────
#  通用 UI 工具
# ─────────────────────────────────────────
def make_button(text, bg=None, text_color=None, height=dp(48), **kwargs):
    bg = bg or C_PRIMARY
    text_color = text_color or C_WHITE
    btn = Button(
        text=text,
        size_hint_y=None,
        height=height,
        background_color=bg,
        color=text_color,
        font_size=sp(15),
        **kwargs
    )
    return btn

def make_label(text, font_size=sp(14), color=None, bold=False,
               halign="left", **kwargs):
    color = color or C_TEXT
    lbl = Label(
        text=text,
        font_size=font_size,
        color=color,
        bold=bold,
        halign=halign,
        text_size=(None, None),
        **kwargs
    )
    lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
    return lbl

def show_popup(title, message, on_close=None):
    content = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
    content.add_widget(Label(text=message, font_size=sp(14),
                              color=C_TEXT, text_size=(dp(260), None),
                              size_hint_y=None, height=dp(80)))
    btn = make_button("确定", height=dp(44))
    content.add_widget(btn)
    popup = Popup(title=title, content=content,
                  size_hint=(0.85, None), height=dp(200))
    btn.bind(on_press=lambda *a: popup.dismiss())
    if on_close:
        popup.bind(on_dismiss=lambda *a: on_close())
    popup.open()

# ─────────────────────────────────────────
#  底部导航栏
# ─────────────────────────────────────────
class NavBar(BoxLayout):
    def __init__(self, sm, **kwargs):
        super().__init__(orientation="horizontal", size_hint_y=None,
                         height=dp(56), **kwargs)
        self.sm = sm
        self._btns = {}
        tabs = [
            ("search_screen",  "🔍 查询"),
            ("vocab_screen",   "📚 生词本"),
            ("card_screen",    "🃏 卡片"),
            ("review_screen",  "🧠 复习"),
        ]
        for screen_name, label in tabs:
            btn = ToggleButton(
                text=label,
                group="nav",
                font_size=sp(12),
                background_color=C_PRIMARY_D,
                color=C_WHITE,
                background_down="atlas://data/images/defaulttheme/button_pressed",
            )
            btn.bind(on_press=lambda inst, sn=screen_name: self._switch(sn))
            self.add_widget(btn)
            self._btns[screen_name] = btn
        self._btns["search_screen"].state = "down"

    def _switch(self, screen_name):
        self.sm.transition = SlideTransition()
        self.sm.current = screen_name

# ─────────────────────────────────────────
#  查询页面
# ─────────────────────────────────────────
class SearchScreen(Screen):
    def __init__(self, words_ref, **kwargs):
        super().__init__(name="search_screen", **kwargs)
        self.words_ref = words_ref
        self.search_results = []
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        # 搜索栏
        search_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        self.search_input = TextInput(
            hint_text="输入日语单词（汉字/假名/罗马字）",
            multiline=False, font_size=sp(15),
            size_hint_x=0.75
        )
        self.search_input.bind(on_text_validate=self._do_search)
        search_row.add_widget(self.search_input)
        btn_search = make_button("查询", size_hint_x=0.25)
        btn_search.bind(on_press=self._do_search)
        search_row.add_widget(btn_search)
        root.add_widget(search_row)

        self.status_label = make_label("", font_size=sp(12), color=C_GRAY)
        self.status_label.size_hint_y = None
        self.status_label.height = dp(20)
        root.add_widget(self.status_label)

        # 滚动结果
        scroll = ScrollView()
        self.result_layout = BoxLayout(
            orientation="vertical", spacing=dp(10),
            size_hint_y=None, padding=(0, dp(4))
        )
        self.result_layout.bind(minimum_height=self.result_layout.setter("height"))
        scroll.add_widget(self.result_layout)
        root.add_widget(scroll)
        self.add_widget(root)

    def _do_search(self, *args):
        kw = self.search_input.text.strip()
        if not kw:
            return
        self.status_label.text = "查询中..."
        self.result_layout.clear_widgets()
        query_word_online(kw, self._on_result)

    def _on_result(self, data, err):
        if err:
            self.status_label.text = f"查询失败：{err}"
            return
        results = parse_jisho_result(data)
        self.search_results = results
        self.status_label.text = f"找到 {len(results)} 个结果" if results else "未找到结果"
        self.result_layout.clear_widgets()
        for r in results:
            self._add_result_card(r)

    def _add_result_card(self, r):
        card = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(6),
                         size_hint_y=None)
        card.bind(minimum_height=card.setter("height"))

        # 单词行
        word_text = r["word"] or r["reading"]
        reading = f"【{r['reading']}】" if r["word"] and r["reading"] else ""
        jlpt_tags = " ".join(t.upper() for t in r.get("jlpt", []))
        common = "★常用" if r.get("is_common") else ""
        header_text = f"[b][size=20sp][color=1A237E]{word_text}[/color][/size][/b]  [size=14sp][color=5C6BC0]{reading}[/color][/size]  [size=12sp][color=2E7D32]{common} {jlpt_tags}[/color][/size]"
        lbl = Label(text=header_text, markup=True,
                    size_hint_y=None, height=dp(40),
                    text_size=(Window.width - dp(40), None), halign="left")
        card.add_widget(lbl)

        # 释义
        defs_lines = []
        for i, m in enumerate(r["meanings"][:4]):
            pos = "、".join(m.get("parts_of_speech", []))
            defs = "；".join(m.get("definitions", []))
            info_str = "（" + "、".join(m.get("info", [])) + "）" if m.get("info") else ""
            line = f"{i+1}. [{pos}] {defs} {info_str}" if pos else f"{i+1}. {defs} {info_str}"
            defs_lines.append(line)
        defs_text = "\n".join(defs_lines)
        lbl_def = Label(text=defs_text, size_hint_y=None,
                        text_size=(Window.width - dp(40), None),
                        halign="left", font_size=sp(13), color=C_TEXT)
        lbl_def.bind(texture_size=lambda inst, val: setattr(inst, "height", val[1] + dp(8)))
        card.add_widget(lbl_def)

        # 备注 + 加入按钮
        note_row = BoxLayout(size_hint_y=None, height=dp(44), spacing=dp(8))
        note_input = TextInput(hint_text="备注（可选）", multiline=False,
                               font_size=sp(13), size_hint_x=0.55)
        note_row.add_widget(note_input)
        btn_add = make_button("➕ 加入生词本", size_hint_x=0.45, height=dp(44))
        def _add(inst, r=r, note_input=note_input):
            self._add_to_vocab(r, note_input.text.strip())
        btn_add.bind(on_press=_add)
        note_row.add_widget(btn_add)
        card.add_widget(note_row)

        # 分隔
        sep = BoxLayout(size_hint_y=None, height=dp(1))
        sep.canvas.before  # just a spacer
        card.add_widget(sep)

        self.result_layout.add_widget(card)

    def _add_to_vocab(self, r, note):
        word_text = r["word"] or r["reading"]
        words = self.words_ref[0]
        if any(w.get("word") == word_text for w in words):
            show_popup("提示", f"「{word_text}」已在生词本中！")
            return
        meanings_list = []
        for m in r["meanings"][:4]:
            meanings_list.append({
                "pos": "、".join(m.get("parts_of_speech", [])),
                "defs": "；".join(m.get("definitions", [])),
                "info": "、".join(m.get("info", [])) if m.get("info") else ""
            })
        entry = {
            "word": word_text,
            "reading": r["reading"],
            "meanings": meanings_list,
            "jlpt": r.get("jlpt", []),
            "is_common": r.get("is_common", False),
            "note": note,
        }
        add_word(words, entry)
        show_popup("成功", f"「{word_text}」已加入生词本！")

# ─────────────────────────────────────────
#  生词本页面
# ─────────────────────────────────────────
class VocabScreen(Screen):
    def __init__(self, words_ref, **kwargs):
        super().__init__(name="vocab_screen", **kwargs)
        self.words_ref = words_ref
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8))
        toolbar = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        toolbar.add_widget(make_label("我的生词本", font_size=sp(16), bold=True,
                                      size_hint_x=0.6))
        btn_refresh = make_button("🔄", size_hint_x=0.2, height=dp(44))
        btn_refresh.bind(on_press=lambda *a: self._refresh())
        toolbar.add_widget(btn_refresh)
        root.add_widget(toolbar)

        scroll = ScrollView()
        self.vocab_layout = BoxLayout(orientation="vertical", spacing=dp(6),
                                      size_hint_y=None, padding=(0, dp(4)))
        self.vocab_layout.bind(minimum_height=self.vocab_layout.setter("height"))
        scroll.add_widget(self.vocab_layout)
        root.add_widget(scroll)
        self.add_widget(root)
        self._refresh()

    def on_enter(self):
        self._refresh()

    def _refresh(self):
        words = load_data()
        self.words_ref[0] = words
        self.vocab_layout.clear_widgets()
        if not words:
            self.vocab_layout.add_widget(
                make_label("生词本为空，先去查询添加单词吧！",
                           color=C_GRAY, halign="center"))
            return
        for i, w in enumerate(words):
            self._add_word_row(i, w)

    def _add_word_row(self, idx, w):
        row = BoxLayout(size_hint_y=None, height=dp(72), spacing=dp(8),
                        padding=(dp(8), dp(4)))
        word_text = w.get("word") or w.get("reading", "")
        reading = w.get("reading", "")
        defs_first = ""
        if w.get("meanings"):
            defs_first = w["meanings"][0].get("defs", "")[:35]
        next_rev = w.get("next_review") or "已掌握"
        stage = w.get("review_stage", 0)

        info_col = BoxLayout(orientation="vertical", size_hint_x=0.75)
        lbl_word = Label(
            text=f"[b][size=17sp][color=1A237E]{word_text}[/color][/size][/b]"
                 + (f"  [size=13sp][color=5C6BC0]【{reading}】[/color][/size]" if reading and reading != word_text else ""),
            markup=True, halign="left",
            text_size=(Window.width * 0.65, None), size_hint_y=0.5
        )
        info_col.add_widget(lbl_word)
        lbl_def = Label(text=defs_first, font_size=sp(12), color=C_GRAY,
                        halign="left", text_size=(Window.width * 0.65, None),
                        size_hint_y=0.3)
        info_col.add_widget(lbl_def)
        lbl_rev = Label(text=f"下次复习：{next_rev}  阶段{stage+1}",
                        font_size=sp(11), color=C_GRAY,
                        halign="left", text_size=(Window.width * 0.65, None),
                        size_hint_y=0.2)
        info_col.add_widget(lbl_rev)
        row.add_widget(info_col)

        btn_del = make_button("🗑", bg=C_RED, size_hint_x=0.15, height=dp(44))
        btn_del.bind(on_press=lambda inst, i=idx: self._delete_word(i))
        row.add_widget(btn_del)
        self.vocab_layout.add_widget(row)

    def _delete_word(self, idx):
        words = self.words_ref[0]
        if idx < len(words):
            word_text = words[idx].get("word", "")
            words.pop(idx)
            save_data(words)
            self.words_ref[0] = words
            show_popup("已删除", f"「{word_text}」已从生词本删除")
            self._refresh()

# ─────────────────────────────────────────
#  单词卡片页面
# ─────────────────────────────────────────
class CardScreen(Screen):
    def __init__(self, words_ref, **kwargs):
        super().__init__(name="card_screen", **kwargs)
        self.words_ref = words_ref
        self.card_deck = []
        self.card_index = 0
        self.card_revealed = False
        self.card_mode = "jp2cn"  # jp2cn or cn2jp
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(10))

        # 模式选择
        mode_row = BoxLayout(size_hint_y=None, height=dp(48), spacing=dp(8))
        btn_jp2cn = ToggleButton(text="日→中", group="card_mode", state="down",
                                  font_size=sp(14))
        btn_cn2jp = ToggleButton(text="中→日", group="card_mode",
                                  font_size=sp(14))
        btn_jp2cn.bind(on_press=lambda *a: setattr(self, "card_mode", "jp2cn"))
        btn_cn2jp.bind(on_press=lambda *a: setattr(self, "card_mode", "cn2jp"))
        mode_row.add_widget(btn_jp2cn)
        mode_row.add_widget(btn_cn2jp)
        btn_start = make_button("🔀 随机开始", height=dp(48))
        btn_start.bind(on_press=lambda *a: self._start_cards())
        mode_row.add_widget(btn_start)
        root.add_widget(mode_row)

        # 进度
        self.progress_label = make_label("", font_size=sp(12), color=C_GRAY,
                                          halign="center")
        self.progress_label.size_hint_y = None
        self.progress_label.height = dp(22)
        root.add_widget(self.progress_label)

        # 卡片
        self.card_box = BoxLayout(orientation="vertical",
                                   size_hint=(1, 0.5))
        self.card_top_lbl = make_label("", font_size=sp(12), color=C_GRAY,
                                        halign="center")
        self.card_main_lbl = make_label("点击「随机开始」", font_size=sp(24),
                                         color=C_PRIMARY_D, bold=True,
                                         halign="center")
        self.card_sub_lbl = make_label("", font_size=sp(14), color=C_TEXT,
                                        halign="center")
        self.card_box.add_widget(self.card_top_lbl)
        self.card_box.add_widget(self.card_main_lbl)
        self.card_box.add_widget(self.card_sub_lbl)
        root.add_widget(self.card_box)

        # 按钮行
        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(8))
        self.btn_reveal = make_button("翻面查看答案")
        self.btn_reveal.bind(on_press=lambda *a: self._reveal_card())
        btn_prev = make_button("⬅ 上一张", bg=C_GRAY)
        btn_prev.bind(on_press=lambda *a: self._prev_card())
        btn_next = make_button("下一张 ➡", bg=C_GRAY)
        btn_next.bind(on_press=lambda *a: self._next_card())
        btn_row.add_widget(btn_prev)
        btn_row.add_widget(self.btn_reveal)
        btn_row.add_widget(btn_next)
        root.add_widget(btn_row)
        self.add_widget(root)

    def on_enter(self):
        # 刷新单词列表
        pass

    def _start_cards(self):
        words = load_data()
        self.words_ref[0] = words
        if not words:
            show_popup("提示", "生词本为空，请先添加单词！")
            return
        self.card_deck = list(range(len(words)))
        random.shuffle(self.card_deck)
        self.card_index = 0
        self.card_revealed = False
        self._show_card()

    def _show_card(self):
        words = self.words_ref[0]
        if not self.card_deck:
            return
        idx = self.card_deck[self.card_index]
        w = words[idx]
        self.card_revealed = False
        self.progress_label.text = f"第 {self.card_index+1} / {len(self.card_deck)} 张"

        word_text = w.get("word") or w.get("reading", "")
        reading = w.get("reading", "")
        meanings = w.get("meanings", [])
        defs_text = "\n".join(
            f"{i+1}. [{m.get('pos','')}] {m.get('defs','')}"
            for i, m in enumerate(meanings[:3])
        )

        if self.card_mode == "jp2cn":
            self.card_top_lbl.text = "日语单词"
            self.card_main_lbl.text = word_text
            self.card_main_lbl.color = C_PRIMARY_D
            rtext = f"【{reading}】" if reading and reading != word_text else ""
            self.card_sub_lbl.text = rtext
            self._answer_text = defs_text
        else:
            self.card_top_lbl.text = "中文释义"
            self.card_main_lbl.text = defs_text[:80] if defs_text else "（无释义）"
            self.card_main_lbl.color = get_color_from_hex("#1B5E20")
            self.card_sub_lbl.text = ""
            self._answer_text = word_text + (f"\n【{reading}】" if reading else "")

        self.btn_reveal.text = "翻面查看答案"

    def _reveal_card(self):
        if not self.card_revealed:
            self.card_revealed = True
            if self.card_mode == "jp2cn":
                self.card_sub_lbl.text = self._answer_text
            else:
                self.card_sub_lbl.text = self._answer_text
                self.card_sub_lbl.color = C_PRIMARY_D
            self.btn_reveal.text = "已翻面 ✓"

    def _next_card(self):
        if not self.card_deck:
            return
        self.card_index = (self.card_index + 1) % len(self.card_deck)
        self._show_card()

    def _prev_card(self):
        if not self.card_deck:
            return
        self.card_index = (self.card_index - 1) % len(self.card_deck)
        self._show_card()

# ─────────────────────────────────────────
#  艾宾浩斯复习页面
# ─────────────────────────────────────────
class ReviewScreen(Screen):
    def __init__(self, words_ref, **kwargs):
        super().__init__(name="review_screen", **kwargs)
        self.words_ref = words_ref
        self.review_queue = []
        self.review_pos = 0
        self._review_revealed = False
        self._build()

    def _build(self):
        root = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))

        # 标题
        title_row = BoxLayout(size_hint_y=None, height=dp(48))
        title_row.add_widget(make_label("🧠 艾宾浩斯复习", font_size=sp(16), bold=True))
        btn_load = make_button("刷新今日任务", size_hint_x=0.45)
        btn_load.bind(on_press=lambda *a: self._load_session())
        title_row.add_widget(btn_load)
        root.add_widget(title_row)

        desc = "复习间隔：1→2→4→7→15→30→60天"
        root.add_widget(make_label(desc, font_size=sp(11), color=C_GRAY))

        # 进度
        self.progress_label = make_label("", font_size=sp(12), color=C_GRAY,
                                          halign="center", size_hint_y=None)
        self.progress_label.height = dp(22)
        root.add_widget(self.progress_label)

        # 卡片
        self.card_area = BoxLayout(orientation="vertical",
                                    size_hint=(1, 0.45))
        self.status_lbl = make_label("点击「刷新今日任务」开始复习",
                                      font_size=sp(14), color=C_GRAY, halign="center")
        self.card_word_lbl = make_label("", font_size=sp(24),
                                         color=C_PRIMARY_D, bold=True, halign="center")
        self.card_reading_lbl = make_label("", font_size=sp(14),
                                            color=C_PRIMARY, halign="center")
        self.card_stage_lbl = make_label("", font_size=sp(11),
                                          color=C_GRAY, halign="center")
        self.card_ans_lbl = make_label("", font_size=sp(13),
                                        color=C_TEXT, halign="center")
        self.card_area.add_widget(self.status_lbl)
        self.card_area.add_widget(self.card_word_lbl)
        self.card_area.add_widget(self.card_reading_lbl)
        self.card_area.add_widget(self.card_stage_lbl)
        self.card_area.add_widget(self.card_ans_lbl)
        root.add_widget(self.card_area)

        # 操作按钮
        btn_row = BoxLayout(size_hint_y=None, height=dp(52), spacing=dp(6))
        self.btn_show = make_button("显示答案")
        self.btn_show.bind(on_press=lambda *a: self._reveal())
        self.btn_ok = make_button("✅ 已记住", bg=C_GREEN)
        self.btn_ok.bind(on_press=lambda *a: self._known())
        self.btn_fail = make_button("❌ 没记住", bg=C_RED)
        self.btn_fail.bind(on_press=lambda *a: self._unknown())
        btn_row.add_widget(self.btn_show)
        btn_row.add_widget(self.btn_ok)
        btn_row.add_widget(self.btn_fail)
        root.add_widget(btn_row)
        self.add_widget(root)

    def on_enter(self):
        self._load_session()

    def _load_session(self):
        words = load_data()
        self.words_ref[0] = words
        due = get_due_words(words)
        if not due:
            self.status_lbl.text = "🎉 今天没有需要复习的单词！"
            self._hide_card_widgets()
            self.progress_label.text = ""
            return
        self.review_queue = due
        self.review_pos = 0
        self._show_card()

    def _hide_card_widgets(self):
        for w in [self.card_word_lbl, self.card_reading_lbl,
                  self.card_stage_lbl, self.card_ans_lbl]:
            w.text = ""

    def _show_card(self):
        words = self.words_ref[0]
        if self.review_pos >= len(self.review_queue):
            self.status_lbl.text = "🎉 今日复习完成！加油！"
            self._hide_card_widgets()
            self.progress_label.text = ""
            return

        total = len(self.review_queue)
        self.progress_label.text = f"今日待复习：{self.review_pos+1} / {total}"
        self.status_lbl.text = ""

        idx, w = self.review_queue[self.review_pos]
        word_text = w.get("word") or w.get("reading", "")
        reading = w.get("reading", "")
        stage = w.get("review_stage", 0)
        interval = EBBINGHAUS_INTERVALS[stage] if stage < len(EBBINGHAUS_INTERVALS) else "已掌握"

        self.card_word_lbl.text = word_text
        self.card_reading_lbl.text = f"【{reading}】" if reading and reading != word_text else ""
        self.card_stage_lbl.text = f"阶段 {stage+1} | 下次间隔 {interval} 天"

        meanings = w.get("meanings", [])
        defs_text = "\n".join(
            f"{i+1}. [{m.get('pos','')}] {m.get('defs','')}"
            for i, m in enumerate(meanings[:3])
        )
        self._answer = defs_text
        self.card_ans_lbl.text = ""
        self._review_revealed = False
        self.btn_show.text = "显示答案"

    def _reveal(self):
        if not self._review_revealed:
            self._review_revealed = True
            self.card_ans_lbl.text = self._answer
            self.btn_show.text = "已显示 ✓"

    def _known(self):
        if not self.review_queue or self.review_pos >= len(self.review_queue):
            return
        idx, _ = self.review_queue[self.review_pos]
        words = self.words_ref[0]
        advance_review_stage(words, idx)
        self.words_ref[0] = words
        self.review_pos += 1
        self._show_card()

    def _unknown(self):
        if not self.review_queue or self.review_pos >= len(self.review_queue):
            return
        idx, w = self.review_queue[self.review_pos]
        words = self.words_ref[0]
        words[idx]["review_stage"] = 0
        tomorrow = datetime.date.today() + datetime.timedelta(days=1)
        words[idx]["next_review"] = tomorrow.isoformat()
        save_data(words)
        self.words_ref[0] = words
        self.review_pos += 1
        self._show_card()

# ─────────────────────────────────────────
#  主 App
# ─────────────────────────────────────────
class JapaneseVocabKivyApp(App):
    def build(self):
        Window.clearcolor = C_BG

        self.words = [load_data()]  # 用列表包装使其可变引用
        words_ref = self.words

        root = BoxLayout(orientation="vertical")

        # 页面管理器
        sm = ScreenManager()
        sm.add_widget(SearchScreen(words_ref))
        sm.add_widget(VocabScreen(words_ref))
        sm.add_widget(CardScreen(words_ref))
        sm.add_widget(ReviewScreen(words_ref))

        # 底部导航
        nav = NavBar(sm)

        root.add_widget(sm)
        root.add_widget(nav)
        return root

    def get_application_name(self):
        return "日语单词本"


if __name__ == "__main__":
    JapaneseVocabKivyApp().run()
