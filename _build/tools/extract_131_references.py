"""Maintainer tool: refresh the bundled 1.31 references from a 1.31 install (enUS).

    python _build/tools/extract_131_references.py "<Warcraft III 1.31 folder>"

Writes:
  __Misc_Tools/mpq_to_casc_converter/structure.txt  exact file list of the 1.31 enUS locale
  __Misc_Tools/locale_templates/<path>              English ui/ and units/ text files, used to
                                                    complete 1.27 files with the keys added later
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from __Misc_Tools.casc_reader.casc import CASCStorage  # noqa: E402

PREFIX = "War3.w3mod:_Locales/enUS.w3mod:"


def main(game_dir):
    s = CASCStorage(game_dir)
    entries = sorted((k[len(PREFIX):].replace(":", "/"), c) for k, c in s.root_entries().items()
                     if k.startswith(PREFIX))
    structure = [p.lower() for p, _ in entries]
    (ROOT / "__Misc_Tools/mpq_to_casc_converter/structure.txt").write_text(
        "\n".join(structure) + "\n", encoding="utf-8")
    out = ROOT / "__Misc_Tools/locale_templates"
    n = 0
    for path, ckey in entries:
        low = path.lower()
        if not low.endswith((".txt", ".fdf")) or not low.startswith(("ui/", "units/")):
            continue
        if not s.is_present(ckey):
            continue
        dest = out.joinpath(*low.split("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(s.read_ckey(ckey))
        n += 1
    print(f"structure.txt: {len(structure)} entries ({s.version}); {n} reference text files")


if __name__ == "__main__":
    main(sys.argv[1])
