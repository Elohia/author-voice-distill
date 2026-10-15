#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""voice_stats.py — 作者语料风格实测器

契约输出：JSON（人读摘要走 stdout，机器口径写 --json 路径）。
用途：给 author-voice-distill 提供「机器口径」的风格骨架——句长、标点、节奏。
单向职责：只统计，不改写，不评价。

用法：
    python voice_stats.py <语料文件或目录> [--json out.json]
    python voice_stats.py 作者A/ --compare 作者B/ [--json diff.json]

退出码：0 成功 / 1 语料为空 / 2 参数错误
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

TEXT_EXT = {".md", ".txt", ".markdown"}
SENT_SPLIT = re.compile(r"[。！？…]+")
CJK = re.compile(r"[\u4e00-\u9fff]")
ALL_PUNCT = "，。！？、；：“”‘’（）《》〈〉—…·「」『』,.;:!?\"'()<>-"

# 只用于剔除 2-gram 噪声，不是"AI 味词表"
STOP_CHARS = set("的了吗呢吧啊呀哦嗯是在有和就不都也我你他她它们这那一个上下来去说要做着过被把给对很会能")


def read_corpus(root: Path) -> tuple[list[str], str]:
    if root.is_dir():
        files = sorted(f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in TEXT_EXT)
    elif root.is_file():
        files = [root]
    else:
        return [], ""
    chunks, names = [], []
    for f in files:
        try:
            chunks.append(f.read_text(encoding="utf-8", errors="ignore"))
            names.append(str(f))
        except OSError:
            continue
    return names, "\n".join(chunks)


def strip_markup(t: str) -> str:
    t = re.sub(r"```.*?```", "", t, flags=re.S)
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", t)
    t = t.replace("|", " ").replace("*", "").replace("`", "").replace(">", "")
    return t


# 纯对白行：整行被引号包住，或「角色：台词」形式（前缀不含方括号，避免误伤 [画面文字]）
_DIALOG_QUOTED = re.compile(r'^\s*["“][^"”]*["”]\s*$')
_DIALOG_SPEAKER = re.compile(r'^\s*[A-Za-z\u4e00-\u9fff][A-Za-z\u4e00-\u9fff·]{0,11}\s*[：:]\s*\S')


def drop_dialogue(text: str) -> str:
    """剔除对白行，只留旁白/动作叙述。

    剧本体裁必需：对白行天然是短句，与叙事散文的句长基线不可直接比较；
    不剔除会把「体裁差异」误判成「风格差异」。
    """
    kept = []
    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue
        if _DIALOG_QUOTED.match(s) or _DIALOG_SPEAKER.match(s):
            continue
        kept.append(line)
    return "\n".join(kept)


def body_chars(s: str) -> int:
    return len(CJK.findall(s)) + len(re.findall(r"[A-Za-z0-9]", s))


def analyze(text: str, exclude_dialogue: bool = False) -> dict:
    body = strip_markup(text)
    if exclude_dialogue:
        body = drop_dialogue(body)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    raw_sents = [s.strip() for s in SENT_SPLIT.split(body) if s.strip()]

    sent_lens = [body_chars(s) for s in raw_sents]
    sent_lens = [n for n in sent_lens if n > 0]
    zh = len(CJK.findall(body))

    def per1k(n: int) -> float:
        return round(n * 1000.0 / zh, 2) if zh else 0.0

    punct = {p: per1k(body.count(p)) for p in ALL_PUNCT if body.count(p) > 0}

    para_lens = [body_chars(p) for p in paragraphs if body_chars(p) > 0]

    stats = {}
    if sent_lens:
        mean = statistics.fmean(sent_lens)
        sd = statistics.pstdev(sent_lens) if len(sent_lens) > 1 else 0.0
        q = statistics.quantiles(sent_lens, n=10) if len(sent_lens) >= 10 else None
        stats = {
            "count": len(sent_lens),
            "mean": round(mean, 2),
            "sd": round(sd, 2),
            "cv": round(sd / mean, 3) if mean else 0.0,
            "min": min(sent_lens),
            "max": max(sent_lens),
            "p10": round(q[0], 1) if q else None,
            "p50": round(statistics.median(sent_lens), 1),
            "p90": round(q[8], 1) if q else None,
            "short_ratio_le8": round(sum(1 for n in sent_lens if n <= 8) / len(sent_lens), 3),
            "long_ratio_ge30": round(sum(1 for n in sent_lens if n >= 30) / len(sent_lens), 3),
        }

    # 2-gram 近似词频（无分词依赖）
    grams: dict[str, int] = {}
    for m in re.finditer(r"[\u4e00-\u9fff]{2,}", body):
        s = m.group()
        for i in range(len(s) - 1):
            g = s[i:i + 2]
            if g[0] in STOP_CHARS or g[1] in STOP_CHARS:
                continue
            grams[g] = grams.get(g, 0) + 1
    top = sorted(grams.items(), key=lambda kv: (-kv[1], kv[0]))[:20]

    return {
        "zh_chars": zh,
        "body_chars": body_chars(body),
        "paragraphs": {
            "count": len(para_lens),
            "mean": round(statistics.fmean(para_lens), 1) if para_lens else 0,
            "median": round(statistics.median(para_lens), 1) if para_lens else 0,
        },
        "sentences": stats,
        "punct_per_1k": punct,
        "top_bigrams": [{"gram": g, "n": n} for g, n in top],
    }


def diff(a: dict, b: dict) -> dict:
    keys = [
        ("sentences.mean", "平均句长"),
        ("sentences.sd", "句长标准差"),
        ("sentences.cv", "句长变异系数"),
        ("sentences.short_ratio_le8", "短句(≤8字)占比"),
        ("sentences.long_ratio_ge30", "长句(≥30字)占比"),
        ("paragraphs.mean", "平均段长"),
    ]
    rows = []
    for path, label in keys:
        va = a
        vb = b
        for part in path.split("."):
            va = (va or {}).get(part) if isinstance(va, dict) else None
            vb = (vb or {}).get(part) if isinstance(vb, dict) else None
        rows.append({"metric": label, "a": va, "b": vb,
                     "delta": round(vb - va, 3) if isinstance(va, (int, float)) and isinstance(vb, (int, float)) else None})
    pa, pb = a.get("punct_per_1k", {}), b.get("punct_per_1k", {})
    punct_rows = []
    for p in sorted(set(pa) | set(pb)):
        punct_rows.append({"punct": p, "a": pa.get(p, 0.0), "b": pb.get(p, 0.0),
                           "delta": round(pb.get(p, 0.0) - pa.get(p, 0.0), 2)})
    return {"metrics": rows, "punct": punct_rows}


def main() -> int:
    ap = argparse.ArgumentParser(description="作者语料风格实测器（只统计，不改写）")
    ap.add_argument("corpus", help="语料文件或目录")
    ap.add_argument("--compare", metavar="PATH", help="对照语料（相同格式）")
    ap.add_argument("--json", metavar="PATH", help="契约 JSON 输出路径")
    ap.add_argument("--quiet", action="store_true", help="只写 JSON，不打印摘要")
    ap.add_argument("--exclude-dialogue", action="store_true",
                    help="剔除对白行只统计旁白（剧本/小说体必用；对白短句会污染句长基线）")
    args = ap.parse_args()

    names, text = read_corpus(Path(args.corpus))
    if not text.strip():
        print(f"[ERR] 语料为空：{args.corpus}", file=sys.stderr)
        return 1

    xd = args.exclude_dialogue
    result: dict = {"corpus": names, "exclude_dialogue": xd, "stats": analyze(text, xd)}

    if args.compare:
        n2, t2 = read_corpus(Path(args.compare))
        if not t2.strip():
            print(f"[ERR] 对照语料为空：{args.compare}", file=sys.stderr)
            return 1
        result["compare"] = {"corpus": n2, "stats": analyze(t2, xd)}
        result["diff"] = diff(result["stats"], result["compare"]["stats"])

    if args.json:
        Path(args.json).write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    if not args.quiet:
        s = result["stats"]
        print(f"语料文件 {len(names)} 个 ｜ 中文字数 {s['zh_chars']}")
        if s.get("sentences"):
            x = s["sentences"]
            print(f"句数 {x['count']} ｜ 平均句长 {x['mean']} ｜ 标准差 {x['sd']} ｜ 变异系数 {x['cv']}")
            print(f"短句(≤8字) {x['short_ratio_le8']:.1%} ｜ 长句(≥30字) {x['long_ratio_ge30']:.1%}")
        print(f"段落 {s['paragraphs']['count']} 段 ｜ 平均 {s['paragraphs']['mean']} 字 ｜ 中位 {s['paragraphs']['median']} 字")
        top_p = sorted(s["punct_per_1k"].items(), key=lambda kv: -kv[1])[:6]
        print("标点/千字：" + "  ".join(f"{k}{v}" for k, v in top_p))
        print("高频二字组：" + "  ".join(f"{d['gram']}({d['n']})" for d in s["top_bigrams"][:10]))
        if "diff" in result:
            print("\n—— 与对照语料差异 ——")
            for r in result["diff"]["metrics"]:
                print(f"  {r['metric']:<14} {r['a']}  ->  {r['b']}   (Δ{r['delta']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
