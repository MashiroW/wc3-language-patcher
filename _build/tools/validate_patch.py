"""Deep check of a built <lang>_patch.zip.

    python _build/tools/validate_patch.py <patch.zip> <workspace> <lang> [<templates dir>]

Checks: junk files, target originals kept, text completeness, campaign menu
-> map files, maps readable as MPQ with localized strings, audio headers.
Exit code 1 if a blocking problem is found.
"""
from __future__ import annotations

import collections
import io
import re
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from __Misc_Tools.mpq_reader.mpq import MPQArchive  # noqa: E402
from __Misc_Tools.translation.string_merge import INI_KEY_RE, FDF_KEY_RE, _split_quoted  # noqa: E402
from __Misc_Tools.translation.translator import is_translatable  # noqa: E402

problems, warnings = [], []


def ok(msg):
    print(f"  OK    {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  WARN  {msg}")


def bad(msg):
    problems.append(msg)
    print(f"  FAIL  {msg}")


def decode(b):
    t = b.decode("utf-8-sig", errors="strict")
    return t.lstrip("﻿")


def ini_values(text, fdf=False):
    out = {}
    rx = FDF_KEY_RE if fdf else INI_KEY_RE
    for line in text.splitlines():
        m = rx.match(line)
        if m and m.group(2) not in out:
            out[m.group(2)] = m.group(4) if fdf else _split_quoted(m.group(4))[0]
    return out


def main(zip_path, workspace, lang, templates=None):
    zip_path, workspace = Path(zip_path), Path(workspace)
    templates = Path(templates) if templates else ROOT / "__Misc_Tools"
    z = zipfile.ZipFile(zip_path)
    names = z.namelist()
    lower = {n.lower(): n for n in names}
    print(f"\n=== {zip_path.name}: {len(names)} files, {zip_path.stat().st_size // 2**20} MB")
    top = collections.Counter(n.split("/")[0].lower() for n in names)
    print("  content:", dict(top))

    # 1. junk
    junk = [n for n in names if n.split("/")[-1].lower() in (
        "placeholder.txt", ".extracted_from_target", "thumbs.db", ".ds_store")]
    if junk:
        bad(f"{len(junk)} junk file(s) in the patch, e.g. {junk[:3]}")
    else:
        ok("no junk files")

    # 2. target originals kept (non-sound files; sounds are replaced by 1.27 voices on purpose)
    casc = workspace / "CASC_Data" / f"{lang.lower()}.w3mod"
    if casc.exists():
        files = [p for p in casc.rglob("*") if p.is_file() and p.name not in ("placeholder.txt", ".extracted_from_target")]
        diff = missing = replaced_sound = editor_restored = 0
        homemade = ROOT / "_HomeMade_Data"
        hm = next((d for d in homemade.iterdir() if d.is_dir() and d.name.lower().startswith(lang.lower())), None) if homemade.exists() else None
        hm_files = {str(p.relative_to(hm)).replace("\\", "/").lower() for p in hm.rglob("*") if p.is_file()} if hm else set()
        for p in files:
            rel = str(p.relative_to(casc)).replace("\\", "/")
            if any(part.lower().endswith((".w3m", ".w3x")) for part in rel.split("/")):
                continue
            n = lower.get(rel.lower())
            if n is None:
                top_dir = rel.split("/")[0].lower()
                if top_dir in ("maps", "movies", "sound", "ui", "units", "campaign", "fonts"):
                    missing += 1
                continue
            if z.read(n) != p.read_bytes():
                if rel.lower() in ("ui/worldeditstrings.txt", "ui/worldeditgamestrings.txt"):
                    editor_restored += 1  # English values replaced by 1.27 text, on purpose
                elif rel.lower().startswith("sound/"):
                    replaced_sound += 1
                elif rel.lower() in hm_files:
                    pass
                else:
                    diff += 1
        if diff or missing:
            bad(f"target originals: {diff} modified, {missing} missing (of {len(files)})")
        else:
            ok(f"{len(files)} original target files kept ({replaced_sound} voices replaced by 1.27 on purpose, "
               f"{editor_restored} World Editor text file(s) with English values restored from 1.27)")
    else:
        warn("no CASC_Data for this language: nothing from the target to check")

    # 3. texts complete
    checks = [("ui/worldeditstrings.txt", "worldeditor_translator/worldeditstrings_template.txt", False),
              ("ui/worldeditgamestrings.txt", "worldeditor_translator/worldeditgamestrings_template.txt", False),
              ("ui/framedef/globalstrings.fdf", "wc3keys_translater/globalstrings_template.fdf", True)]
    for rel, tpl, fdf in checks:
        n = lower.get(rel)
        if n is None:
            bad(f"{rel} missing")
            continue
        try:
            text = decode(z.read(n))
        except UnicodeDecodeError as e:
            bad(f"{rel} is not valid UTF-8: {e}")
            continue
        got = ini_values(text, fdf)
        ref = ini_values(decode((templates / tpl).read_bytes()), fdf)
        miss = [k for k in ref if k not in got]
        english = [k for k in ref if k in got and got[k] == ref[k] and is_translatable(ref[k])
                   and len(ref[k].strip()) > 1]
        msg = f"{rel}: {len(got)} keys, {len(miss)} missing vs reference, {len(english)} identical to English"
        original = casc.exists() and any(
            str(p.relative_to(casc)).replace("\\", "/").lower() == rel for p in casc.rglob(rel.split("/")[-1]))
        if original:
            ok(msg + " (original file of the target, kept as-is)")
        else:
            (bad if miss else ok)(msg)

    # 4. campaign menus -> maps
    for rel in ("ui/campaignstrings.txt", "ui/campaignstrings_exp.txt"):
        n = lower.get(rel)
        if n is None:
            bad(f"{rel} missing")
            continue
        text = decode(z.read(n))
        missions = re.findall(r'^Mission\d+="[^"]*","([^"]*)","([^"]*)"', text, re.M)
        unresolved = []
        for title, path in missions:
            p = path.replace("\\", "/").lower()
            if not any(c in lower for c in (p, "maps/" + p)):
                unresolved.append(path)
        if unresolved:
            warn(f"{rel}: {len(missions)} missions, {len(unresolved)} map path(s) not inside the patch "
                 f"(the game's own map is used), e.g. {unresolved[:2]}")
        else:
            ok(f"{rel}: {len(missions)} missions, every map path is inside the patch")
        if missions:
            print(f"        e.g. {missions[0][0]!r} -> {missions[0][1]}")

    # 5. maps are valid MPQ archives with strings
    maps = [n for n in names if n.lower().endswith((".w3m", ".w3x")) and not n.endswith("/")]
    broken, accented, checked = [], 0, 0
    with tempfile.TemporaryDirectory() as tmp:
        for n in maps:
            data = z.read(n)
            if len(data) < 512:
                continue
            f = Path(tmp) / "m.mpq"
            f.write_bytes(data)
            try:
                with MPQArchive(f) as a:
                    wts = a.read_file("war3map.wts")
                    j = a.read_file("war3map.j") or a.read_file("scripts\\war3map.j")
                    if not wts:
                        broken.append((n, "no war3map.wts"))
                        continue
                    checked += 1
                    if re.search(rb"[\xc3\xc5\xd0\xd1\xe0-\xef]", wts):
                        accented += 1
            except Exception as e:
                broken.append((n, str(e)[:60]))
    if broken:
        bad(f"{len(broken)} map(s) unreadable, e.g. {broken[:2]}")
    else:
        ok(f"{checked} maps open as MPQ with war3map.wts ({accented} contain non-ASCII localized text)")

    # 6. audio headers
    bad_audio = collections.Counter()
    counts = collections.Counter()
    for n in names:
        ext = n.lower().rsplit(".", 1)[-1]
        if ext not in ("wav", "mp3", "ogg"):
            continue
        counts[ext] += 1
        head = z.open(n).read(12)
        if ext == "wav" and not (head[:4] == b"RIFF" and head[8:12] == b"WAVE"):
            if head[:3] == b"ID3" or (head[0] == 0xFF and head[1] & 0xE0 == 0xE0):
                warn(f"{n}: MP3 data with a .wav name (as in the original 1.27 data)")
            else:
                bad_audio[ext] += 1
        elif ext == "mp3" and not (head[:3] == b"ID3" or (head[0] == 0xFF and head[1] & 0xE0 == 0xE0)):
            bad_audio[ext] += 1
        elif ext == "ogg" and head[:4] != b"OggS":
            bad_audio[ext] += 1
    if bad_audio:
        bad(f"invalid audio headers: {dict(bad_audio)}")
    else:
        ok(f"audio headers valid: {dict(counts)}")

    print(f"\n  RESULT: {len(problems)} problem(s), {len(warnings)} warning(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(*sys.argv[1:5]))
