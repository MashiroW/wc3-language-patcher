"""Bring 1.27 localisation text files up to the 1.31 layout.

The modern template (English 1.31 file) is used as the skeleton: its order,
sections and comments are kept. For every key:
  - the 1.27 localised value is used when it exists (original Blizzard text),
  - otherwise the English value is translated (bundled cache / online / English).
"""
from __future__ import annotations

import re
from pathlib import Path

INI_KEY_RE = re.compile(r"^(\s*)([A-Za-z0-9_]+)(\s*=)(.*)$")
FDF_KEY_RE = re.compile(r'^(\s*)([A-Za-z0-9_]+)(\s+)"((?:[^"\\]|\\.)*)"(\s*,?)(.*)$')

_MOJIBAKE_BOM = "ï»¿"  # UTF-8 BOM decoded as cp1252, found in some 1.27 files


def read_text(path) -> tuple[str, bool]:
    raw = Path(path).read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    while text.startswith(_MOJIBAKE_BOM) or text.startswith("﻿"):
        text = text[3:] if text.startswith(_MOJIBAKE_BOM) else text[1:]
    return text, had_bom


def write_text(path, text: str, bom: bool):
    text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    with open(path, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)


def _ini_values(text):
    values = {}
    for line in text.splitlines():
        m = INI_KEY_RE.match(line)
        if m and m.group(2) not in values:
            values[m.group(2)] = m.group(4)
    return values


def _split_quoted(raw: str):
    s = raw.strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"') and s.count('"') == 2:
        return s[1:-1], True
    return s, False


def merge_ini_strings(template_path, target_path, translator, log=print):
    """WorldEditStrings.txt / WorldEditGameStrings.txt style files (KEY=value)."""
    tpl_text, _ = read_text(template_path)
    tgt_text, bom = read_text(target_path)
    localized = _ini_values(tgt_text)

    out, kept, translated, dropped = [], 0, 0, 0
    template_keys = set()
    for line in tpl_text.splitlines():
        m = INI_KEY_RE.match(line)
        if not m:
            out.append(line)
            continue
        indent, key, eq, raw = m.groups()
        template_keys.add(key)
        if key in localized:
            out.append(f"{indent}{key}{eq}{localized[key]}")
            kept += 1
            continue
        inner, quoted = _split_quoted(raw)
        new = translator.translate(inner)
        if new != inner:
            translated += 1
        out.append(f'{indent}{key}{eq}"{new}"' if quoted else f"{indent}{key}{eq}{new}")
    dropped = len(set(localized) - template_keys)
    write_text(target_path, "\n".join(out) + "\n", bom)
    log(f"  |   |  📊 {Path(target_path).name}: {kept} original strings kept, "
        f"{len(template_keys) - kept} added ({translated} translated), {dropped} obsolete removed")


def _fdf_values(text):
    values = {}
    for line in text.splitlines():
        m = FDF_KEY_RE.match(line)
        if m and m.group(2) not in values:
            values[m.group(2)] = m.group(4)
    return values


def merge_fdf_strings(template_path, target_path, translator, log=print):
    """GlobalStrings.fdf style files (KEY  "value",)."""
    tpl_text, _ = read_text(template_path)
    tgt_text, bom = read_text(target_path)
    localized = _fdf_values(tgt_text)

    out, kept, added, translated = [], 0, 0, 0
    for line in tpl_text.splitlines():
        m = FDF_KEY_RE.match(line)
        if not m:
            out.append(line)
            continue
        indent, key, space, value, comma, rest = m.groups()
        if key in localized:
            value = localized[key]
            kept += 1
        else:
            added += 1
            # single-letter values are keyboard shortcuts: keep them
            new = value if len(value.strip()) <= 1 else translator.translate(value)
            if new != value:
                translated += 1
            value = new.replace('\\"', '"').replace('"', '\\"')
        out.append(f'{indent}{key}{space}"{value}"{comma}{rest}')
    write_text(target_path, "\n".join(out) + "\n", bom)
    log(f"  |   |  📊 {Path(target_path).name}: {kept} original strings kept, "
        f"{added} added ({translated} translated)")


# ------------------------------------------------------------ campaigns ---
_TRIPLE_RE = re.compile(r'^\s*"([^"]*)"\s*,\s*"([^"]*)"\s*,\s*"([^"]*)"\s*$')


def _modernize_path(key: str, path: str) -> str:
    """1.27 -> 1.31 paths: 'Maps\\Campaign\\X.w3m' -> 'Campaign\\X.w3m',
    cinematic 'HumanOp' -> 'Movies\\HumanOp'."""
    if key.endswith("Cinematic"):
        return path if "\\" in path or "/" in path else f"Movies\\{path}"
    if path.lower().startswith("maps\\") or path.lower().startswith("maps/"):
        return path[5:]
    return path


def convert_campaign_strings(target_path, template_path=None, log=print):
    """Convert a 1.27 CampaignStrings(_exp).txt to the 1.31 format in place.

    With a template, the template's structure and file paths are kept and
    only the localised header/name parts come from the 1.27 file. Without a
    template, the 1.27 file is kept and only its paths are modernised.
    """
    text, bom = read_text(target_path)
    sections, current = {}, None
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("[") and s.endswith("]"):
            current = s[1:-1]
            sections.setdefault(current, {})
            continue
        m = INI_KEY_RE.match(line)
        if m and current is not None:
            sections[current][m.group(2)] = m.group(4)

    def localized(section, key):
        return sections.get(section, {}).get(key)

    out = []
    if template_path and Path(template_path).exists():
        tpl, _ = read_text(template_path)
        current = None
        for line in tpl.splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                current = s[1:-1]
                out.append(line)
                continue
            m = INI_KEY_RE.match(line)
            if not m or current is None:
                out.append(line)
                continue
            indent, key, eq, raw = m.groups()
            loc = localized(current, key)
            if loc is not None and key in ("Header", "Name"):
                raw = loc
            else:
                t = _TRIPLE_RE.match(raw)
                lt = _TRIPLE_RE.match(loc) if loc else None
                if t and lt:
                    raw = f'"{lt.group(1)}","{lt.group(2)}","{t.group(3)}"'
            out.append(f"{indent}{key}{eq}{raw}")
    else:
        current = None
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("[") and s.endswith("]"):
                current = s[1:-1]
            m = INI_KEY_RE.match(line)
            t = _TRIPLE_RE.match(m.group(4)) if m else None
            if t:
                indent, key, eq, _ = m.groups()
                line = f'{indent}{key}{eq}"{t.group(1)}","{t.group(2)}","{_modernize_path(key, t.group(3))}"'
            out.append(line)
    write_text(target_path, "\n".join(out) + "\n", bom)
    log(f"  |   |  ✅ Converted {Path(target_path).name} to the 1.31 format")


def prefer_localized_over_english(target_path, localized_path, english_template, log=print, translator=None):
    """Target original kept, except the values that are still plain English:
    those take the 1.27 localized value when one exists (World Editor texts).

    The target file keeps its own keys, order, comments and already
    localized values; only lines whose value equals the English reference
    are replaced. Returns the number of replaced values."""
    tgt_text, bom = read_text(target_path)
    localized = _ini_values(read_text(localized_path)[0])
    english = _ini_values(read_text(english_template)[0])
    out, replaced, translated = [], 0, 0
    for line in tgt_text.splitlines():
        m = INI_KEY_RE.match(line)
        if m:
            indent, key, eq, raw = m.groups()
            en = english.get(key)
            loc = localized.get(key)
            if en is not None and raw.strip() == en.strip():
                if loc is not None and loc.strip() != en.strip():
                    line = f"{indent}{key}{eq}{loc}"
                    replaced += 1
                elif translator is not None:
                    # no 1.27 text for this key: same rule as missing strings
                    inner, quoted = _split_quoted(raw)
                    new = translator.translate(inner, allow_empty=False)
                    if new != inner:
                        line = f'{indent}{key}{eq}"{new}"' if quoted else f"{indent}{key}{eq}{new}"
                        translated += 1
        out.append(line)
    if replaced or translated:
        write_text(target_path, "\n".join(out) + "\n", bom)
    log(f"  |   |  📊 {Path(target_path).name}: target original kept, {replaced} English value(s) "
        f"replaced by the original 1.27 text, {translated} by AI translations")
    return replaced + translated
