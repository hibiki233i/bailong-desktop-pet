"""Render every Claude clip into outputs/Claude桌宠素材 with its manifest.

Usage: python3 work/claude_assets/build_clips.py [--only idle,18] [--jobs 6]
"""
import argparse
import json
import multiprocessing
import pathlib
import sys
import time

import numpy as np
from PIL import Image

sys.path.insert(0, str(pathlib.Path(__file__).parent))
from clips import POSES, drawn_cycle, floating
from motion import FPS, contact, save_webp
from rig_poses import SHEETS, build_sheet, strip_rigs
from rig_sheet import build_walk

ROOT = pathlib.Path(__file__).resolve().parents[2]
TARGET = ROOT / 'outputs/Claude桌宠素材'
SOURCE = ROOT / 'outputs/Claude素材源'
PREVIEW = SOURCE / 'preview'
MOVES = [
    ('move01right', 'walk', 'right', '01', '走路（向右）', 4.0),
    ('move01left', 'walk', 'left', '01', '走路（向左）', 4.0),
    ('move02', 'run', 'right', '02', '跑步（向右）', 3.0),
    ('move02left', 'run', 'left', '02', '跑步（向左）', 3.0),
    ('move03right', 'float', 'right', '03', '飘行（向右）', 5.0),
    ('move03left', 'float', 'left', '03', '飘行（向左）', 5.0),
]
RIGS = {}


def sheet_of(pose):
    return next(name for name, poses in SHEETS.items() if pose in poses)


def rig(pose):
    sheet = sheet_of(pose)
    if sheet not in RIGS:
        RIGS[sheet] = build_sheet(sheet)
    return RIGS[sheet][pose]


def strip(name):
    if name not in RIGS:
        RIGS[name] = build_walk(SOURCE / 'raw/walk.png', SOURCE / 'raw/poses.png')[0] if name == 'walk' else strip_rigs(name, lifts=name != 'float')
    return RIGS[name]


def move_frames(kind, facing, seconds):
    if kind == 'walk':
        frames = drawn_cycle(strip('walk'), seconds, hold=5, bob=5)
    elif kind == 'run':
        frames = drawn_cycle(strip('run'), seconds, hold=3, bob=12, sway=9, mascot=8)
    else:
        frames = floating(strip('float'), seconds)
    return [np.ascontiguousarray(frame[:, ::-1]) for frame in frames] if facing == 'left' else frames


def render(job):
    started = time.monotonic()
    name, frames = job[0], None
    if job[1] == 'pose':
        frames = job[3](rig(job[2]))
    else:
        frames = move_frames(*job[2:])
    save_webp(frames, TARGET / f'{name}.webp')
    contact(frames, PREVIEW / f'{name}.png')
    print(f'{name:12s} {len(frames):4d} frames {(TARGET / f"{name}.webp").stat().st_size >> 10:6d} KiB {time.monotonic() - started:.0f}s', flush=True)


def clip(identity, frames, **extra):
    return {'id': identity, 'file': f'{identity}.webp', 'durationMs': round(frames * 1000 / FPS), 'renderScale': 1.0, 'renderOffset': [0.0, 0.0], **extra}


def manifest(counts):
    data = {'version': 1, 'character': 'claude', 'additionalIdleAnimations': [], 'variants': [], 'workAnimations': [], 'movementAnimations': []}
    for name, _, _, slot, title, line in POSES:
        item = clip(name, counts[name], name=title)
        if line:
            item['line'] = line
        if slot == 'idles':
            data['additionalIdleAnimations'].append(item)
        elif slot == 'variants':
            data['variants'].append(item)
        elif slot == 'work':
            data['workAnimations'].append(item)
        else:
            data[slot] = item
    data['idle']['loop'] = True
    for name, kind, facing, number, title, _ in MOVES:
        item = clip(name, counts[name], number=number, name=title, sourceFacing=facing)
        item.update(moveStartMs=0, moveStopMs=item['durationMs'])
        if kind == 'float':
            item.update(movementAngleRange=[45, 80], movementSpeed=0.65)
        data['movementAnimations'].append(item)
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--only', default='')
    parser.add_argument('--jobs', type=int, default=6)
    options = parser.parse_args()
    only = set(filter(None, options.only.split(',')))
    TARGET.mkdir(parents=True, exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    jobs = [(name, 'pose', pose, motion) for name, pose, motion, *_ in POSES] + [(name, 'move', kind, facing, seconds) for name, kind, facing, _, _, seconds in MOVES]
    selected = [job for job in jobs if not only or job[0] in only]
    with multiprocessing.get_context('fork').Pool(options.jobs) as pool:
        pool.map(render, selected, chunksize=1)
    # Count from the files, so rebuilding a few clips still leaves a complete manifest.
    counts = {}
    for path in TARGET.glob('*.webp'):
        with Image.open(path) as source:
            counts[path.stem] = source.n_frames
    (TARGET / '素材清单.json').write_text(json.dumps(manifest(counts), ensure_ascii=False, indent=1), encoding='utf-8')
    print('clips', len(counts), 'MiB', sum(path.stat().st_size for path in TARGET.glob('*.webp')) >> 20)


if __name__ == '__main__':
    main()
