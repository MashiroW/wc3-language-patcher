"""Translation of strings that exist in the modern (1.31+) game but not in 1.27.

Order of lookup for each English string:
  1. Bundled translation cache  (translations/<region>.json, shipped with the
     program, generated once by the maintainer with context-aware AI
     translation; see tools/build_translation_cache.py)
  2. Optional online machine translation (free endpoints, no API key).
     Disabled by default because the free endpoints are rate-limited and may
     be blocked; it can be enabled with allow_online=True.
  3. The English text itself (the game shows it as-is).

Nothing here needs PyTorch, transformers, GPUs or API keys.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

# Region code (game) -> language codes for the online services
REGION_TO_ONLINE_LANG = {
    "frFR": "fr", "deDE": "de", "esES": "es", "esMX": "es", "itIT": "it",
    "plPL": "pl", "ruRU": "ru", "csCZ": "cs", "koKR": "ko", "ptBR": "pt",
    "zhCN": "zh-CN", "zhTW": "zh-TW", "enUS": "en",
}

# Game-specific tokens that must never be translated or altered.
_PROTECT_RE = re.compile(
    r"\|[cC][0-9a-fA-F]{8}|\|[rR]|\|[nN]"        # colour codes / line breaks
    r"|%\d*\$?[-+ #0]*\d*(?:\.\d+)?[sdifuxXc%]"  # printf-style
    r"|<[^<>]+>"                              # <AHbz,DataA1> data references
    r"|\$[A-Za-z0-9_]+\$"                     # $var$
    r"|\\n"                                    # literal \n
)

# A value that is only a reference to another key (e.g. WESTRING_TERRAIN)
_REFERENCE_RE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def is_translatable(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if _REFERENCE_RE.match(stripped):
        return False
    # nothing but tokens, digits and punctuation
    leftover = _PROTECT_RE.sub("", stripped)
    return bool(re.search(r"[A-Za-z]", leftover))


def _protect(text: str):
    tokens = []

    def repl(m):
        tokens.append(m.group(0))
        return f"[[{len(tokens) - 1}]]"

    return _PROTECT_RE.sub(repl, text), tokens


def _unprotect(text: str, tokens) -> str | None:
    for i, tok in enumerate(tokens):
        pattern = re.compile(r"\[\s*\[\s*%d\s*\]\s*\]" % i)
        if not pattern.search(text):
            return None  # a token got lost: reject this translation
        text = pattern.sub(lambda _m, t=tok: t, text, count=1)
    return text


class _OnlineBackend:
    """Free online machine translation. Best effort only."""

    def __init__(self, target: str, log=None):
        self.target = target
        self.log = log or (lambda *_: None)
        self.disabled = False
        self._last = 0.0

    def _get(self, url: str, timeout=15) -> str:
        # stay well below the rate limits
        wait = 0.35 - (time.time() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.time()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8")

    def _google(self, text: str) -> str:
        q = urllib.parse.urlencode(
            {"client": "gtx", "sl": "en", "tl": self.target, "dt": "t", "q": text})
        data = json.loads(self._get("https://translate.googleapis.com/translate_a/single?" + q))
        return "".join(part[0] for part in data[0] if part and part[0])

    def _mymemory(self, text: str) -> str:
        q = urllib.parse.urlencode({"q": text, "langpair": f"en|{self.target}"})
        data = json.loads(self._get("https://api.mymemory.translated.net/get?" + q))
        if data.get("quotaFinished") or str(data.get("responseStatus")) != "200":
            raise RuntimeError(data.get("responseDetails") or "MyMemory quota reached")
        return data["responseData"]["translatedText"]

    def translate(self, text: str) -> str | None:
        if self.disabled:
            return None
        for backend in (self._google, self._mymemory):
            try:
                out = backend(text)
                if out:
                    return out
            except Exception as e:  # network error, 429, quota...
                self.log(f"  |   |   ⚠️ online translation ({backend.__name__[1:]}) failed: {e}")
        # both failed: stop trying for the rest of the run
        self.disabled = True
        self.log("  |   |   ⚠️ Online translation unavailable, keeping English for the remaining strings")
        return None


class StringTranslator:
    def __init__(self, region_code: str, cache_dir: Path, log=None, allow_online=False):
        self.region_code = region_code
        self.log = log or print
        self.cache_file = Path(cache_dir) / f"{region_code}.json"
        self.cache: dict[str, str] = {}
        if self.cache_file.exists():
            with open(self.cache_file, "r", encoding="utf-8") as f:
                self.cache = json.load(f).get("strings", {})
        target = REGION_TO_ONLINE_LANG.get(region_code)
        self.online = _OnlineBackend(target, self.log) if (allow_online and target and target != "en") else None
        self.stats = {"cache": 0, "online": 0, "english": 0}

    def translate(self, english: str) -> str:
        if not is_translatable(english):
            return english
        if english in self.cache:
            self.stats["cache"] += 1
            return self.cache[english]
        if self.online:
            protected, tokens = _protect(english)
            out = self.online.translate(protected)
            if out:
                out = _unprotect(out, tokens)
                if out:
                    self.stats["online"] += 1
                    return out
        self.stats["english"] += 1
        return english

    def summary(self) -> str:
        s = self.stats
        return (f"{s['cache']} from bundled translations, {s['online']} translated online, "
                f"{s['english']} kept in English")
