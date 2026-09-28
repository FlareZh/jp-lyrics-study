#!/usr/bin/env python3
"""生成后的歌词学习页交卷检查。

用法：
  python3 references/jlpt/validate_lyric_page.py demo/あぶく.html
  python3 references/jlpt/validate_lyric_page.py song.html --strict

exit 0 = 无 error（warning 仍会打印）
exit 1 = 有 error
exit 2 = 文件读不出 / 解析失败
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # jp-lyrics-study/
LOOKUP = Path(__file__).resolve().parent / "jlpt_lookup.py"

VERB_FORMS = {
    "字典形", "ない形", "ます形", "て形", "た形", "ば形",
    "意志形", "命令形", "可能态", "被动态", "使役态", "使役被动态",
}
ADJ_FORMS = {"字典形", "否定形", "过去形", "て形", "副词化", "假定形"}
VERB_POS = {"动词", "动词短语", "动词（敬语）", "动词（使役态）"}
ADJ_POS = {"イ形容词", "ナ形容词"}
NEED_FORMS_POS = VERB_POS | ADJ_POS | {"助动词", "句型", "句型（许可）"}
VALID_LV = {"", "n5", "n4", "n3", "n2", "n1"}
# 助词黑名单：不得出现在 ws / POS
PARTICLES = {
    "に", "は", "を", "も", "へ", "で", "が", "と", "より", "から", "まで",
    "だけ", "しか", "ばかり", "ほど", "か", "や", "の", "ね", "よ", "さ", "ぞ", "わ", "かな",
}

PLACEHOLDER_RES = [
    (re.compile(r"\[歌名\]"), "仍有占位符 [歌名]"),
    (re.compile(r"\[歌手名\]"), "仍有占位符 [歌手名]"),
    (re.compile(r"\[歌名中文译名\]"), "仍有占位符 [歌名中文译名]"),
    (re.compile(r"\[作词人\]"), "仍有占位符 [作词人]"),
    (re.compile(r"\[一句歌词主题/简介\]"), "仍有占位符 [一句歌词主题/简介]"),
    (re.compile(r"TODO:\s*填充"), "仍有 TODO 填充占位"),
]
LATIN_WORD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9'’\-]*$")
HIRAGANA_ONLY_RE = re.compile(r"^[\u3040-\u309fー]+$")
KATAKANA_RE = re.compile(r"[\u30a0-\u30ff]")
HAS_KANJI_RE = re.compile(r"[\u4e00-\u9fff]")
# 不在 ruby 里的汉字（粗略：去掉 ruby 块后再找汉字）
RUBY_BLOCK_RE = re.compile(r"<ruby[\s\S]*?</ruby>", re.I)


def extract_with_node(html_path: Path) -> dict:
    script = r"""
const fs = require('fs');
const html = fs.readFileSync(process.argv[1], 'utf8');
function sliceAssign(src, name) {
  const re = new RegExp('const\\s+' + name + '\\s*=');
  const m = re.exec(src);
  if (!m) return null;
  let i = m.index + m[0].length;
  while (i < src.length && /\s/.test(src[i])) i++;
  // skip block comment right after =
  if (src.startsWith('/*', i)) {
    const endc = src.indexOf('*/', i);
    if (endc < 0) throw new Error(name + ': bad comment');
    i = endc + 2;
    while (i < src.length && /\s/.test(src[i])) i++;
  }
  const ch = src[i];
  if (ch === "'" || ch === '"' || ch === '`') {
    const quote = ch;
    i++;
    let s = '';
    while (i < src.length) {
      const c = src[i];
      if (c === '\\') { s += src[i+1]; i += 2; continue; }
      if (c === quote) { i++; break; }
      s += c; i++;
    }
    return s;
  }
  if (ch !== '[' && ch !== '{') throw new Error(name + ': expected [ or { at ' + i);
  const openCh = ch, closeCh = ch === '[' ? ']' : '}';
  let depth = 0, inStr = null, esc = false;
  const from = i;
  for (; i < src.length; i++) {
    const c = src[i];
    if (inStr) {
      if (esc) { esc = false; continue; }
      if (c === '\\') { esc = true; continue; }
      if (c === inStr) inStr = null;
      continue;
    }
    if (c === "'" || c === '"' || c === '`') { inStr = c; continue; }
    if (c === '/' && src[i+1] === '/') {
      while (i < src.length && src[i] !== '\n') i++;
      continue;
    }
    if (c === '/' && src[i+1] === '*') {
      i += 2;
      while (i < src.length && !(src[i] === '*' && src[i+1] === '/')) i++;
      i++;
      continue;
    }
    if (c === openCh) depth++;
    else if (c === closeCh) {
      depth--;
      if (depth === 0) {
        const body = src.slice(from, i + 1);
        return (new Function('return (' + body + ')'))();
      }
    }
  }
  throw new Error(name + ': unclosed');
}
try {
  const songId = sliceAssign(html, 'SONG_ID');
  const S = sliceAssign(html, 'S');
  const POS = sliceAssign(html, 'POS');
  if (songId == null) throw new Error('missing SONG_ID');
  if (!Array.isArray(S)) throw new Error('S is not an array (got ' + typeof S + ')');
  if (!POS || typeof POS !== 'object' || Array.isArray(POS)) throw new Error('POS is not an object');
  process.stdout.write(JSON.stringify({ songId, S, POS }));
} catch (e) {
  process.stderr.write(String(e && e.stack || e));
  process.exit(2);
}
"""
    proc = subprocess.run(
        ["node", "-e", script, str(html_path)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "node extract failed")
    return json.loads(proc.stdout)


def batch_lookup(words: list[str], kind: str = "vocab") -> dict[str, dict]:
    if not words:
        return {}
    out: dict[str, dict] = {}
    batch = 40
    for i in range(0, len(words), batch):
        chunk = words[i:i + batch]
        proc = subprocess.run(
            [sys.executable, str(LOOKUP), kind, *chunk],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or f"jlpt_lookup {kind} failed")
        for line in proc.stdout.splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            out[row["q"]] = row
    return out


def batch_lookup_vocab(words: list[str]) -> dict[str, dict]:
    return batch_lookup(words, "vocab")


def batch_lookup_grammar(pats: list[str]) -> dict[str, dict]:
    return batch_lookup(pats, "grammar")


def check_placeholders(html: str, issues: list) -> None:
    for cre, msg in PLACEHOLDER_RES:
        if cre.search(html):
            issues.append(("error", msg))
    if "SONG_ID='[歌名]|[歌手名]'" in html or 'SONG_ID="[歌名]|[歌手名]"' in html:
        issues.append(("error", "SONG_ID 仍是模板默认占位"))


def check_data(song_id: str, S: list, POS: dict, issues: list, skip_jlpt: bool) -> None:
    if not song_id or song_id.strip() in {"[歌名]|[歌手名]", "|"}:
        issues.append(("error", f"SONG_ID 无效: {song_id!r}"))
    elif "|" not in song_id:
        issues.append(("warning", f"SONG_ID 建议写成 歌名|歌手名，当前: {song_id!r}"))

    ws_words: set[str] = set()
    for si, sent in enumerate(S):
        if not isinstance(sent, dict):
            issues.append(("error", f"S[{si}] 不是对象"))
            continue
        jp = sent.get("jp") or ""
        stripped = RUBY_BLOCK_RE.sub("", jp)
        if HAS_KANJI_RE.search(stripped):
            issues.append(("warning", f"第{si+1}句：有汉字可能未包在 <ruby> 里"))

        ws = sent.get("ws") or []
        if not isinstance(ws, list):
            issues.append(("error", f"S[{si}].ws 不是数组"))
            continue
        for wi, row in enumerate(ws):
            if not isinstance(row, (list, tuple)) or len(row) < 5:
                issues.append(("error", f"S[{si}].ws[{wi}] 应为 5 元数组"))
                continue
            ja, read, _mean, lv, _note = row[0], row[1], row[2], row[3], row[4]
            ja = ja if isinstance(ja, str) else str(ja)
            ws_words.add(ja)
            if LATIN_WORD_RE.match(ja):
                issues.append(("error", f"生词不应收录英文: {ja!r}（第{si+1}句）"))
            if ja in PARTICLES:
                issues.append(("error", f"助词 {ja!r} 不应进 ws（第{si+1}句）；请改写入 grams"))
            if lv not in VALID_LV:
                issues.append(("error", f"{ja}: 等级 {lv!r} 非法（只要 n5–n1 或空）"))
            if isinstance(read, str) and read:
                if HIRAGANA_ONLY_RE.match(ja):
                    issues.append(("warning", f"{ja}: 纯平假名一般不填读音"))
                if KATAKANA_RE.search(ja) and not HIRAGANA_ONLY_RE.match(read):
                    issues.append(("warning", f"{ja}: 片假名读音应写成平假名，当前 {read!r}"))

        grams = sent.get("grams")
        if grams is None and sent.get("gram"):
            issues.append(("warning", f"第{si+1}句仍用旧字段 gram，请改为 grams 数组"))
        elif grams is None:
            issues.append(("warning", f"第{si+1}句缺少 grams（可用 []）"))
        elif not isinstance(grams, list):
            issues.append(("error", f"S[{si}].grams 应为数组"))
        else:
            for gi, g in enumerate(grams):
                if not isinstance(g, dict):
                    issues.append(("error", f"S[{si}].grams[{gi}] 应为对象"))
                    continue
                pat = g.get("pat")
                lv = g.get("lv", "")
                note = g.get("note", "")
                if not isinstance(pat, str) or not pat.strip():
                    issues.append(("error", f"S[{si}].grams[{gi}] 缺少 pat"))
                if lv not in VALID_LV:
                    issues.append(("error", f"语法 {pat!r}: 等级 {lv!r} 非法"))
                if note is not None and not isinstance(note, str):
                    issues.append(("error", f"语法 {pat!r}: note 应为字符串"))

    pos_keys = set(POS.keys())
    missing_pos = sorted(ws_words - pos_keys)
    for ja in missing_pos:
        issues.append(("error", f"生词 {ja!r} 在 ws 里出现，但 POS 表没有"))

    orphan = sorted(pos_keys - ws_words)
    for ja in orphan[:20]:
        issues.append(("warning", f"POS 有 {ja!r}，但所有 ws 都没用到"))
    if len(orphan) > 20:
        issues.append(("warning", f"另有 {len(orphan)-20} 个 POS 键未出现在 ws"))

    for ja, meta in POS.items():
        if ja in PARTICLES:
            issues.append(("error", f"助词 {ja!r} 不应进 POS"))
        if LATIN_WORD_RE.match(ja):
            issues.append(("error", f"POS 不应收录英文: {ja!r}"))
        if not isinstance(meta, dict):
            issues.append(("error", f"POS[{ja!r}] 不是对象"))
            continue
        pos = meta.get("pos") or ""
        if pos == "助词":
            issues.append(("error", f"POS[{ja!r}] 词性为助词，应删除该键并把用法写入 grams"))
        if not pos:
            issues.append(("error", f"POS[{ja!r}] 缺少 pos"))
            continue
        needs = pos in NEED_FORMS_POS or pos.startswith("句型")
        if needs:
            form = meta.get("form")
            forms = meta.get("forms")
            if not form:
                issues.append(("error", f"POS[{ja!r}]（{pos}）缺少 form"))
            if not isinstance(forms, list) or not forms:
                issues.append(("error", f"POS[{ja!r}]（{pos}）缺少 forms"))
            else:
                names = []
                for item in forms:
                    if not isinstance(item, (list, tuple)) or len(item) < 2:
                        issues.append(("error", f"POS[{ja!r}].forms 项格式应为 [形态名, 词形]"))
                        continue
                    names.append(item[0])
                if pos in VERB_POS:
                    bad = [n for n in names if n not in VERB_FORMS]
                    if bad:
                        issues.append(("error", f"POS[{ja!r}] 动词形态名不在名单: {bad}"))
                    if form and form not in VERB_FORMS:
                        issues.append(("error", f"POS[{ja!r}].form={form!r} 不在动词名单"))
                elif pos in ADJ_POS:
                    bad = [n for n in names if n not in ADJ_FORMS]
                    if bad:
                        issues.append(("error", f"POS[{ja!r}] 形容词形态名不在名单: {bad}"))
                    if form and form not in ADJ_FORMS:
                        issues.append(("error", f"POS[{ja!r}].form={form!r} 不在形容词名单"))

    if skip_jlpt:
        return

    # 词汇等级对照
    leveled = sorted({
        row[0]
        for sent in S if isinstance(sent, dict)
        for row in (sent.get("ws") or [])
        if isinstance(row, (list, tuple)) and len(row) >= 4 and row[3]
    })
    if leveled:
        looked = batch_lookup_vocab(leveled)
        for ja in leveled:
            page_lvs = {
                row[3]
                for sent in S if isinstance(sent, dict)
                for row in (sent.get("ws") or [])
                if isinstance(row, (list, tuple)) and len(row) >= 4 and row[0] == ja and row[3]
            }
            info = looked.get(ja) or {"status": "miss"}
            st = info.get("status")
            if st == "ok":
                if page_lvs - {info["lv"]}:
                    issues.append((
                        "error",
                        f"{ja}: 页面等级 {sorted(page_lvs)} 与索引 {info['lv']} 不一致",
                    ))
            elif st == "ambiguous":
                guess = info.get("lv_guess")
                if guess and page_lvs <= {guess}:
                    issues.append((
                        "warning",
                        f"{ja}: 索引有多义，页面填了 {sorted(page_lvs)}（索引同级猜测 {guess}）",
                    ))
                else:
                    issues.append((
                        "error",
                        f"{ja}: 页面填了等级 {sorted(page_lvs)}，但索引无法唯一确定（{info.get('reason','ambiguous')}）",
                    ))
            else:
                issues.append((
                    "error",
                    f"{ja}: 页面填了等级 {sorted(page_lvs)}，但索引为 {st}，应改成空",
                ))

    # 语法等级对照
    gram_pats = sorted({
        g.get("pat")
        for sent in S if isinstance(sent, dict)
        for g in (sent.get("grams") or [])
        if isinstance(g, dict) and g.get("pat") and g.get("lv")
    })
    if gram_pats:
        glooked = batch_lookup_grammar(gram_pats)
        for pat in gram_pats:
            page_lvs = {
                g.get("lv")
                for sent in S if isinstance(sent, dict)
                for g in (sent.get("grams") or [])
                if isinstance(g, dict) and g.get("pat") == pat and g.get("lv")
            }
            info = glooked.get(pat) or {"status": "miss"}
            st = info.get("status")
            if st == "ok":
                if page_lvs - {info["lv"]}:
                    issues.append((
                        "error",
                        f"语法 {pat}: 页面等级 {sorted(page_lvs)} 与索引 {info['lv']} 不一致",
                    ))
            elif st == "ambiguous":
                guess = info.get("lv_guess")
                if guess and page_lvs <= {guess}:
                    issues.append((
                        "warning",
                        f"语法 {pat}: 索引多义，页面填了 {sorted(page_lvs)}（猜测 {guess}）",
                    ))
                else:
                    issues.append((
                        "error",
                        f"语法 {pat}: 页面填了 {sorted(page_lvs)}，但索引无法唯一确定",
                    ))
            else:
                issues.append((
                    "error",
                    f"语法 {pat}: 页面填了 {sorted(page_lvs)}，但索引为 {st}，应改成空",
                ))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="歌词学习页交卷检查")
    ap.add_argument("html", type=Path, help="要检查的 HTML 文件")
    ap.add_argument("--strict", action="store_true", help="把 warning 也当成失败")
    ap.add_argument("--skip-jlpt", action="store_true", help="跳过与词汇索引对照")
    args = ap.parse_args(argv)

    path = args.html
    if not path.is_file():
        print(f"找不到文件: {path}", file=sys.stderr)
        return 2

    html = path.read_text(encoding="utf-8")
    issues: list[tuple[str, str]] = []
    check_placeholders(html, issues)

    try:
        data = extract_with_node(path)
    except Exception as e:
        print(f"解析 SONG_ID / S / POS 失败: {e}", file=sys.stderr)
        # 模板未填完时也尽量报占位符
        if issues:
            for level, msg in issues:
                print(f"[{level}] {msg}")
        return 2

    check_data(data["songId"], data["S"], data["POS"], issues, skip_jlpt=args.skip_jlpt)

    errors = [m for lv, m in issues if lv == "error"]
    warnings = [m for lv, m in issues if lv == "warning"]

    for level, msg in issues:
        print(f"[{level}] {msg}")

    print(
        f"\n{path}: {len(errors)} error, {len(warnings)} warning"
        + ("  (strict)" if args.strict else "")
    )

    if errors:
        return 1
    if args.strict and warnings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
