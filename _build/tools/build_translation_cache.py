"""Maintainer tool: build the bundled translation caches (translations/<region>.json).

The strings that exist in 1.31 but not in a 1.27 language pack never change,
so they are translated once (with context-aware AI translation, or by a
human) and shipped with the patcher. Users then need no API, no key, no GPU.

  export  -> list the English strings missing from a 1.27 language
             python _build/tools/build_translation_cache.py export MPQ_Data/csCZ-MPQ csCZ
  import  -> validate a translated JSON file and merge it into the cache
             python _build/tools/build_translation_cache.py import csCZ translated.json
  check   -> validate every cache file

Translated JSON format: {"<english text>": "<translation>", ...}
Game tokens (|cffRRGGBB, |r, |n, %s, %d, <A000,DataA1>, \\n...) must be kept.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from __Misc_Tools.translation.translator import is_translatable, _PROTECT_RE  # noqa: E402
from __Misc_Tools.translation.string_merge import (  # noqa: E402
    read_text, INI_KEY_RE, FDF_KEY_RE, _split_quoted)

TEMPLATES = ROOT / "__Misc_Tools"
CACHE_DIR = ROOT / "translations"
ARCHIVE_PRIORITY = ["War3Patch.mpq", "War3xlocal.mpq", "War3x.mpq", "war3.mpq"]

FILES = [
    ("ini", "worldeditor_translator/worldeditstrings_template.txt", ("UI", "WorldEditStrings.txt")),
    ("ini", "worldeditor_translator/worldeditgamestrings_template.txt", ("UI", "WorldEditGameStrings.txt")),
    ("fdf", "wc3keys_translater/globalstrings_template.fdf", ("UI", "FrameDef", "GlobalStrings.fdf")),
]


def find_ci(base: Path, *parts):
    cur = base
    for part in parts:
        if not cur.is_dir():
            return None
        cur = next((c for c in cur.iterdir() if c.name.lower() == part.lower()), None)
        if cur is None:
            return None
    return cur


def effective_file(region_dir: Path, parts):
    for archive in ARCHIVE_PRIORITY:
        f = find_ci(region_dir, archive, *parts)
        if f and f.is_file():
            return f
    return None


def parse(kind, text):
    out = {}
    for line in text.splitlines():
        if kind == "ini":
            m = INI_KEY_RE.match(line)
            if m and m.group(2) not in out:
                out[m.group(2)] = _split_quoted(m.group(4))[0]
        else:
            m = FDF_KEY_RE.match(line)
            if m and m.group(2) not in out:
                out[m.group(2)] = m.group(4)
    return out


def missing_strings(region_dir: Path):
    items = []
    for kind, template_rel, parts in FILES:
        template = parse(kind, read_text(TEMPLATES / template_rel)[0])
        f = effective_file(region_dir, parts)
        localized = parse(kind, read_text(f)[0]) if f else {}
        for key, en in template.items():
            if key in localized:
                continue
            if kind == "fdf" and len(en.strip()) <= 1:
                continue
            if is_translatable(en):
                items.append({"file": parts[-1], "key": key, "en": en})
    return items


def tokens(text):
    return sorted(_PROTECT_RE.findall(text))


def validate(english, translated):
    problems = []
    if tokens(english) != tokens(translated):
        problems.append(f"tokens differ: {tokens(english)} vs {tokens(translated)}")
    if "&" in english and "&" not in translated:
        problems.append("menu accelerator '&' lost")
    if '"' in translated:
        problems.append("contains a double quote")
    if not translated.strip():
        problems.append("empty")
    return problems


def cmd_export(region_dir, region, out=None):
    items = missing_strings(Path(region_dir))
    out = Path(out or CACHE_DIR / "_todo" / f"{region}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(items)} strings to translate -> {out}")


def load_cache(region):
    f = CACHE_DIR / f"{region}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    return {"region": region, "source": "", "strings": {}}


def save_cache(region, cache):
    CACHE_DIR.mkdir(exist_ok=True)
    cache["strings"] = dict(sorted(cache["strings"].items()))
    (CACHE_DIR / f"{region}.json").write_text(
        json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_import(region, translated_file, source="AI translation, context-aware"):
    data = json.loads(Path(translated_file).read_text(encoding="utf-8"))
    cache = load_cache(region)
    cache["source"] = source
    ok = rejected = 0
    for en, tr in data.items():
        tr = tr.replace('"', "'")
        problems = validate(en, tr)
        if problems:
            rejected += 1
            print(f"  rejected {en[:60]!r}: {'; '.join(problems)}")
            continue
        cache["strings"][en] = tr
        ok += 1
    save_cache(region, cache)
    print(f"{region}: {ok} imported, {rejected} rejected, {len(cache['strings'])} in cache")


def cmd_check():
    bad = 0
    for f in sorted(CACHE_DIR.glob("*.json")):
        cache = json.loads(f.read_text(encoding="utf-8"))
        for en, tr in cache.get("strings", {}).items():
            problems = validate(en, tr)
            if problems:
                bad += 1
                print(f"{f.name}: {en[:50]!r}: {'; '.join(problems)}")
        print(f"{f.name}: {len(cache.get('strings', {}))} strings")
    return bad


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "export":
        cmd_export(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    elif len(sys.argv) >= 4 and sys.argv[1] == "import":
        cmd_import(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == "check":
        sys.exit(1 if cmd_check() else 0)
    else:
        print(__doc__)
