"""Extract the audio track of the 1.27 cinematics without ffmpeg.

In Warcraft III 1.27 installs, Movies/<Name>.mpq are AVI files whose audio
stream is plain MP3. Concatenating the audio chunks of the 'movi' list gives
a valid .mp3 file (same as `ffmpeg -i x.mpq -vn -acodec copy x.mp3`).
"""
from __future__ import annotations

import struct
from pathlib import Path

# cinematic file name in 1.27 -> name expected by 1.31 (Movies/Audio/<name>.mp3)
CINEMATICS = ["HumanEd", "HumanOp", "IntroX", "NightElfEd", "OrcEd", "OutroX",
              "TutorialIn", "TutorialOp", "UndeadEd"]


def _chunks(data, start, end):
    pos = start
    while pos + 8 <= end:
        fourcc = data[pos:pos + 4]
        (size,) = struct.unpack_from("<I", data, pos + 4)
        yield fourcc, pos + 8, size
        pos += 8 + size + (size & 1)


def avi_audio(path) -> bytes | None:
    data = Path(path).read_bytes()
    if data[:4] != b"RIFF" or data[8:12] != b"AVI ":
        return None
    audio_stream = None
    stream_index = 0
    movi = None
    for fourcc, off, size in _chunks(data, 12, len(data)):
        if fourcc != b"LIST":
            continue
        kind = data[off:off + 4]
        if kind == b"hdrl":
            for f2, o2, s2 in _chunks(data, off + 4, off + size):
                if f2 == b"LIST" and data[o2:o2 + 4] == b"strl":
                    for f3, o3, _ in _chunks(data, o2 + 4, o2 + s2):
                        if f3 == b"strh" and data[o3:o3 + 4] == b"auds" and audio_stream is None:
                            audio_stream = stream_index
                    stream_index += 1
        elif kind == b"movi":
            movi = (off + 4, off + size)
    if audio_stream is None or movi is None:
        return None
    tag = b"%02dwb" % audio_stream
    out = []

    def walk(start, end):
        for f, o, s in _chunks(data, start, end):
            if f == tag:
                out.append(data[o:o + s])
            elif f == b"LIST" and data[o:o + 4] == b"rec ":
                walk(o + 4, o + s)

    walk(*movi)
    return b"".join(out) if out else None


def extract_cinematic_audio(install_dir, dest_dir, log=print):
    """Write movies/audio/<name>.mp3 for every cinematic found in <install>/Movies."""
    movies = None
    for child in Path(install_dir).iterdir():
        if child.is_dir() and child.name.lower() == "movies":
            movies = child
    if movies is None:
        log("  | ⚠️ No Movies folder in the 1.27 install: cinematic audio not extracted")
        return 0
    files = {p.stem.lower(): p for p in movies.iterdir() if p.suffix.lower() == ".mpq"}
    dest_dir = Path(dest_dir)
    done, missing = 0, []
    for name in CINEMATICS:
        src = files.get(name.lower())
        audio = avi_audio(src) if src else None
        if not audio:
            missing.append(name)
            continue
        dest_dir.mkdir(parents=True, exist_ok=True)
        (dest_dir / f"{name.lower()}.mp3").write_bytes(audio)
        done += 1
    log(f"  | 🎬 Cinematic audio from the 1.27 movies: {done}/{len(CINEMATICS)}"
        + (f" (missing: {', '.join(missing)})" if missing else ""))
    return done
