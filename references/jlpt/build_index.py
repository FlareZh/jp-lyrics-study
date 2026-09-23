#!/usr/bin/env python3
"""Build references/jlpt/index.jsonl from the per-level markdown tables.

One JSON object per line. Look up a word or grammar point with the key field:

    grep '"k": "会う"' references/jlpt/index.jsonl
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVELS = ["n5", "n4", "n3", "n2", "n1"]
OUT = ROOT / "index.jsonl"


def table_rows(path: Path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| ") or line.startswith("| #") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        yield cells


def norm_tilde(text: str) -> str:
    return text.replace("～", "〜").replace("~", "〜")


def grammar_keys(pattern: str):
    keys = []
    for part in re.split(r"\s*/\s*", pattern):
        part = part.strip()
        if not part:
            continue
        keys.append(part)
        if "+" in part:
            tail = part.split("+")[-1].strip()
            if len(tail) >= 2:
                keys.append(tail)
    seen = []
    for key in keys:
        folded = norm_tilde(key)
        for item in (key, folded):
            if item and item not in seen:
                seen.append(item)
    return seen


def main():
    records = []
    seen = set()

    def add(record):
        ident = (record["t"], record["k"], record["lv"], record.get("w", ""), record.get("r", ""), record["m"])
        if ident in seen:
            return
        seen.add(ident)
        records.append(record)

    for level in LEVELS:
        vocab = ROOT / level / "vocabulary.md"
        for cells in table_rows(vocab):
            if len(cells) < 4:
                continue
            _n, word, reading, meaning = cells[:4]
            word = norm_tilde(word)
            reading = norm_tilde(reading)
            if word:
                add({"t": "v", "k": word, "lv": level, "r": reading, "m": meaning})
            key = reading or word
            if key and key != word:
                rec = {"t": "v", "k": key, "lv": level, "m": meaning}
                if word:
                    rec["w"] = word
                add(rec)
            elif not word and key:
                add({"t": "v", "k": key, "lv": level, "m": meaning})

        grammar = ROOT / level / "grammar.md"
        for cells in table_rows(grammar):
            if len(cells) < 3:
                continue
            _n, pattern, meaning = cells[:3]
            pattern = pattern.strip()
            if not pattern:
                continue
            keys = grammar_keys(pattern)
            for key in keys:
                rec = {"t": "g", "k": key, "lv": level, "m": meaning}
                if key != pattern and key != norm_tilde(pattern):
                    rec["src"] = pattern
                add(rec)

    records.sort(key=lambda r: (r["t"], r["lv"], r["k"]))
    vocab_entries = sum(1 for r in records if r["t"] == "v" and "w" not in r)
    grammar_entries = sum(1 for r in records if r["t"] == "g" and "src" not in r)
    lines = [
        json.dumps(
            {
                "t": "meta",
                "vocab": vocab_entries,
                "grammar": grammar_entries,
                "note": "t=v 词汇, t=g 语法; k 查找键; lv 为 n5–n1; r 读音; w 词形(按读音查到时); src 语法原条目",
            },
            ensure_ascii=False,
        )
    ]
    lines.extend(json.dumps(r, ensure_ascii=False) for r in records)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT} lines={len(lines)} vocab={vocab_entries} grammar_keys={sum(1 for r in records if r['t']=='g')}")


if __name__ == "__main__":
    main()
