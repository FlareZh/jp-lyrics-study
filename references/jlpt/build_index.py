#!/usr/bin/env python3
"""Build JLPT vocabulary/grammar JSONL indexes from per-level markdown tables.

    grep '"k": "会う"' references/jlpt/vocabulary.jsonl
    grep '"k": "だに"' references/jlpt/grammar.jsonl
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LEVELS = ["n5", "n4", "n3", "n2", "n1"]
OUT_VOCAB = ROOT / "vocabulary.jsonl"
OUT_GRAMMAR = ROOT / "grammar.jsonl"


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


def write_jsonl(path: Path, meta: dict, records: list):
    lines = [json.dumps(meta, ensure_ascii=False)]
    lines.extend(json.dumps(r, ensure_ascii=False) for r in records)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {path} lines={len(lines)}")


def main():
    vocab = []
    grammar = []
    seen_v = set()
    seen_g = set()

    def add_vocab(record):
        ident = (record["k"], record["lv"], record.get("w", ""), record.get("r", ""), record["m"])
        if ident in seen_v:
            return
        seen_v.add(ident)
        vocab.append(record)

    def add_grammar(record):
        ident = (record["k"], record["lv"], record.get("src", ""), record["m"])
        if ident in seen_g:
            return
        seen_g.add(ident)
        grammar.append(record)

    for level in LEVELS:
        for cells in table_rows(ROOT / level / "vocabulary.md"):
            if len(cells) < 4:
                continue
            _n, word, reading, meaning = cells[:4]
            word = norm_tilde(word)
            reading = norm_tilde(reading)
            if word:
                add_vocab({"k": word, "lv": level, "r": reading, "m": meaning})
            key = reading or word
            if key and key != word:
                rec = {"k": key, "lv": level, "m": meaning}
                if word:
                    rec["w"] = word
                add_vocab(rec)
            elif not word and key:
                add_vocab({"k": key, "lv": level, "m": meaning})

        for cells in table_rows(ROOT / level / "grammar.md"):
            if len(cells) < 3:
                continue
            _n, pattern, meaning = cells[:3]
            pattern = pattern.strip()
            if not pattern:
                continue
            for key in grammar_keys(pattern):
                rec = {"k": key, "lv": level, "m": meaning}
                if key != pattern and key != norm_tilde(pattern):
                    rec["src"] = pattern
                add_grammar(rec)

    vocab.sort(key=lambda r: (r["lv"], r["k"]))
    grammar.sort(key=lambda r: (r["lv"], r["k"]))

    vocab_entries = sum(1 for r in vocab if "w" not in r)
    grammar_entries = sum(1 for r in grammar if "src" not in r)

    write_jsonl(
        OUT_VOCAB,
        {
            "meta": True,
            "entries": vocab_entries,
            "note": "k 查找键; lv 为 n5–n1; r 读音; w 词形(按读音查到时); m 英文释义",
        },
        vocab,
    )
    write_jsonl(
        OUT_GRAMMAR,
        {
            "meta": True,
            "entries": grammar_entries,
            "note": "k 查找键(句型或核心); lv 为 n5–n1; src 完整原条目(核心行时); m 英文释义",
        },
        grammar,
    )
    print(f"vocab_entries={vocab_entries} grammar_entries={grammar_entries} "
          f"vocab_keys={len(vocab)} grammar_keys={len(grammar)}")


if __name__ == "__main__":
    main()
