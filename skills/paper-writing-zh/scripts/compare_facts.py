# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""核对改稿有没有丢信息或引入常见硬伤：
1. 列出改稿后消失或新增的数字（连同正负号和不等号）、引用编号、英文缩写，以及出现次数变了的数字和引用；
2. 提示分号与冒号的增减；
3. 检查新稿中的“降低/减少了 N 倍”病句，以及中英文摘要（若同时存在）之间的阿拉伯数字差异。

    uv run compare_facts.py 旧稿.md 新稿.md

有消失、新增或倍数病句时退出码为 1。次数变化、标点增减和中英摘要数字差异只作提示（中文写“3 类”而英文写“three”属正常差异，人工核对即可）。
原因句、限定条件和数字有没有安到别的对象上查不出，仍要逐句对照原文。
"""
import re
import sys
from collections import Counter
from pathlib import Path

# 数字前的连字符只在不紧跟数字、字母时算负号，免得把“3-5”这类范围读成 -5
FACT = re.compile(
    r"\[[\d,，\-–~～ ]+\]"
    r"|(?:[+−±≤≥<>]|(?<![\dA-Za-z\]])-)?\d+(?:\.\d+)?%?"
    r"|[A-Za-z][A-Za-z0-9\-]*"
)
BAD_FOLD = re.compile(r"(?:降低|减少|下降|缩小|缩短|削弱)了?\s*(?:\d+(?:\.\d+)?|[一二两三四五六七八九十百]+)\s*倍")
NUM_ONLY = re.compile(r"(?:[+−±]|(?<![\dA-Za-z\]])-)?\d+(?:\.\d+)?%?")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def facts(text: str) -> Counter:
    return Counter(FACT.findall(text))


def extract_section(text: str, heading_pattern: str) -> str | None:
    m = re.search(heading_pattern, text, flags=re.MULTILINE)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^#{1,3}\s+|^\*\*(?:关键词|Keywords)", rest, flags=re.MULTILINE)
    return rest[:nxt.start()] if nxt else rest


def bilingual_abstract_diff(text: str) -> tuple[list[str], list[str]] | None:
    zh = extract_section(text, r"^#{1,3}\s*摘\s*要\s*$|^摘\s*要[:：]")
    en = extract_section(text, r"^#{1,3}\s*Abstract\s*$|^Abstract[:：]")
    if not zh or not en:
        return None
    zh_nums, en_nums = set(NUM_ONLY.findall(zh)), set(NUM_ONLY.findall(en))
    return sorted(zh_nums - en_nums), sorted(en_nums - zh_nums)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    old_text, new_text = read(Path(sys.argv[1])), read(Path(sys.argv[2]))
    old, new = facts(old_text), facts(new_text)
    lost, added = sorted(set(old) - set(new)), sorted(set(new) - set(old))
    # 英文缩写改稿时常被代词替换，次数变化没有参考价值，只看数字和引用
    recount = [f"{k}（{old[k]}→{new[k]}）" for k in sorted(set(old) & set(new))
               if old[k] != new[k] and not k[0].isalpha()]
    bad_folds = BAD_FOLD.findall(new_text)

    print("改稿后消失：", "、".join(lost) or "无")
    print("改稿后新增：", "、".join(added) or "无")
    print("次数变了：", "、".join(recount) or "无")
    print("标点：", "，".join(f"{name} {old_text.count(ch)}→{new_text.count(ch)}" for name, ch in (("分号", "；"), ("冒号", "："))))
    if bad_folds:
        print("倍数病句：", "、".join(bad_folds))
    bi = bilingual_abstract_diff(new_text)
    if bi and (bi[0] or bi[1]):
        parts = []
        if bi[0]:
            parts.append("仅中文摘要有 " + "、".join(bi[0]))
        if bi[1]:
            parts.append("仅英文Abstract有 " + "、".join(bi[1]))
        print("双语摘要数字提示：", "；".join(parts))
    sys.exit(1 if (lost or added or bad_folds) else 0)


if __name__ == "__main__":
    main()
