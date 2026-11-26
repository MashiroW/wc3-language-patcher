"""Where the 1.27 files are read from.

FolderSource  : MPQ_Data/<lang>-MPQ/<archive>.mpq/... (extracted manually, the
                original workflow)
ArchiveSource : the four .mpq archives of a 1.27 install, read directly
                (no extraction step, nothing written to disk but the result)

Both expose:
  index                  {filename_lower: [(handle, dir_parts_lower, priority)]}
  write(handle, dest)    copy one file to dest
  children(archive, *dirs) -> [(filename, handle)] files directly in that folder
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

PRIORITY = {"war3.mpq": 0, "war3x.mpq": 1, "war3xlocal.mpq": 2, "war3patch.mpq": 3}


class FolderSource:
    def __init__(self, region_folder, log=print):
        self.root = Path(region_folder)
        self.index = {}
        self.folders = {}
        for child in (self.root.iterdir() if self.root.exists() else []):
            prio = PRIORITY.get(child.name.lower())
            if prio is None or not child.is_dir():
                continue
            self.folders[child.name.lower()] = child
            for root, _, files in os.walk(child):
                parts = [p.lower() for p in Path(root).relative_to(child).parts]
                for f in files:
                    if f != "placeholder.txt":
                        self.index.setdefault(f.lower(), []).append((Path(root) / f, parts, prio))
        missing = [a for a in PRIORITY if a not in self.folders]
        for a in missing:
            log(f"  | ⚠️ {a} folder not found in {self.root.name}")

    def write(self, handle, dest: Path):
        shutil.copy2(handle, dest)

    def children(self, archive, *dirs):
        folder = self.folders.get(archive.lower())
        for d in dirs:
            if folder is None:
                return []
            folder = next((c for c in folder.iterdir() if c.is_dir() and c.name.lower() == d.lower()), None)
        if folder is None:
            return []
        return [(f.name, f) for f in folder.iterdir() if f.is_file()]

    def close(self):
        pass


class ArchiveSource:
    def __init__(self, install_dir, log=print):
        from __Misc_Tools.mpq_reader.mpq import MPQArchive
        from __Misc_Tools.mpq_reader.install_extractor import find_archives, ARCHIVES

        found = find_archives(install_dir)
        missing = [a for a in ARCHIVES if a not in found]
        if missing:
            raise FileNotFoundError(f"missing archive(s) in {install_dir}: {', '.join(missing)}")
        self.archives = {name.lower(): MPQArchive(path) for name, path in found.items()}
        # War3Patch.mpq has no (listfile): probe the names known from the others
        known = []
        for name in ("war3.mpq", "war3x.mpq", "war3xlocal.mpq"):
            known.extend(self.archives[name].listfile())
        self.names = {}
        for name, arc in self.archives.items():
            listed = arc.listfile() if name != "war3patch.mpq" else [n for n in dict.fromkeys(known) if arc.has_file(n)]
            self.names[name] = [n for n in listed if not n.startswith("(") and arc.has_file(n)]
        self.index = {}
        for name, files in self.names.items():
            prio = PRIORITY[name]
            for n in files:
                parts = n.replace("/", "\\").split("\\")
                self.index.setdefault(parts[-1].lower(), []).append(
                    ((name, n), [p.lower() for p in parts[:-1]], prio))
        total = sum(len(v) for v in self.names.values())
        log(f"  | 📦 Reading the 1.27 archives directly ({total} files indexed, no extraction needed)")

    def write(self, handle, dest: Path):
        archive, name = handle
        data = self.archives[archive].read_file(name)
        if data is None:
            raise FileNotFoundError(name)
        dest.write_bytes(data)

    def children(self, archive, *dirs):
        archive = archive.lower()
        prefix = [d.lower() for d in dirs]
        out = []
        for n in self.names.get(archive, []):
            parts = n.replace("/", "\\").split("\\")
            if [p.lower() for p in parts[:-1]] == prefix:
                out.append((parts[-1], (archive, n)))
        return out

    def close(self):
        for a in self.archives.values():
            a.close()
