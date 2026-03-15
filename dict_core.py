#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
离线词典查询核心模块
- 优先查询内嵌 SQLite 词典（jmdict.db，21万条）
- 词典查不到时自动联网查询 Jisho API
- 支持：汉字、平假名、片假名、罗马字（Hepburn）检索
- 零第三方依赖：仅使用 Python 标准库
"""

import sqlite3
import json
import os
import sys
import urllib.request
import urllib.parse
import threading

# ──────────────────────────────────────────────
#  路径解析：支持 PyInstaller _MEIPASS 临时目录
# ──────────────────────────────────────────────
def _get_db_path():
    if hasattr(sys, '_MEIPASS'):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(base, "jmdict.db"),
        os.path.join(base, "dict", "jmdict.db"),
        os.path.join(os.path.dirname(base), "jmdict.db"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None

DB_PATH = _get_db_path()

# ──────────────────────────────────────────────
#  罗马字 → 平假名
# ──────────────────────────────────────────────
_ROMAJI_TABLE = [
    ("shi","し"),("chi","ち"),("tsu","つ"),("dzu","づ"),
    ("sha","しゃ"),("shu","しゅ"),("sho","しょ"),
    ("cha","ちゃ"),("chu","ちゅ"),("cho","ちょ"),
    ("kya","きゃ"),("kyu","きゅ"),("kyo","きょ"),
    ("gya","ぎゃ"),("gyu","ぎゅ"),("gyo","ぎょ"),
    ("nya","にゃ"),("nyu","にゅ"),("nyo","にょ"),
    ("hya","ひゃ"),("hyu","ひゅ"),("hyo","ひょ"),
    ("bya","びゃ"),("byu","びゅ"),("byo","びょ"),
    ("pya","ぴゃ"),("pyu","ぴゅ"),("pyo","ぴょ"),
    ("mya","みゃ"),("myu","みゅ"),("myo","みょ"),
    ("rya","りゃ"),("ryu","りゅ"),("ryo","りょ"),
    ("ka","か"),("ki","き"),("ku","く"),("ke","け"),("ko","こ"),
    ("ga","が"),("gi","ぎ"),("gu","ぐ"),("ge","げ"),("go","ご"),
    ("sa","さ"),("su","す"),("se","せ"),("so","そ"),
    ("za","ざ"),("zu","ず"),("ze","ぜ"),("zo","ぞ"),
    ("ta","た"),("te","て"),("to","と"),
    ("da","だ"),("de","で"),("do","ど"),
    ("na","な"),("ni","に"),("nu","ぬ"),("ne","ね"),("no","の"),
    ("ha","は"),("hi","ひ"),("fu","ふ"),("he","へ"),("ho","ほ"),
    ("ba","ば"),("bi","び"),("bu","ぶ"),("be","べ"),("bo","ぼ"),
    ("pa","ぱ"),("pi","ぴ"),("pu","ぷ"),("pe","ぺ"),("po","ぽ"),
    ("ma","ま"),("mi","み"),("mu","む"),("me","め"),("mo","も"),
    ("ya","や"),("yu","ゆ"),("yo","よ"),
    ("ra","ら"),("ri","り"),("ru","る"),("re","れ"),("ro","ろ"),
    ("wa","わ"),("wo","を"),("ji","じ"),("si","し"),("ti","ち"),
    ("a","あ"),("i","い"),("u","う"),("e","え"),("o","お"),("n","ん"),
]

def romaji_to_hiragana(text):
    text = text.lower().strip()
    result = ""
    i = 0
    while i < len(text):
        if i + 1 < len(text) and text[i] == text[i+1] and text[i] not in "aeioun":
            result += "っ"
            i += 1
            continue
        matched = False
        for romaji, kana in _ROMAJI_TABLE:
            if text[i:i+len(romaji)] == romaji:
                result += kana
                i += len(romaji)
                matched = True
                break
        if not matched:
            result += text[i]
            i += 1
    return result

def _is_japanese(text):
    for ch in text:
        cp = ord(ch)
        if 0x3040 <= cp <= 0x9FFF or 0xF900 <= cp <= 0xFAFF:
            return True
    return False

# ──────────────────────────────────────────────
#  英→中翻译映射（内嵌，无需外部文件）
# ──────────────────────────────────────────────
_EN_ZH = {
    "to eat":"吃","to drink":"喝","to go":"去","to come":"来",
    "to see":"看、见","to watch":"观看","to look":"看",
    "to listen":"听","to hear":"听到","to speak":"说话",
    "to say":"说","to tell":"告诉","to talk":"说话、交谈",
    "to read":"读、阅读","to write":"写","to think":"思考、认为",
    "to know":"知道","to understand":"理解、明白",
    "to do":"做","to make":"做、制作","to create":"创造、制作",
    "to use":"使用","to buy":"买","to sell":"卖",
    "to give":"给","to receive":"接受、收到","to take":"拿、取",
    "to bring":"带来","to carry":"携带","to hold":"拿着、持有",
    "to put":"放","to place":"放置","to leave":"离开、留下",
    "to return":"返回、归还","to arrive":"到达","to depart":"出发",
    "to enter":"进入","to exit":"出去、退出","to open":"打开",
    "to close":"关闭","to start":"开始","to begin":"开始",
    "to finish":"结束、完成","to end":"结束","to stop":"停止",
    "to continue":"继续","to stand":"站立","to sit":"坐",
    "to lie down":"躺","to sleep":"睡觉","to wake up":"醒来",
    "to get up":"起床","to run":"跑","to walk":"走",
    "to swim":"游泳","to drive":"驾驶","to ride":"骑、乘坐",
    "to fly":"飞","to work":"工作","to study":"学习",
    "to learn":"学习","to teach":"教","to ask":"问",
    "to answer":"回答","to call":"打电话、叫","to send":"发送",
    "to meet":"见面、遇见","to wait":"等待","to help":"帮助",
    "to try":"尝试","to want":"想要","to need":"需要",
    "to like":"喜欢","to love":"爱","to hate":"讨厌、恨",
    "to feel":"感觉、感受","to become":"变成",
    "to be":"是、在","to have":"有、持有","to exist":"存在",
    "to live":"居住、生活","to die":"死","to be born":"出生",
    "to grow":"成长、生长","to change":"改变",
    "to show":"展示、给看","to find":"找到、发现",
    "to look for":"寻找","to lose":"失去、迷失",
    "to win":"赢","to play":"玩、演奏","to sing":"唱歌",
    "to dance":"跳舞","to draw":"画","to cook":"烹饪、做饭",
    "to clean":"打扫","to wash":"洗","to cut":"切",
    "to break":"打破、折断","to fix":"修理","to build":"建造",
    "to worry":"担心","to hope":"希望",
    "to remember":"记得","to forget":"忘记","to decide":"决定",
    "to choose":"选择","to check":"检查、确认",
    "to agree":"同意","to allow":"允许","to forbid":"禁止",
    "to avoid":"避免","to cause":"引起、造成",
    "to happen":"发生","to seem":"似乎",
    "to appear":"出现、看起来","to disappear":"消失",
    "to increase":"增加","to decrease":"减少",
    "to rise":"上升","to fall":"下降、落下",
    "to throw":"扔、投","to catch":"接住",
    "to push":"推","to pull":"拉","to lift":"举起",
    "to hit":"打、击","to touch":"触摸",
    "to plan":"计划","to prepare":"准备","to practice":"练习",
    "to pay":"支付、付款","to borrow":"借（入）","to lend":"借（出）",
    "to share":"分享","to join":"加入","to visit":"拜访、参观",
    "to invite":"邀请","to introduce":"介绍",
    "to explain":"解释","to describe":"描述",
    "to express":"表达","to translate":"翻译","to count":"数",
    "to calculate":"计算","to measure":"测量",
    "person":"人","people":"人们","man":"男人","woman":"女人",
    "child":"孩子、小孩","adult":"成人","baby":"婴儿",
    "boy":"男孩","girl":"女孩","friend":"朋友","enemy":"敌人",
    "family":"家庭、家人","parent":"父母","father":"父亲",
    "mother":"母亲","son":"儿子","daughter":"女儿",
    "brother":"兄弟","sister":"姐妹","husband":"丈夫","wife":"妻子",
    "relative":"亲戚","neighbor":"邻居","colleague":"同事",
    "classmate":"同学","teacher":"老师","student":"学生",
    "doctor":"医生","nurse":"护士","police":"警察",
    "worker":"工人","employee":"员工","boss":"老板",
    "customer":"顾客","host":"主人","guest":"客人",
    "country":"国家","city":"城市","town":"城镇","village":"村庄",
    "house":"房子","home":"家","building":"建筑物","room":"房间",
    "door":"门","window":"窗户","wall":"墙","road":"道路",
    "street":"街道","bridge":"桥","river":"河流","lake":"湖",
    "sea":"海","ocean":"海洋","mountain":"山","forest":"森林",
    "park":"公园","garden":"花园","sky":"天空","sun":"太阳",
    "moon":"月亮","star":"星星","cloud":"云","rain":"雨",
    "snow":"雪","wind":"风","fire":"火","water":"水",
    "tree":"树","flower":"花","grass":"草","leaf":"叶子",
    "animal":"动物","plant":"植物","bird":"鸟","fish":"鱼",
    "time":"时间","year":"年","month":"月","week":"周、星期",
    "day":"天、日","hour":"小时","minute":"分钟","second":"秒",
    "morning":"早晨","afternoon":"下午","evening":"傍晚","night":"夜晚",
    "today":"今天","yesterday":"昨天","tomorrow":"明天",
    "now":"现在","past":"过去","future":"未来",
    "spring":"春天","summer":"夏天","autumn":"秋天","winter":"冬天",
    "food":"食物","drink":"饮料","meal":"饭、餐","rice":"米、大米",
    "bread":"面包","meat":"肉","vegetable":"蔬菜","fruit":"水果",
    "egg":"鸡蛋","milk":"牛奶","tea":"茶","coffee":"咖啡",
    "sugar":"糖","salt":"盐","book":"书","paper":"纸",
    "pen":"笔","pencil":"铅笔","bag":"袋子、包","box":"箱子",
    "bottle":"瓶子","cup":"杯子","plate":"盘子","bowl":"碗",
    "knife":"刀","chopsticks":"筷子","spoon":"勺子",
    "chair":"椅子","table":"桌子","bed":"床","clothes":"衣服",
    "shirt":"衬衫","shoes":"鞋子","hat":"帽子","coat":"外套",
    "car":"汽车","bus":"公共汽车","train":"火车","airplane":"飞机",
    "bicycle":"自行车","phone":"电话","computer":"电脑",
    "television":"电视","camera":"相机","key":"钥匙","money":"钱",
    "big":"大的","large":"大的","small":"小的","tall":"高的",
    "short":"矮的、短的","long":"长的","wide":"宽的","narrow":"窄的",
    "heavy":"重的","light":"轻的","fast":"快的","slow":"慢的",
    "new":"新的","old":"旧的、老的","young":"年轻的",
    "good":"好的","bad":"坏的","great":"很好的",
    "excellent":"优秀的","terrible":"糟糕的","wonderful":"精彩的",
    "beautiful":"美丽的","ugly":"丑的","cute":"可爱的",
    "clean":"干净的","dirty":"脏的","hot":"热的","cold":"冷的",
    "warm":"暖和的","cool":"凉爽的","hard":"硬的、难的",
    "soft":"软的","easy":"容易的","difficult":"困难的",
    "important":"重要的","necessary":"必要的","possible":"可能的",
    "same":"相同的","different":"不同的","similar":"相似的",
    "special":"特别的","strange":"奇怪的","interesting":"有趣的",
    "boring":"无聊的","funny":"有趣的","serious":"严肃的",
    "kind":"善良的","gentle":"温柔的","strong":"强壮的",
    "weak":"弱的","rich":"富有的","poor":"贫穷的","busy":"忙碌的",
    "free":"空闲的、自由的","tired":"疲惫的","happy":"快乐的",
    "sad":"悲伤的","angry":"生气的","surprised":"惊讶的",
    "afraid":"害怕的","worried":"担心的","safe":"安全的",
    "dangerous":"危险的","healthy":"健康的","sick":"生病的",
    "delicious":"美味的","tasty":"好吃的","fresh":"新鲜的",
    "sweet":"甜的","sour":"酸的","bitter":"苦的","spicy":"辣的",
    "correct":"正确的","wrong":"错误的","true":"真实的",
    "false":"假的","real":"真实的","public":"公共的",
    "private":"私人的","popular":"受欢迎的","common":"常见的",
    "rare":"罕见的","school":"学校","university":"大学",
    "class":"班级、课","lesson":"课程","homework":"作业",
    "test":"考试","exam":"考试","grade":"成绩","language":"语言",
    "body":"身体","head":"头","face":"脸","eye":"眼睛",
    "nose":"鼻子","mouth":"嘴","ear":"耳朵","hand":"手",
    "arm":"手臂","leg":"腿","foot":"脚","finger":"手指",
    "hair":"头发","heart":"心、心脏","stomach":"胃、肚子",
    "love":"爱、喜爱","feeling":"感觉、感情","emotion":"情感",
    "joy":"喜悦","sorrow":"悲伤","anger":"愤怒","fear":"恐惧",
    "excitement":"兴奋","loneliness":"孤独","kindness":"善良",
    "courage":"勇气","patience":"耐心","honesty":"诚实",
    "job":"工作、职业","company":"公司","office":"办公室",
    "meeting":"会议","business":"生意、商业","salary":"工资",
    "restaurant":"餐厅","menu":"菜单","breakfast":"早餐",
    "lunch":"午餐","dinner":"晚餐","snack":"零食",
    "noodles":"面条","sushi":"寿司","ramen":"拉面",
    "udon":"乌冬面","tempura":"天妇罗","tofu":"豆腐",
    "shop":"商店","store":"店铺","supermarket":"超市",
    "price":"价格","discount":"折扣","cheap":"便宜的",
    "expensive":"贵的","cash":"现金",
    "station":"车站","airport":"机场","ticket":"票",
    "departure":"出发","arrival":"到达","north":"北",
    "south":"南","east":"东","west":"西","left":"左","right":"右",
    "hospital":"医院","medicine":"药","treatment":"治疗",
    "pain":"疼痛","fever":"发烧","headache":"头痛","injury":"受伤",
    "movie":"电影","game":"游戏","sport":"运动","hobby":"爱好",
    "travel":"旅行","vacation":"假期","holiday":"节假日",
    "party":"派对","concert":"音乐会","festival":"节日",
    "red":"红色","blue":"蓝色","green":"绿色","yellow":"黄色",
    "orange":"橙色","purple":"紫色","pink":"粉色",
    "white":"白色","black":"黑色","gray":"灰色","brown":"棕色",
    "meaning":"意思、含义","reason":"理由、原因","result":"结果",
    "effect":"效果、影响","purpose":"目的","method":"方法",
    "way":"方式","rule":"规则","fact":"事实","truth":"真相",
    "opinion":"意见","idea":"想法","dream":"梦、梦想",
    "goal":"目标","hope":"希望","wish":"愿望","luck":"运气",
    "chance":"机会","risk":"风险","problem":"问题","trouble":"麻烦",
    "mistake":"错误","success":"成功","failure":"失败",
    "experience":"经验","memory":"记忆","knowledge":"知识",
    "skill":"技能","ability":"能力","talent":"才能",
    "culture":"文化","tradition":"传统","custom":"习俗",
    "society":"社会","world":"世界","life":"生活、生命",
    "nature":"自然","environment":"环境","situation":"情况、状况",
    "information":"信息","news":"新闻","story":"故事",
    "history":"历史","relationship":"关系",
    "communication":"沟通、交流","agreement":"协议、同意",
    "character":"性格、字符","personality":"个性",
    "attitude":"态度","behavior":"行为","action":"行动",
    "reaction":"反应","response":"回应","request":"请求",
    "support":"支持","cooperation":"合作","competition":"竞争",
    "progress":"进步","development":"发展",
    "beginning":"开始","part":"部分","detail":"细节",
    "number":"数字","size":"大小","shape":"形状","color":"颜色",
    "sound":"声音","power":"力量、权力","speed":"速度",
    "position":"位置","place":"地方","space":"空间",
    "thank you":"谢谢","sorry":"对不起","please":"请",
    "hello":"你好","goodbye":"再见","yes":"是的","no":"不、不是",
    "japanese":"日语、日本的","japan":"日本",
    "cherry blossom":"樱花","hot spring":"温泉",
    "shrine":"神社","temple":"寺庙","kimono":"和服",
    "anime":"动漫","manga":"漫画","atmosphere":"氛围、气氛",
    "season":"季节","climate":"气候","weather":"天气",
    "temperature":"温度","freedom":"自由","peace":"和平",
    "happiness":"幸福","health":"健康","strength":"力量",
    "wisdom":"智慧","beauty":"美","study":"学习、勉强",
    "work":"工作","heart":"心、心脏","mind":"心理、意志",
    "spirit":"精神","soul":"灵魂","body (physical)":"肉体",
    "things":"事情、东西","matter":"事情、问题","event":"事件",
    "place":"场所、地方","area":"区域、地区","region":"地区",
    "period":"期间、时期","age":"年龄、时代","era":"时代",
    "method":"方法","system":"系统、制度","form":"形式",
    "type":"类型","kind (type)":"种类","sort":"种类",
    "degree":"程度","level":"水平、等级","stage":"阶段",
    "step":"步骤","process":"过程","order":"顺序、命令",
    "direction":"方向、指导","standard":"标准",
    "condition":"条件、状态","state":"状态",
    "case":"情况、案例","example":"例子","sample":"样品",
    "model":"模型、模范","original":"原版、独创",
    "special":"特别的","general":"一般的","common":"普通的",
    "main":"主要的","basic":"基本的","simple":"简单的",
    "complex":"复杂的","natural":"自然的","artificial":"人工的",
    "physical":"物理的、身体的","mental":"精神的",
    "social":"社会的","economic":"经济的","political":"政治的",
    "religious":"宗教的","scientific":"科学的",
    "technical":"技术的","practical":"实用的",
    "theoretical":"理论的","official":"官方的",
    "personal":"个人的","public":"公共的","private":"私人的",
    "national":"国家的","international":"国际的",
    "traditional":"传统的","modern":"现代的",
    "ancient":"古代的","historical":"历史的",
}

_POS_ZH = {
    "名詞":"名词","動詞":"动词","形容詞（い形）":"い形容词",
    "形容動詞（な形）":"な形容词","副詞":"副词","助詞":"助词",
    "助動詞":"助动词","接続詞":"接续词","感動詞":"感叹词",
    "接頭辞":"接头词","接尾辞":"接尾词","助数詞":"量词",
    "代名詞":"代词","五段動詞":"五段动词","一段動詞":"一段动词",
    "カ変動詞":"カ变动词","サ変動詞":"サ变动词","表現":"表达",
    "自動詞":"自动词","他動詞":"他动词","副詞的名詞":"副词性名词",
    "四字熟語":"四字熟语","慣用句":"习语","固有名詞":"专有名词",
    "noun":"名词","verb":"动词","adjective":"形容词",
    "adverb":"副词","particle":"助词","conjunction":"接续词",
    "interjection":"感叹词","prefix":"接头词","suffix":"接尾词",
    "counter":"量词","pronoun":"代词","expression":"表达",
    "auxiliary verb":"助动词","numeric":"数词",
    "Wikipedia definition":"（百科）",
}

def _translate(en_text):
    """
    英→中翻译。
    策略：精确全词匹配优先；否则保留英文原文。
    不做子串替换（避免把 "darling" 里的 "ear" 换掉之类的问题）。
    """
    tl = en_text.lower().strip()
    if tl in _EN_ZH:
        return _EN_ZH[tl]
    # 精确去掉括号补充后匹配（如 "to eat (food)" → "to eat"）
    import re
    stripped = re.sub(r'\s*\(.*?\)\s*$', '', tl).strip()
    if stripped in _EN_ZH:
        return _EN_ZH[stripped]
    # 尝试把首个短语匹配到中文，后半部分保留英文
    best_k, best_v = "", ""
    for k, v in _EN_ZH.items():
        # 只允许 整词 开头匹配（避免 "ear" 匹配到 "early"）
        if tl.startswith(k) and len(k) > len(best_k):
            # 确保 k 之后是空格、标点或字符串结束
            rest = tl[len(k):]
            if not rest or rest[0] in " ,;(":
                best_k, best_v = k, v
    if best_v:
        rest = en_text[len(best_k):].strip(" ,;")
        return best_v + (f"（{rest}）" if rest else "")
    return en_text

def _pos_zh(pos):
    return _POS_ZH.get(pos, pos)

# ──────────────────────────────────────────────
#  DB 连接（线程安全单例）
# ──────────────────────────────────────────────
_db_conn = None

def _get_conn():
    global _db_conn
    if _db_conn is None and DB_PATH:
        _db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _db_conn

def _row_to_entry(row):
    eid, kanji_str, reading_str, meanings_json, is_common = row
    kanji_list   = [k for k in kanji_str.split("｜") if k] if kanji_str else []
    reading_list = [r for r in reading_str.split("｜") if r] if reading_str else []
    senses_raw   = json.loads(meanings_json) if meanings_json else []

    senses = []
    for s in senses_raw:
        glosses_raw = s.get("glosses", [])
        is_zh = s.get("is_chinese", False)
        glosses_zh = glosses_raw if is_zh else [_translate(g) for g in glosses_raw]
        senses.append({
            "glosses":    glosses_zh,
            "glosses_en": glosses_raw,
            "is_chinese": is_zh,
            "pos":        [_pos_zh(p) for p in s.get("pos", [])],
            "misc":       s.get("misc", []),
            "examples":   s.get("examples", []),
        })

    return {
        "word":      kanji_list[0] if kanji_list else (reading_list[0] if reading_list else ""),
        "kanji":     kanji_list,
        "reading":   reading_list[0] if reading_list else "",
        "senses":    senses,
        "is_common": bool(is_common),
        "jlpt":      [],
        "source":    "offline",
    }

# ──────────────────────────────────────────────
#  离线查询
# ──────────────────────────────────────────────
def lookup_offline(keyword):
    conn = _get_conn()
    if conn is None:
        return []
    c = conn.cursor()
    results = []
    seen = set()

    def _fetch(form):
        c.execute(
            "SELECT e.id,e.kanji,e.reading,e.meanings,e.is_common "
            "FROM entries e JOIN kanji_idx k ON e.id=k.eid WHERE k.form=? LIMIT 5",
            (form,))
        rows = c.fetchall()
        if not rows:
            c.execute(
                "SELECT e.id,e.kanji,e.reading,e.meanings,e.is_common "
                "FROM entries e JOIN reading_idx r ON e.id=r.eid WHERE r.form=? LIMIT 5",
                (form,))
            rows = c.fetchall()
        return rows

    for row in _fetch(keyword):
        if row[0] not in seen:
            seen.add(row[0]); results.append(_row_to_entry(row))

    if not _is_japanese(keyword) and not results:
        hira = romaji_to_hiragana(keyword)
        if hira != keyword:
            for row in _fetch(hira):
                if row[0] not in seen:
                    seen.add(row[0]); results.append(_row_to_entry(row))

    return results[:5]

# ──────────────────────────────────────────────
#  在线查询（Jisho API）
# ──────────────────────────────────────────────
def _parse_jisho(data):
    results = []
    for item in (data.get("data") or [])[:5]:
        jp = item.get("japanese", [{}])
        word    = jp[0].get("word", "")
        reading = jp[0].get("reading", "")
        senses = []
        for s in item.get("senses", []):
            en_defs = s.get("english_definitions", [])
            senses.append({
                "glosses":    [_translate(g) for g in en_defs],
                "glosses_en": en_defs,
                "is_chinese": False,
                "pos":        [_pos_zh(p) for p in s.get("parts_of_speech", [])],
                "misc":       s.get("tags", []),
                "examples":   [],
            })
        results.append({
            "word":      word or reading,
            "kanji":     [word] if word else [],
            "reading":   reading,
            "senses":    senses,
            "is_common": item.get("is_common", False),
            "jlpt":      item.get("jlpt", []),
            "source":    "online",
        })
    return results

def lookup_online(keyword, callback):
    def _fetch():
        try:
            enc = urllib.parse.quote(keyword)
            url = f"https://jisho.org/api/v1/search/words?keyword={enc}"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode("utf-8")
            callback(_parse_jisho(json.loads(raw)), None)
        except Exception as e:
            callback([], str(e))
    threading.Thread(target=_fetch, daemon=True).start()

# ──────────────────────────────────────────────
#  统一查询入口
# ──────────────────────────────────────────────
def lookup(keyword, callback):
    """先离线，查不到再联网。callback(results, source, error)"""
    keyword = keyword.strip()
    if not keyword:
        callback([], "none", "关键词为空"); return
    offline = lookup_offline(keyword)
    if offline:
        callback(offline, "offline", None); return
    def _cb(results, err):
        callback(results, "online", err if not results else None)
    lookup_online(keyword, _cb)

# ──────────────────────────────────────────────
#  格式化工具
# ──────────────────────────────────────────────
def format_entry(entry, max_senses=4):
    word    = entry.get("word", "")
    reading = entry.get("reading", "")
    tags    = (["★常用"] if entry.get("is_common") else [])
    tags   += [t.upper() for t in entry.get("jlpt", [])]
    if entry.get("source") == "online": tags.append("🌐联网")
    header = word + (f"  【{reading}】" if reading and reading != word else "")
    if tags: header += "  " + " ".join(tags)
    lines = [header, "─" * 36]
    for i, s in enumerate(entry.get("senses", [])[:max_senses]):
        pos = "·".join(s.get("pos", []))
        gls = "；".join(s.get("glosses", []))
        misc = "·".join(s.get("misc", []))
        line = f"{i+1}."
        if pos: line += f" [{pos}]"
        line += f" {gls}"
        if misc: line += f"  ({misc})"
        lines.append(line)
        for ex in s.get("examples", [])[:1]:
            if ex.get("ja"): lines.append(f"   例：{ex['ja']}")
            if ex.get("zh"): lines.append(f"       {ex['zh']}")
    return "\n".join(lines)


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "食べる"
    print(f"DB: {DB_PATH}")
    res = lookup_offline(kw)
    print(f"离线结果: {len(res)} 条")
    for e in res:
        print(format_entry(e))
        print()
