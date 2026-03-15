#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将 JMdict XML 解析为 SQLite 词典数据库
输出：jmdict.db（可直接内嵌进各版本软件）

表结构：
  entries(id, kanji, reading, meanings_json, jlpt, is_common)
  kanji_index(kanji, entry_id)        -- 汉字快速检索
  reading_index(reading, entry_id)    -- 读音快速检索

中文映射：
  JMdict 本身含有 Chinese (Mandarin) gloss（xml:lang="zh" / "zh_CN"）
  若没有中文则保留英文，前端显示时标注"(英文释义)"
"""

import gzip, xml.etree.ElementTree as ET, sqlite3, json, os, sys, re

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GZ_FILE    = os.path.join(SCRIPT_DIR, "JMdict.gz")
DB_OUT     = os.path.join(SCRIPT_DIR, "jmdict.db")

# JMdict 实体展开表（避免 XML 解析报错）
JMDICT_ENTITIES = {
    # 词性
    "adj-f":"連体詞", "adj-i":"形容詞（い形）", "adj-ix":"形容詞（いい/よい）",
    "adj-kari":"形容詞（かり活用）", "adj-ku":"形容詞（く活用）", "adj-na":"形容動詞（な形）",
    "adj-nari":"形容動詞（なり活用）", "adj-no":"の形容詞", "adj-pn":"指示詞",
    "adj-shiku":"形容詞（しく活用）", "adj-t":"たる形容詞",
    "adv":"副詞", "adv-to":"副詞（と）",
    "aux":"助動詞", "aux-adj":"助動詞（形容詞型）", "aux-v":"助動詞（動詞型）",
    "conj":"接続詞", "cop":"コピュラ", "ctr":"助数詞",
    "exp":"表現", "int":"感動詞", "n":"名詞", "n-adv":"副詞的名詞",
    "n-pr":"固有名詞", "n-pref":"名詞（接頭）", "n-suf":"名詞（接尾）",
    "n-t":"時間名詞", "num":"数詞", "pn":"代名詞", "pref":"接頭辞",
    "prt":"助詞", "suf":"接尾辞", "unc":"未分類",
    "v1":"一段動詞", "v1-s":"一段動詞（特殊）",
    "v2a-s":"二段動詞（ア段）", "v4h":"四段動詞（ハ行）", "v4r":"四段動詞（ラ行）",
    "v5aru":"五段動詞（ある）", "v5b":"五段動詞（ぶ）", "v5g":"五段動詞（ぐ）",
    "v5k":"五段動詞（く）", "v5k-s":"五段動詞（いく）", "v5m":"五段動詞（む）",
    "v5n":"五段動詞（ぬ）", "v5r":"五段動詞（る）", "v5r-i":"五段動詞（る不規則）",
    "v5s":"五段動詞（す）", "v5t":"五段動詞（つ）", "v5u":"五段動詞（う）",
    "v5u-s":"五段動詞（う特殊）", "v5uru":"五段動詞（うる）",
    "vi":"自動詞", "vk":"カ変動詞", "vn":"ナ変動詞", "vr":"ラ変動詞",
    "vs":"サ変動詞", "vs-c":"サ変動詞（特殊）", "vs-i":"サ変動詞（する）",
    "vs-s":"サ変動詞（特殊す）", "vt":"他動詞", "vz":"ざ変動詞",
    # 其他常见实体
    "MA":"MA", "X":"X", "abbr":"略語", "arch":"古語",
    "chn":"幼児語", "col":"口語", "derog":"侮辱語", "euph":"婉曲語",
    "fam":"くだけた表現", "fem":"女性語", "hon":"丁寧語", "hum":"謙譲語",
    "id":"慣用句", "io":"不規則な読み", "joc":"冗談表現",
    "lit":"文語", "male":"男性語", "obs":"廃語", "obsc":"難解語",
    "on-mim":"擬音語・擬態語", "poet":"詩的表現", "pol":"丁寧表現",
    "rare":"まれ", "sens":"感覚的表現", "sl":"俗語", "uk":"通常かな書き",
    "uK":"通常漢字書き", "vulg":"卑語", "yoji":"四字熟語",
    "ksb":"関西弁", "ktb":"北東方言", "kyb":"京都弁", "kyu":"九州弁",
    "nab":"名古屋弁", "osb":"大阪弁", "rkb":"琉球語", "thb":"東北弁",
    "tsb":"土佐弁", "tsug":"津軽弁",
    "news1":"頻出（1位）", "news2":"頻出（2位）",
    "ichi1":"市中頻出（1）", "ichi2":"市中頻出（2）",
    "spec1":"特殊（1）", "spec2":"特殊（2）",
    "gai1":"外来語（1）", "gai2":"外来語（2）",
    "nf01":"nf01","nf02":"nf02","nf03":"nf03","nf04":"nf04",
    "nf05":"nf05","nf06":"nf06","nf07":"nf07","nf08":"nf08",
    "nf09":"nf09","nf10":"nf10","nf11":"nf11","nf12":"nf12",
    "nf13":"nf13","nf14":"nf14","nf15":"nf15","nf16":"nf16",
    "nf17":"nf17","nf18":"nf18","nf19":"nf19","nf20":"nf20",
    "nf21":"nf21","nf22":"nf22","nf23":"nf23","nf24":"nf24",
    "nf25":"nf25","nf26":"nf26","nf27":"nf27","nf28":"nf28",
    "nf29":"nf29","nf30":"nf30","nf31":"nf31","nf32":"nf32",
    "nf33":"nf33","nf34":"nf34","nf35":"nf35","nf36":"nf36",
    "nf37":"nf37","nf38":"nf38","nf39":"nf39","nf40":"nf40",
    "nf41":"nf41","nf42":"nf42","nf43":"nf43","nf44":"nf44",
    "nf45":"nf45","nf46":"nf46","nf47":"nf47","nf48":"nf48",
    "P":"常用", "iK":"不規則漢字",
}

def patch_xml(raw: bytes) -> bytes:
    """替换 DOCTYPE/实体声明，避免 ElementTree 报错"""
    # 移除整个 DOCTYPE 块
    raw = re.sub(rb'<!DOCTYPE[^[]*\[.*?\]>', b'', raw, flags=re.DOTALL)
    # 替换所有实体引用 &xxx; → 对应文字
    def repl(m):
        key = m.group(1).decode()
        val = JMDICT_ENTITIES.get(key, key)
        return val.encode("utf-8")
    raw = re.sub(rb'&([A-Za-z0-9_-]+);', repl, raw)
    return raw

def parse_entry(entry_el):
    """解析单个 <entry>，返回 dict 或 None"""
    # 汉字形式
    kanji_list = [k.findtext("keb", "").strip()
                  for k in entry_el.findall("k_ele")]
    kanji_list = [k for k in kanji_list if k]

    # 读音
    reading_list = [r.findtext("reb", "").strip()
                    for r in entry_el.findall("r_ele")]
    reading_list = [r for r in reading_list if r]

    if not kanji_list and not reading_list:
        return None

    # 词义
    senses = []
    for sense_el in entry_el.findall("sense"):
        # 优先取中文 gloss
        zh_glosses = []
        en_glosses = []
        for g in sense_el.findall("gloss"):
            lang = g.get("{http://www.w3.org/XML/1998/namespace}lang", "eng")
            txt = (g.text or "").strip()
            if not txt:
                continue
            if lang in ("zhs", "zh", "zh_CN", "cmn"):
                zh_glosses.append(txt)
            elif lang in ("eng", "en", ""):
                en_glosses.append(txt)

        glosses = zh_glosses if zh_glosses else en_glosses
        is_chinese = bool(zh_glosses)

        if not glosses:
            continue

        # 词性
        pos_list = [p.text or "" for p in sense_el.findall("pos") if p.text]
        # 例句
        examples = []
        for ex_el in sense_el.findall("example"):
            ja = ex_el.findtext("ex_sent[@{http://www.w3.org/XML/1998/namespace}lang='jpn']") or ""
            # ElementTree 不支持含命名空间属性的选择器，手动遍历
            ja, zh_ex = "", ""
            for s in ex_el.findall("ex_sent"):
                lang = s.get("{http://www.w3.org/XML/1998/namespace}lang", "")
                if lang == "jpn":
                    ja = s.text or ""
                elif lang in ("zhs", "zh", "cmn"):
                    zh_ex = s.text or ""
            if ja:
                examples.append({"ja": ja.strip(), "zh": zh_ex.strip()})

        # misc / field
        misc = [m.text or "" for m in sense_el.findall("misc") if m.text]
        field = [f.text or "" for f in sense_el.findall("field") if f.text]

        senses.append({
            "glosses": glosses,
            "is_chinese": is_chinese,
            "pos": pos_list,
            "misc": misc,
            "field": field,
            "examples": examples[:2],  # 最多保留2条例句
        })

    if not senses:
        return None

    # JLPT / 常用标记（来自 ke_pri / re_pri）
    pri_vals = set()
    for k in entry_el.findall("k_ele"):
        for p in k.findall("ke_pri"):
            if p.text: pri_vals.add(p.text)
    for r in entry_el.findall("r_ele"):
        for p in r.findall("re_pri"):
            if p.text: pri_vals.add(p.text)
    is_common = any(v in pri_vals for v in ("news1","news2","ichi1","ichi2","spec1","spec2","gai1","gai2"))

    return {
        "kanji":    kanji_list,
        "reading":  reading_list,
        "senses":   senses,
        "is_common": is_common,
    }

def build_db():
    if not os.path.exists(GZ_FILE):
        print(f"❌ 找不到 {GZ_FILE}")
        sys.exit(1)

    print("📖 读取并解析 JMdict XML…")
    with gzip.open(GZ_FILE, "rb") as f:
        raw = f.read()

    print(f"   原始大小：{len(raw)//1024//1024} MB，开始修复实体…")
    raw = patch_xml(raw)

    print("   解析 XML 树…")
    root = ET.fromstring(raw)
    del raw  # 释放内存

    print("💾 创建 SQLite 数据库…")
    if os.path.exists(DB_OUT):
        os.remove(DB_OUT)
    conn = sqlite3.connect(DB_OUT)
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE entries (
            id          INTEGER PRIMARY KEY,
            kanji       TEXT,
            reading     TEXT,
            meanings    TEXT,
            is_common   INTEGER DEFAULT 0
        );
        CREATE TABLE kanji_idx (
            form    TEXT NOT NULL,
            eid     INTEGER NOT NULL
        );
        CREATE TABLE reading_idx (
            form    TEXT NOT NULL,
            eid     INTEGER NOT NULL
        );
    """)

    eid = 0
    skipped = 0
    batch_k, batch_r, batch_e = [], [], []

    print("🔄 导入词条…")
    for entry_el in root.findall("entry"):
        parsed = parse_entry(entry_el)
        if parsed is None:
            skipped += 1
            continue

        kanji_str   = "｜".join(parsed["kanji"])
        reading_str = "｜".join(parsed["reading"])
        meanings_json = json.dumps(parsed["senses"], ensure_ascii=False)
        is_common   = 1 if parsed["is_common"] else 0

        batch_e.append((eid, kanji_str, reading_str, meanings_json, is_common))
        for k in parsed["kanji"]:
            batch_k.append((k, eid))
        for r in parsed["reading"]:
            batch_r.append((r, eid))

        eid += 1
        if eid % 10000 == 0:
            c.executemany("INSERT INTO entries VALUES(?,?,?,?,?)", batch_e)
            c.executemany("INSERT INTO kanji_idx VALUES(?,?)", batch_k)
            c.executemany("INSERT INTO reading_idx VALUES(?,?)", batch_r)
            batch_e, batch_k, batch_r = [], [], []
            print(f"   已导入 {eid} 条…", end="\r")

    # 剩余
    if batch_e:
        c.executemany("INSERT INTO entries VALUES(?,?,?,?,?)", batch_e)
        c.executemany("INSERT INTO kanji_idx VALUES(?,?)", batch_k)
        c.executemany("INSERT INTO reading_idx VALUES(?,?)", batch_r)

    print(f"\n   导入完成：{eid} 条，跳过 {skipped} 条")

    print("🏗  建立索引…")
    c.executescript("""
        CREATE INDEX idx_kanji   ON kanji_idx(form);
        CREATE INDEX idx_reading ON reading_idx(form);
    """)
    conn.commit()
    conn.close()

    size_mb = os.path.getsize(DB_OUT) / 1024 / 1024
    print(f"✅ 词典数据库已生成：{DB_OUT}  ({size_mb:.1f} MB)")

if __name__ == "__main__":
    build_db()
