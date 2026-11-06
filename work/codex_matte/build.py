"""Rebuild the Codex character clips with a clean matte.

Reads outputs/白龙原始素材 and writes outputs/白龙桌宠素材. The result is WebP, whose
alpha plane is lossless, so edges stay crisp and playback no longer needs FFmpeg.

Usage: python3 work/codex_matte/build.py [--only idle,18] [--jobs 6]
"""
import argparse
import json
import multiprocessing
import pathlib
import sys
import time

import numpy as np
from PIL import Image
from scipy import ndimage

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'app'), str(ROOT / 'work/codex_matte')]
from refine import classify, refine
from video_frames import rgba_frames

SOURCE = ROOT / 'outputs/白龙原始素材'
TARGET = ROOT / 'outputs/白龙桌宠素材'
FOLDER = '精修WebP'
NATIVE, SIZE = 720, 512


def shrink(rgba):
    """Downscale on premultiplied alpha so edge pixels keep the line colour."""
    premultiplied = rgba.copy()
    premultiplied[..., :3] *= premultiplied[..., 3:4] / 255.0
    channels = [np.asarray(Image.fromarray(premultiplied[..., i].astype(np.float32), 'F').resize((SIZE, SIZE), Image.LANCZOS))
                for i in range(4)]
    small = np.dstack(channels).clip(0, 255)
    alpha = small[..., 3:4]
    small[..., :3] = np.where(alpha > 0.5, small[..., :3] * 255.0 / np.maximum(alpha, 0.5), 0.0)
    return small.clip(0, 255)


def bleed(rgba):
    """Fill empty pixels with nearby colour: WebP halves chroma, and black would tint the edge."""
    solid = rgba[..., 3] > 200
    if not solid.any():
        return rgba
    rows, columns = ndimage.distance_transform_edt(~solid, return_distances=False, return_indices=True)
    out = rgba.copy()
    empty = rgba[..., 3] < 8
    out[empty, :3] = rgba[rows[empty], columns[empty], :3]
    return out


def residue(frame):
    """Visible olive pixels: the number this tool exists to bring down."""
    rgb, alpha = frame[..., :3].astype(np.float64), frame[..., 3].astype(np.float64)
    _, olive, _, _ = classify(rgb, alpha)
    return int((olive & (alpha > 64)).sum())


def convert(job):
    name, source, target, fps = job
    started = time.monotonic()
    frames, before, after = [], 0, 0
    for index, raw in enumerate(rgba_frames(source, NATIVE)):
        frame = np.frombuffer(raw, np.uint8).reshape(NATIVE, NATIVE, 4)
        clean = refine(frame)
        if index % 16 == 0:
            before += residue(frame)
            after += residue(np.clip(clean + 0.5, 0, 255).astype(np.uint8))
        small = bleed(shrink(clean))
        frames.append(Image.fromarray(np.clip(small + 0.5, 0, 255).astype(np.uint8), 'RGBA'))
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(target, save_all=True, append_images=frames[1:], duration=round(1000 / fps), loop=0,
                   quality=90, method=4, exact=True)
    print(f'{name:12s} {len(frames):4d} frames {target.stat().st_size >> 10:6d} KiB olive {before}->{after} {time.monotonic() - started:.0f}s', flush=True)
    return {'id': name, 'frames': len(frames), 'bytes': target.stat().st_size, 'oliveBefore': before, 'oliveAfter': after}


def clips(manifest):
    """Every clip dictionary in the manifest, in any slot."""
    for key in ('idle', 'dragAnimation', 'landingAnimation', 'quotaAnimation'):
        yield manifest[key]
    for key in ('additionalIdleAnimations', 'variants', 'workAnimations', 'movementAnimations'):
        yield from (item for item in manifest[key] if item)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='')
    parser.add_argument('--jobs', type=int, default=6)
    options = parser.parse_args()
    only = set(filter(None, options.only.split(',')))
    manifest = json.loads((SOURCE / '素材清单.json').read_text(encoding='utf-8'))
    jobs = []
    for clip in clips(manifest):
        source = SOURCE / clip.get('playbackFile', clip['file'])
        target = TARGET / FOLDER / f'{source.stem}.webp'
        if not only or clip['id'] in only:
            fps = 30 if clip.get('movementAngleRange') else 24
            jobs.append((clip['id'], source, target, fps))
        clip['file'] = f'{FOLDER}/{source.stem}.webp'
        clip.pop('playbackFile', None)
    jobs.sort(key=lambda job: -job[1].stat().st_size)
    with multiprocessing.Pool(options.jobs) as pool:
        report = pool.map(convert, jobs, chunksize=1)
    (TARGET / '素材清单.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding='utf-8')
    (TARGET / '精修报告.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    print('clips', len(report), 'MiB', sum(r['bytes'] for r in report) >> 20,
          'olive', sum(r['oliveBefore'] for r in report), '->', sum(r['oliveAfter'] for r in report))


if __name__ == '__main__':
    main()
