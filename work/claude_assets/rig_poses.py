"""Build one animation rig per pose from the generated character sheets.

Every sheet holds six figures drawn together, so they agree on proportions and
colour. All coordinates are pixels in the sheet.
"""
import pathlib

import numpy as np
from PIL import Image
from scipy import ndimage

from cutout import key_out, place_on_canvas, split_figures
from motion import Rig
from rig_sheet import EYES as MEASURED, FOOT, SIZE, TOP, eye_faces, match_colour, split_mascot

RAW = pathlib.Path(__file__).resolve().parents[2] / 'outputs/Claude素材源/raw'
RADIUS = {'props': (31, 33), 'moods': (31, 33), 'gifts': (23, 25), 'tasks': (23, 25)}
EYES = {'book': ((190, 243), (292, 238)), 'game': ((1213, 243), (1298, 238)), 'cookie': ((705, 672), (793, 672)), 'wave': ((1213, 672), (1297, 672)),
        'idea': ((207, 195), (297, 195)), 'heart': ((197, 195), (279, 195)), 'sunflower': ((707, 192), (790, 190)), 'box': ((197, 702), (279, 702)),
        'salute': ((230, 182), (302, 180)), 'folders': ((727, 182), (800, 182)), 'docs': ((1225, 185), (1295, 185)), 'clipboard': ((730, 698), (800, 698))}

# name: (neck x, neck y, unused, figure stands, mascot lifts off)
SHEETS = {
    'poses': {'work': (262, 295, True, False, True), 'cheer': (748, 232, False, False, True), 'think': (1248, 262, True, True, True),
              'ask': (262, 775, True, True, True), 'sleep': (775, 810, False, False, True), 'stand': (1265, 770, True, True, True)},
    'props': {'book': (250, 295, True, False, True), 'pillow': (760, 285, False, False, True), 'game': (1270, 290, True, False, True),
              'pat': (258, 735, False, True, False), 'cookie': (760, 745, True, True, True), 'wave': (1270, 745, True, True, True)},
    'moods': {'idea': (255, 255, True, True, True), 'proud': (770, 255, False, True, True), 'hug': (1280, 250, False, True, True),
              'tsundere': (250, 755, True, True, True), 'angry': (770, 755, True, True, True), 'yawn': (1280, 760, False, True, True)},
    'gifts': {'heart': (245, 235, True, True, True), 'sunflower': (755, 235, True, True, True), 'bask': (1290, 225, False, True, True),
              'box': (245, 745, True, True, True), 'pinwheel': (755, 745, True, True, True), 'shy': (1265, 745, True, True, True)},
    'tasks': {'salute': (262, 232, True, True, True), 'folders': (765, 232, True, True, True), 'docs': (1265, 232, True, True, True),
              'glass': (245, 745, True, True, True), 'clipboard': (770, 745, True, True, True), 'dangle': (1265, 715, True, False, True)},
}


def eye_spec(sheet, pose, box):
    """Eye ellipses as lid outlines in crop coordinates. Poses without an entry do not blink."""
    if pose not in EYES:
        return None
    rx, ry = RADIUS[sheet]
    polys, arcs = [], []
    for x, y in EYES[pose]:
        cx, cy = x - box[0], y - box[1]
        polys.append([(cx + rx * np.cos(t), cy + ry * np.sin(t)) for t in np.linspace(0, 2 * np.pi, 18, endpoint=False)])
        arcs.append(((cx - rx - 1, cy + 6), (cx + rx + 1, cy + 6)))
    return {'polys': polys, 'arcs': arcs}


def matched(name):
    """Cut a sheet out and match its hair to the first sheet, so clips do not change colour."""
    cut = key_out(Image.open(RAW / f'{name}.png'))
    if name != 'poses':
        gain = match_colour(cut, key_out(Image.open(RAW / 'poses.png')))
        print(name, 'hair gain', gain.round(3), flush=True)
    return cut


def strip_rigs(name, lifts=True, mascot_width=107.0):
    """Rigs for a drawn strip, scaled so the mascot matches the pose sheets.

    With lifts off the mascot stays in the drawing: the float pose has a huge
    flower head at the top, whose brown centre would be mistaken for the mascot.
    """
    figures = split_figures(matched(name))
    fit = min((FOOT - 16) / max(box[3] - box[1] for box, _ in figures), (SIZE - 10) / max(box[2] - box[0] for box, _ in figures))
    parts = [split_mascot(crop) if lifts else (crop, None, 0.0) for _, crop in figures]
    scale = min(fit, mascot_width / np.median([np.ptp(np.nonzero(part[1][..., 3] > 128)[1]) for part in parts])) if lifts else fit
    rigs = []
    for (box, crop), (base, mascot, head_top) in zip(figures, parts):
        face, left, top = place_on_canvas(base, scale, SIZE, FOOT)
        layer = place_on_canvas(mascot, scale, SIZE, FOOT)[0] if mascot is not None else None
        height, width = crop.shape[:2]
        neck = (0.62 * width * scale + left, 0.55 * height * scale + top)
        rigs.append(Rig({'open': face}, neck=neck, feet_y=FOOT, body_half=60, head_bottom=neck[1], head_top=head_top * scale + top, mascot=layer))
    return rigs


def build_sheet(name):
    spec = SHEETS[name]
    figures = dict(zip(spec, split_figures(matched(name))))
    if len(figures) != len(spec):
        raise RuntimeError(f'{name}: found {len(figures)} figures')
    tallest = max(box[3] - box[1] for pose, (box, _) in figures.items() if spec[pose][3])
    scale = (FOOT - TOP) / tallest
    rigs = {}
    for pose, (box, crop) in figures.items():
        nx, ny, _, _, lifts = spec[pose]
        base, mascot, head_top = split_mascot(crop) if lifts else (crop, None, 0.0)
        faces = {'open': base}
        eyes = eye_spec(name, pose, box) if name != 'poses' else None
        if name == 'poses' and pose in MEASURED:
            eyes = {'polys': [[(x - box[0], y - box[1]) for x, y in poly] for poly in MEASURED[pose]['polys']],
                    'arcs': [((a[0] - box[0], a[1] - box[1]), (b[0] - box[0], b[1] - box[1])) for a, b in MEASURED[pose]['arcs']]}
        if eyes:
            faces.update(eye_faces(base, eyes, (0, 0)))
        placed = {key: place_on_canvas(value, scale, SIZE, FOOT)[0] for key, value in faces.items()}
        _, left, top = place_on_canvas(base, scale, SIZE, FOOT)
        layer = place_on_canvas(mascot, scale, SIZE, FOOT)[0] if mascot is not None else None

        def to_canvas(x, y, box=box, left=left, top=top):
            return (x - box[0]) * scale + left, (y - box[1]) * scale + top

        neck = to_canvas(nx, ny)
        rig = Rig(placed, neck=neck, feet_y=FOOT, body_half=74, head_bottom=neck[1], head_top=head_top * scale + top, mascot=layer)
        rig.at = to_canvas
        rig.scale = scale
        rig.blinks = 'half' in placed
        rigs[pose] = rig
    return rigs
