"""Decode clips on demand so two pets fit in memory.

Keeping every frame resident costs 1 MiB per frame on a Retina screen, about
4.5 GiB for the 35-clip set. A clip decodes about ten times faster than it plays,
so a worker thread can fill it while the first frames are already on screen.
Frames are QImage because QPixmap may only be created on the GUI thread.
"""
import gzip
import json
import threading
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QImage


class ClipFrames(list):
    """Frames of one clip. A worker appends while playback already uses the first ones."""

    def __init__(self, total):
        super().__init__()
        self.total = max(1, int(total))
        self.done = threading.Event()
        self.error = None
        self.cancelled = False

    def wait(self, timeout=60):
        """Block until decoded; only start-up and tests should need this."""
        self.done.wait(timeout)
        if self.error:
            raise RuntimeError(self.error)
        return self


def to_image(raw, size):
    """Premultiply here, in the worker, so painting needs no per-frame conversion."""
    return QImage(raw, size, size, size * 4, QImage.Format.Format_RGBA8888).convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)


def packed_frames(packed, path):
    """Yield frames from a cache made by prepare_assets.py when it still matches the source."""
    metadata = packed.with_suffix('.json')
    if not (packed.is_file() and metadata.is_file()):
        return None
    meta = json.loads(metadata.read_text(encoding='utf-8'))
    stat = path.stat()
    if meta['sourceSize'] != stat.st_size or meta['sourceMtime'] != stat.st_mtime_ns:
        return None
    raw = gzip.decompress(packed.read_bytes())
    stride = 512 * 512 * 4
    if len(raw) != meta['frames'] * stride:
        return None
    return [raw[offset:offset + stride] for offset in range(0, len(raw), stride)]


def decode_into(clip, path, size, packed=None):
    try:
        cached = packed_frames(packed, path) if packed else None
        if cached:
            clip.total = len(cached)
            for raw in cached:
                if clip.cancelled:
                    return
                image = Image.frombytes('RGBA', (512, 512), raw)
                if size != 512:
                    image = image.resize((size, size), Image.Resampling.LANCZOS)
                clip.append(to_image(image.tobytes(), size))
        elif Path(path).suffix.lower() == '.webm':
            from video_frames import rgba_frames
            for raw in rgba_frames(path, size):
                if clip.cancelled:
                    return
                clip.append(to_image(raw, size))
            clip.total = max(1, len(clip))
        else:
            with Image.open(path) as source:
                clip.total = source.n_frames
                for index in range(source.n_frames):
                    if clip.cancelled:
                        return
                    source.seek(index)
                    image = source.convert('RGBA')
                    if image.size != (size, size):
                        image = image.resize((size, size), Image.Resampling.LANCZOS)
                    clip.append(to_image(image.tobytes(), size))
        if not clip:
            clip.error = '动画没有可播放帧：' + str(path)
    except Exception as error:
        clip.error = str(error)
    finally:
        clip.done.set()


def start_decode(path, size, expected, packed=None):
    clip = ClipFrames(expected)
    threading.Thread(target=decode_into, args=(clip, path, size, packed), daemon=True).start()
    return clip
