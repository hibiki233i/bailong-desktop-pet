"""Code-driven actions built from one still image.

Each frame is a single warp of the still: a smooth displacement field bends the
upper body around the neck, swings the outer hair, and squashes the figure on
its feet. The pixel mascot is a separate layer so it can lag behind the head.
All warps run on premultiplied alpha so edges stay clean.
"""
import math

import numpy as np
from PIL import Image
from scipy import ndimage

SIZE = 512
FPS = 24


def smooth(value):
    value = np.clip(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def premultiply(rgba):
    out = rgba.copy()
    out[..., :3] *= out[..., 3:4] / 255.0
    return out


def unpremultiply(rgba):
    out = rgba.copy()
    alpha = np.maximum(out[..., 3:4], 0.5)
    out[..., :3] = np.where(out[..., 3:4] > 0.5, out[..., :3] * 255.0 / alpha, 0.0)
    return out.clip(0, 255)


class Rig:
    """Pre-cut layers on one canvas, plus the few landmarks the warps need."""

    def __init__(self, faces, neck, feet_y, body_half, head_bottom, head_top, mascot=None):
        self.faces = {name: premultiply(layer) for name, layer in faces.items()}
        self.mascot = premultiply(mascot) if mascot is not None else None
        self.neck = neck
        self.feet_y = feet_y
        self.body_half = body_half
        self.head_bottom = head_bottom
        self.head_top = head_top
        self.ys, self.xs = np.mgrid[0:SIZE, 0:SIZE].astype(np.float64)

    def frame(self, tilt=0.0, sway=0.0, phase=0.0, stretch=0.0, lift=0.0, shift=0.0, face='open', mascot_lift=0.0, mascot_shift=0.0, local=()):
        """Render one pose. tilt is in degrees, stretch > 0 is taller, lift > 0 is up."""
        cx, cy = self.neck
        x = self.xs - shift
        y = self.ys + lift
        # Squash or stretch on the feet, keeping the volume roughly constant.
        y = self.feet_y + (y - self.feet_y) / (1.0 + stretch)
        x = cx + (x - cx) / (1.0 - 0.6 * stretch)
        # Bend: full rotation at the head, fading to none at the waist.
        waist = cy + 0.34 * (self.feet_y - cy)
        weight = smooth((waist - y) / max(1.0, waist - cy + 40.0))
        angle = -math.radians(tilt) * weight
        dx, dy = x - cx, y - cy
        rx = cx + dx * np.cos(angle) - dy * np.sin(angle)
        ry = cy + dx * np.sin(angle) + dy * np.cos(angle)
        # Hair swing: free ends move most, the centre of the body stays still.
        side = smooth((np.abs(rx - cx) - self.body_half) / 70.0)
        depth = smooth((ry - self.head_bottom) / max(1.0, self.feet_y - self.head_bottom))
        wave = np.sin(phase - (ry - self.head_bottom) * 0.012)
        rx = rx - sway * side * depth * wave
        # Local moves: ('shift', x, y, radius, dx, dy) or ('turn', px, py, x, y, radius, degrees).
        for kind, *values in local:
            if kind == 'shift':
                lx, ly, radius, mx, my = values
                weight = smooth(1.0 - np.hypot(rx - lx, ry - ly) / radius)
                rx, ry = rx - mx * weight, ry - my * weight
            else:
                px, py, lx, ly, radius, degrees = values
                weight = smooth(1.0 - np.hypot(rx - lx, ry - ly) / radius)
                turn = -math.radians(degrees) * weight
                ox, oy = rx - px, ry - py
                rx, ry = px + ox * np.cos(turn) - oy * np.sin(turn), py + ox * np.sin(turn) + oy * np.cos(turn)
        source = self.faces.get(face, self.faces['open'])
        out = np.dstack([ndimage.map_coordinates(source[..., i], (ry, rx), order=1, mode='constant') for i in range(4)])
        if self.mascot is not None:
            # The mascot follows the top of the head and adds its own lag.
            turn = math.radians(tilt)
            top_y = self.head_top
            follow_x = -math.sin(-turn) * (cy - top_y)
            follow_y = (1 - math.cos(turn)) * (cy - top_y)
            mx = shift + follow_x + mascot_shift
            my = -lift + follow_y - mascot_lift - stretch * (self.feet_y - top_y)
            layer = ndimage.shift(self.mascot, (my, mx, 0), order=1, mode='constant')
            out = layer + out * (1.0 - layer[..., 3:4] / 255.0)
        return unpremultiply(out)


def blink_face(t, period=3.2, start=1.6):
    """Open, half, closed, half, open: one quick blink per period."""
    local = (t - start) % period
    if local < 1 / FPS * 2:
        return 'half'
    if local < 1 / FPS * 5:
        return 'closed'
    if local < 1 / FPS * 7:
        return 'half'
    return 'open'


def action_idle(rig, seconds=4.0):
    frames = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        breath = math.sin(2 * math.pi * t / 2.0)
        frames.append(rig.frame(tilt=1.1 * math.sin(2 * math.pi * t / 4.0), sway=4.5, phase=2 * math.pi * t / 2.0,
                                stretch=0.009 * breath, face=blink_face(t),
                                mascot_lift=1.5 * max(0.0, math.sin(2 * math.pi * t / 2.0 - 0.8))))
    return frames


def action_hop(rig, seconds=2.0, hops=2):
    frames = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        u = (t / seconds * hops) % 1.0
        if u < 0.18:      # crouch before the jump
            k = u / 0.18
            lift, stretch = 0.0, -0.075 * math.sin(k * math.pi / 2)
        elif u < 0.72:    # airborne on a parabola, stretched at both ends
            k = (u - 0.18) / 0.54
            lift, stretch = 46 * 4 * k * (1 - k), 0.05 * abs(1 - 2 * k)
        else:             # landing squash that settles back
            k = (u - 0.72) / 0.28
            lift, stretch = 0.0, -0.08 * math.exp(-4 * k) * math.cos(k * 7)
        late = (u - 0.1) % 1.0
        frames.append(rig.frame(sway=9, phase=u * 2 * math.pi, stretch=stretch, lift=lift, face='happy',
                                tilt=3.5 * math.sin(2 * math.pi * t / seconds * hops),
                                mascot_lift=12 * max(0.0, math.sin(late * math.pi * 1.6))))
    return frames


def action_think(rig, seconds=4.0):
    frames = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        lean = smooth(np.array(min(1.0, t / 0.6))) * smooth(np.array(min(1.0, (seconds - t) / 0.6)))
        frames.append(rig.frame(tilt=float(lean) * (7.0 + 1.2 * math.sin(2 * math.pi * t / 1.6)), sway=4, phase=2 * math.pi * t / 2.0,
                                stretch=0.007 * math.sin(2 * math.pi * t / 2.0), face=blink_face(t, 2.6, 1.2)))
    return frames


def action_sleep(rig, seconds=5.0):
    frames = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        breath = math.sin(2 * math.pi * t / 2.5)
        frames.append(rig.frame(tilt=5.0 + 3.0 * breath, sway=2.5, phase=2 * math.pi * t / 2.5, stretch=0.014 * breath,
                                face='closed', mascot_lift=1.0 + breath))
    return frames


def action_walk(rig, seconds=2.0, steps=4):
    """Paper-doll walk: hop and rock in place; the app moves the window."""
    frames = []
    for i in range(int(seconds * FPS)):
        t = i / FPS
        u = t / seconds * steps
        bounce = abs(math.sin(math.pi * u))
        frames.append(rig.frame(tilt=4.0 * math.sin(math.pi * u), sway=8, phase=math.pi * u * 2, stretch=0.022 * (bounce - 0.5), lift=11 * bounce,
                                face=blink_face(t, 1.9, 0.8), mascot_lift=7 * abs(math.sin(math.pi * u - 0.6))))
    return frames


def bleed_edges(frame):
    """Copy the nearest solid colour into empty pixels.

    WebP stores colour at reduced resolution. If empty pixels stay black, that
    neutral colour mixes into the brown outline and turns it olive.
    """
    solid = frame[..., 3] > 200
    rows, columns = ndimage.distance_transform_edt(~solid, return_distances=False, return_indices=True)
    out = frame.copy()
    empty = frame[..., 3] < 8
    out[empty, :3] = frame[rows[empty], columns[empty], :3]
    return out


def save_webp(frames, path):
    images = [Image.fromarray(np.clip(bleed_edges(f) + 0.5, 0, 255).astype(np.uint8), 'RGBA') for f in frames]
    images[0].save(path, save_all=True, append_images=images[1:], duration=round(1000 / FPS), loop=0,
                   quality=88, method=4, exact=True)
    return images


def contact(frames, path, columns=8, cell=170, background=(226, 228, 235)):
    picks = [frames[round(i * (len(frames) - 1) / (columns - 1))] for i in range(columns)]
    sheet = Image.new('RGB', (cell * columns, cell), background)
    for index, frame in enumerate(picks):
        image = Image.fromarray(np.clip(frame + 0.5, 0, 255).astype(np.uint8), 'RGBA').resize((cell, cell), Image.LANCZOS)
        sheet.paste(image, (index * cell, 0), image)
    sheet.save(path)
