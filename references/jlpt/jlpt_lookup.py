#!/usr/bin/env python3
"""查 JLPT 等级：把词形丢进来，告诉你能不能定级。

用法：
  python3 references/jlpt/jlpt_lookup.py vocab 私 蠢く 浮かぶ あげる
  python3 references/jlpt/jlpt_lookup.py vocab -f words.txt
  python3 references/jlpt/jlpt_lookup.py grammar 〜ては だに
  python3 references/jlpt/jlpt_lookup.py vocab --tsv 私 浮かぶ

结果 status：
  ok         唯一靠谱命中 → 用 lv 填 ws 第 3 列
  ambiguous  多个等级/释义，别瞎填（可人工对照后选，或填空）
  reject     命中但释义像乱码/明显不对 → 当没查到，填空
  miss       索引里没有 → 填空
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VOCAB_PATH = ROOT / "vocabulary.jsonl"
GRAMMAR_PATH = ROOT / "grammar.jsonl"

# 已知 OCR / 垃圾释义（不要把 hand/why/eye 这类正常短英文释义当垃圾）
NOISE_RE = re.compile(
    r"tWO|breaktast|JIS\s*X\s*0212|kuten|\bnull\b|\bundefined\b",
    re.I,
)


def load_index(path: Path) -> dict[str, list[dict]]:
    by: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("meta"):
            continue
        k = row.get("k")
        if k:
            by[k].append(row)
    return by


def is_noisy_meaning(m: str) -> bool:
    text = (m or "").strip()
    if not text:
        return True
    return bool(NOISE_RE.search(text))


def clean_hits(hits: list[dict]) -> tuple[list[dict], list[dict]]:
    """返回 (干净命中, 因释义被扔掉的命中)。"""
    good, bad = [], []
    for r in hits:
        if is_noisy_meaning(r.get("m", "")):
            bad.append(r)
        else:
            good.append(r)
    return good, bad


def summarize_candidates(rows: list[dict], limit: int = 8) -> list[dict]:
    out = []
    for r in rows[:limit]:
        item = {"lv": r.get("lv", ""), "m": r.get("m", "")}
        if r.get("r"):
            item["r"] = r["r"]
        if r.get("w"):
            item["w"] = r["w"]
        if r.get("src"):
            item["src"] = r["src"]
        out.append(item)
    return out


def lookup_vocab_one(q: str, index: dict[str, list[dict]]) -> dict:
    q = (q or "").strip()
    if not q:
        return {"q": q, "status": "miss"}

    raw = index.get(q, [])
    if not raw:
        return {"q": q, "status": "miss"}

    good, noisy = clean_hits(raw)
    word_hits = [r for r in good if "w" not in r]
    reading_hits = [r for r in good if "w" in r]
    # 原始结果里是否出现过「词形行」（无 w）。有的话不要掉进同音的别的字。
    had_word_rows = any("w" not in r for r in raw)

    # 优先：干净的词形行
    if word_hits:
        pool = word_hits
    elif had_word_rows:
        # 词形行全是垃圾释义（如 に → tWO），不当成「荷」的读音行
        return {
            "q": q,
            "status": "reject",
            "reason": "meaning_noise",
            "candidates": summarize_candidates(noisy or raw),
        }
    elif reading_hits:
        # 查询键是读音（如 むこう）→ 列出对应汉字词
        pool = reading_hits
    elif noisy:
        return {
            "q": q,
            "status": "reject",
            "reason": "meaning_noise",
            "candidates": summarize_candidates(noisy),
        }
    else:
        return {"q": q, "status": "miss"}

    levels = sorted({r.get("lv", "") for r in pool if r.get("lv")})
    # 词形行里若同一等级多条（不同释义），仍算 ambiguous，避免「あげる」一类混用
    if len(levels) == 1 and len(pool) == 1:
        r = pool[0]
        out = {
            "q": q,
            "status": "ok",
            "lv": r["lv"],
            "k": r.get("k", q),
            "m": r.get("m", ""),
        }
        if r.get("r"):
            out["r"] = r["r"]
        if r.get("w"):
            out["w"] = r["w"]
        return out

    if len(levels) == 1 and len(pool) > 1:
        # 同级多释义：仍给 lv，但标 ambiguous，让填写者对照中文释义
        return {
            "q": q,
            "status": "ambiguous",
            "lv_guess": levels[0],
            "reason": "same_level_multiple_meanings",
            "candidates": summarize_candidates(pool),
        }

    return {
        "q": q,
        "status": "ambiguous",
        "reason": "multiple_levels",
        "candidates": summarize_candidates(pool),
    }


def load_grammar_index(path: Path) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """返回 (精确键索引, 去罗马音括号后的规范化键索引)。"""
    by_exact: dict[str, list[dict]] = defaultdict(list)
    by_norm: dict[str, list[dict]] = defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("meta"):
            continue
        k = row.get("k")
        if not k:
            continue
        by_exact[k].append(row)
        nk = norm_grammar_key(k)
        if nk:
            by_norm[nk].append(row)
        # 同时挂上 ～ 变体，方便查询
        alt = k.replace("〜", "～")
        if alt != k:
            by_exact[alt].append(row)
    return by_exact, by_norm


def norm_grammar_key(q: str) -> str:
    s = (q or "").strip().replace("～", "〜").replace("~", "〜")
    # 去掉末尾罗马音/注释括号：〜ほど (hodo)
    s = re.sub(r"\s*[\(（][^）\)]*[\)）]\s*$", "", s).strip()
    return s


# 有限核心回退：查询串里若含这些尾巴，再试标准键
GRAMMAR_CORE_FALLBACKS = (
    ("たい", ("〜たい", "たい")),
    ("だけ", ("だけ", "〜だけ")),
    ("ほど", ("〜ほど", "ほど", "～ほど")),
    ("より", ("〜より〜のほうが", "より")),
    ("てもいい", ("〜てもいい", "てもいい")),
    ("でもいい", ("〜でもいい", "でもいい")),
    ("てはいけない", ("〜てはいけない", "てはいけない")),
    ("がほしい", ("〜がほしい", "がほしい", "欲しい")),
    ("が欲しい", ("〜がほしい", "が欲しい", "欲しい")),
    ("みたい", ("みたいだ", "〜みたいだ")),
    ("だに", ("だに", "N + だに")),
)


def gather_grammar_raw(
    q: str,
    by_exact: dict[str, list[dict]],
    by_norm: dict[str, list[dict]],
) -> list[dict]:
    """按规范化与有限回退收集候选（去重保序）。"""
    seen: set[int] = set()
    out: list[dict] = []

    def add_rows(rows: list[dict]):
        for r in rows:
            ident = id(r)
            if ident in seen:
                continue
            seen.add(ident)
            out.append(r)

    nq = norm_grammar_key(q)
    if not nq:
        return out

    # 精确 / 规范化键
    add_rows(by_exact.get(q, []))
    add_rows(by_exact.get(nq, []))
    add_rows(by_norm.get(nq, []))
    # 带/不带 〜 前缀
    if not nq.startswith("〜"):
        add_rows(by_exact.get("〜" + nq, []))
        add_rows(by_norm.get("〜" + nq, []))
    else:
        bare = nq[1:]
        add_rows(by_exact.get(bare, []))
        add_rows(by_norm.get(bare, []))

    if out:
        return out

    # 核心尾巴回退（仅在尚无命中时）
    low = nq
    for needle, keys in GRAMMAR_CORE_FALLBACKS:
        if needle not in low:
            continue
        for k in keys:
            add_rows(by_exact.get(k, []))
            add_rows(by_norm.get(norm_grammar_key(k), []))
        if out:
            break
    return out


def decide_grammar_pool(q: str, pool: list[dict]) -> dict:
    if not pool:
        return {"q": q, "status": "miss"}
    good, noisy = clean_hits(pool)
    if not good and noisy:
        return {
            "q": q,
            "status": "reject",
            "reason": "meaning_noise",
            "candidates": summarize_candidates(noisy),
        }
    levels = sorted({r.get("lv", "") for r in good if r.get("lv")})
    if len(levels) == 1 and len(good) == 1:
        r = good[0]
        out = {
            "q": q,
            "status": "ok",
            "lv": r["lv"],
            "k": r.get("k", q),
            "m": r.get("m", ""),
        }
        if r.get("src"):
            out["src"] = r["src"]
        return out
    if len(levels) == 1:
        meanings = {(r.get("m") or "").strip() for r in good}
        # 同级且释义相同（如 〜ほど / ～ほど (hodo) 重复行）→ 视为唯一命中
        if len(meanings) == 1:
            r = good[0]
            out = {
                "q": q,
                "status": "ok",
                "lv": levels[0],
                "k": r.get("k", q),
                "m": r.get("m", ""),
            }
            if r.get("src"):
                out["src"] = r["src"]
            return out
        return {
            "q": q,
            "status": "ambiguous",
            "lv_guess": levels[0],
            "reason": "same_level_multiple_entries",
            "candidates": summarize_candidates(good),
        }
    return {
        "q": q,
        "status": "ambiguous",
        "reason": "multiple_levels",
        "candidates": summarize_candidates(good),
    }


def lookup_grammar_one(
    q: str,
    by_exact: dict[str, list[dict]],
    by_norm: dict[str, list[dict]] | None = None,
) -> dict:
    """查语法。by_norm 可省略（则只按 exact 字典，兼容旧调用）。"""
    raw_q = (q or "").strip()
    if not raw_q:
        return {"q": raw_q, "status": "miss"}
    if by_norm is None:
        # 旧接口：只有一个 exact 索引
        by_norm = defaultdict(list)
        for k, rows in by_exact.items():
            by_norm[norm_grammar_key(k)].extend(rows)
    pool = gather_grammar_raw(raw_q, by_exact, by_norm)
    return decide_grammar_pool(raw_q, pool)


def read_queries(args: argparse.Namespace) -> list[str]:
    qs: list[str] = []
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            qs.append(line.split("\t")[0].strip())
    qs.extend(args.words or [])
    # 去重且保持顺序
    seen = set()
    out = []
    for q in qs:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def format_tsv(row: dict) -> str:
    st = row.get("status", "")
    lv = row.get("lv") or row.get("lv_guess") or ""
    reason = row.get("reason") or ""
    m = row.get("m") or ""
    if not m and row.get("candidates"):
        m = " | ".join(
            f"{c.get('lv','')}:{c.get('w') or ''}{c.get('m','')[:40]}"
            for c in row["candidates"][:3]
        )
    return f"{row.get('q','')}\t{st}\t{lv}\t{reason}\t{m}"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="JLPT 等级查询（词汇 / 语法）")
    p.add_argument("kind", choices=("vocab", "grammar"), help="查词汇还是语法")
    p.add_argument("words", nargs="*", help="待查词形或句型核心")
    p.add_argument("-f", "--file", help="每行一个词的文本文件")
    p.add_argument("--tsv", action="store_true", help="用制表符表格输出（方便人看）")
    args = p.parse_args(argv)

    queries = read_queries(args)
    if not queries:
        print("请提供要查的词，例如：jlpt_lookup.py vocab 私 浮かぶ", file=sys.stderr)
        return 2

    if args.kind == "vocab":
        index = load_index(VOCAB_PATH)
        results = [lookup_vocab_one(q, index) for q in queries]
    else:
        by_exact, by_norm = load_grammar_index(GRAMMAR_PATH)
        results = [lookup_grammar_one(q, by_exact, by_norm) for q in queries]

    if args.tsv:
        print("词\t状态\t等级\t原因\t说明")
        for row in results:
            print(format_tsv(row))
    else:
        for row in results:
            print(json.dumps(row, ensure_ascii=False))

    # 有 miss/reject/ambiguous 不视为程序失败；方便管道使用
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
