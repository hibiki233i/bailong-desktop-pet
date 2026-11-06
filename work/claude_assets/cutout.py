"""Chroma-key cutout, sheet slicing and canvas fitting.

The green share of each edge pixel sets its transparency, while its colour comes
from the nearest solid pixel. That keeps edges soft without an olive halo.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

KEY_LOW, KEY_HIGH = 22.0, 190.0


def key_out(image):
    """Return float RGBA (0-255) with the green background removed."""
    rgb = np.asarray(image.convert('RGB')).astype(np.float64)
    excess = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    alpha = 1.0 - np.clip((excess - KEY_LOW) / (KEY_HIGH - KEY_LOW), 0.0, 1.0)

    # An edge pixel's own colour is unreliable: un-mixing it leaves R close to G,
    # which reads as an olive halo. Take the colour of the nearest solid pixel.
    # The outermost "opaque" pixels are tinted too, so sample two pixels further in.
    solid = ndimage.binary_erosion(alpha > 0.97, iterations=2)
    rows, columns = ndimage.distance_transform_edt(~solid, return_distances=False, return_indices=True)
    figure = rgb[rows, columns]
    figure = np.where(solid[..., None], rgb, figure)

    # Compression noise leaves isolated specks in the green area.
    labels, count = ndimage.label(alpha > 0.15)
    if count:
        sizes = ndimage.sum(np.ones_like(alpha), labels, index=np.arange(1, count + 1))
        tiny = np.isin(labels, np.flatnonzero(sizes < 40) + 1)
        alpha = np.where(tiny, 0.0, alpha)
    return np.dstack((figure, alpha * 255.0))


def to_image(rgba):
    return Image.fromarray(np.clip(rgba + 0.5, 0, 255).astype(np.uint8), 'RGBA')


def split_figures(rgba, grow=9, min_share=0.02):
    """Slice a sheet into figures, ordered row by row, with their bounding boxes."""
    solid = rgba[..., 3] > 40
    labels, count = ndimage.label(ndimage.binary_dilation(solid, iterations=grow))
    boxes = []
    for index, area in enumerate(ndimage.find_objects(labels), start=1):
        mask = (labels[area] == index) & solid[area]
        if mask.sum() >= solid.sum() * min_share:
            ys, xs = np.nonzero(mask)
            boxes.append((area[1].start + xs.min(), area[0].start + ys.min(),
                          area[1].start + xs.max() + 1, area[0].start + ys.max() + 1, index))
    if not boxes:
        return []
    height = np.median([b[3] - b[1] for b in boxes])
    boxes.sort(key=lambda b: (round(((b[1] + b[3]) / 2) / height), b[0]))
    figures = []
    for left, top, right, bottom, index in boxes:
        crop = rgba[top:bottom, left:right].copy()
        crop[..., 3] = np.where(labels[top:bottom, left:right] == index, crop[..., 3], 0)
        figures.append(((left, top, right, bottom), crop))
    return figures


def place_on_canvas(crop, scale, size=512, foot=480):
    """Scale a crop with premultiplied alpha and stand it on the baseline."""
    height, width = crop.shape[:2]
    target = (max(1, round(width * scale)), max(1, round(height * scale)))
    premultiplied = crop.copy()
    premultiplied[..., :3] *= premultiplied[..., 3:4] / 255.0
    channels = [np.asarray(Image.fromarray(premultiplied[..., i].astype(np.float32), 'F')
                           .resize(target, Image.LANCZOS)) for i in range(4)]
    small = np.dstack(channels).clip(0, 255)
    small[..., :3] = np.where(small[..., 3:4] > 0.5, small[..., :3] * 255.0 / np.maximum(small[..., 3:4], 0.5), 0)
    canvas = np.zeros((size, size, 4))
    left = (size - target[0]) // 2
    top = foot - target[1]
    y0, x0 = max(0, top), max(0, left)
    y1, x1 = min(size, top + target[1]), min(size, left + target[0])
    canvas[y0:y1, x0:x1] = small[y0 - top:y1 - top, x0 - left:x1 - left]
    return canvas, left, top


def fit_canvas(rgba, size=512, scale=None, foot=480, top_margin=26, side_margin=22):
    """Place a figure on a square canvas with its feet on a fixed baseline."""
    ys, xs = np.nonzero(rgba[..., 3] > 8)
    crop = rgba[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    height, width = crop.shape[:2]
    if scale is None:
        scale = min((foot - top_margin) / height, (size - 2 * side_margin) / width)
    return place_on_canvas(crop, scale, size, foot)[0], scale
