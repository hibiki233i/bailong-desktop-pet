"""Build every action into out/, in the format the pet's load() reads."""
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import numpy as np
from PIL import Image

from actions import ACTIONS, drag, landing, pop, walk, walk_drawn
from motion import contact, save_webp
from rig_sheet import build, build_walk

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / 'out'
PREVIEW = ROOT / 'preview'
OUT.mkdir(exist_ok=True)
PREVIEW.mkdir(exist_ok=True)

rigs = build(ROOT / 'raw/poses.png')
start = time.monotonic()
for rig_name, (name, action) in ACTIONS.items():
    frames = action(rigs[rig_name])
    save_webp(frames, OUT / f'{name}.webp')
    contact(frames, PREVIEW / f'{name}.png')
    print(name, len(frames), 'frames', (OUT / f'{name}.webp').stat().st_size // 1024, 'KiB', flush=True)
frames = walk(rigs['stand'])
save_webp(frames, OUT / 'walk_code.webp')
contact(frames, PREVIEW / 'walk_code.png')
walk_rigs, gain = build_walk(ROOT / 'raw/walk.png', ROOT / 'raw/poses.png')
print('walk colour gain', gain.round(3))
frames = walk_drawn(walk_rigs)
save_webp(frames, OUT / 'walk.webp')
contact(frames, PREVIEW / 'walk.png')
print('walk', len(frames), 'frames', (OUT / 'walk.webp').stat().st_size // 1024, 'KiB', flush=True)
for name, frames in (('drag', drag(rigs['ask'])), ('landing', landing(rigs['stand']))):
    save_webp(frames, OUT / f'{name}.webp')
    print(name, len(frames), 'frames', flush=True)
reel = []
order = ['stand', 'work', 'ask', 'cheer', 'sleep']
for current, following in zip(order, order[1:] + order[:1]):
    name, action = ACTIONS[current]
    clip = action(rigs[current])
    reel += clip[:60] + pop(rigs[current], rigs[following])
save_webp(reel, OUT / 'reel.webp')
print('reel', len(reel), 'frames', (OUT / 'reel.webp').stat().st_size // 1024, 'KiB')
print('seconds', round(time.monotonic() - start))
