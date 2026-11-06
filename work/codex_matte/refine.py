"""Clean the matte of the bundled Codex character clips.

The source alpha is a blurred blob that sits up to eight pixels outside the
drawing, so an opaque olive band of green-screen colour surrounds the dark
outline and fills the pockets between hair strands. Floor shadows also survive
as faint dark patches.

The character is enclosed by a dark indigo outline, so everything outside that
line is background. Removal grows inwards from the transparent area and from
olive pockets, and stops at the line. Effects drawn without a line, such as
confetti and flames, are protected because the flood only runs close to it.
"""
import numpy as np
from scipy import ndimage

SOLID = 235
BAND = 9
SHADOW_START = 0.72
MIN_POCKET = 10
MIN_PIECE = 40
EIGHT = np.ones((3, 3))


def classify(rgb, alpha):
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    top, low = rgb.max(axis=2), rgb.min(axis=2)
    saturation = (top - low) / np.maximum(top, 1.0)
    line = (top < 135) & (blue >= green - 2) & (alpha >= 170)
    # Compression breaks the line where it meets the band, and the flood would leak through a gap.
    outline = ndimage.binary_closing(line, structure=EIGHT, iterations=2) | (ndimage.binary_dilation(line) & (top < 105))
    # Olive has green level with red and above blue. Gold and skin have red well above green,
    # and the lavender art has blue above green. Bright warm whites are highlights, not olive.
    olive = (green - blue >= 2) & (green >= red - 11) & (top < 190) & (alpha > 0) & ~outline
    return outline, olive, saturation, top


def pockets(olive, outline, alpha, rgb):
    """Opaque olive areas enclosed by the line, such as the gaps between hair strands."""
    red, green, blue = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    labels, count = ndimage.label(olive & (alpha >= SOLID) & (np.abs(red - green) <= 12) & (green - blue >= 10), structure=EIGHT)
    found = np.zeros(alpha.shape, bool)
    for index, area in enumerate(ndimage.find_objects(labels), start=1):
        window = (slice(max(0, area[0].start - 3), area[0].stop + 3), slice(max(0, area[1].start - 3), area[1].stop + 3))
        piece = labels[window] == index
        if piece.sum() < MIN_POCKET:
            continue
        ring = ndimage.binary_dilation(piece, iterations=2) & ~piece
        # A real gap touches the line all round; olive shading inside gold touches gold.
        if (outline[window] | olive[window])[ring].mean() >= 0.6:
            found[window] |= piece
    return found


def background(rgb, alpha):
    """Mask of everything that belongs to the green screen or the floor."""
    outline, olive, saturation, top = classify(rgb, alpha)
    near_line = ndimage.binary_dilation(outline, iterations=BAND)
    height = alpha.shape[0]
    floor = (np.arange(height) >= height * SHADOW_START)[:, None]
    shadow = floor & (alpha < SOLID) & ((saturation < 0.24) | (top < 60)) & ~outline
    soft = (alpha < SOLID) & near_line & ~outline
    empty = alpha < 8
    seeds = empty | pockets(olive, outline, alpha, rgb)
    return ndimage.binary_propagation(seeds, mask=seeds | olive | shadow | soft)


def drop_specks(alpha):
    """Remove small loose pieces with no solid core; confetti and stars keep theirs."""
    labels, count = ndimage.label(alpha > 24, structure=EIGHT)
    if not count:
        return alpha
    index = np.arange(1, count + 1)
    sizes = ndimage.sum(np.ones_like(alpha), labels, index=index)
    peaks = ndimage.maximum(alpha, labels, index=index)
    # Thin wisps are what is left of a removed band: nothing survives one erosion.
    cores = ndimage.maximum(ndimage.binary_erosion(alpha > 24, iterations=2).astype(np.float64), labels, index=index)
    loose = index[(sizes < MIN_PIECE) | (peaks < 140) | ((cores == 0) & (sizes < 400))]
    return np.where(np.isin(labels, loose), 0.0, alpha)


def fill_pinholes(alpha):
    """Compression leaves small see-through dots inside the body."""
    solid = alpha >= 200
    holes = ndimage.binary_fill_holes(solid) & ~solid
    labels, count = ndimage.label(holes)
    if not count:
        return alpha
    sizes = ndimage.sum(np.ones_like(alpha), labels, index=np.arange(1, count + 1))
    return np.where(np.isin(labels, np.flatnonzero(sizes < 40) + 1), 255.0, alpha)


def refine(frame):
    """Take straight-alpha RGBA uint8 and return straight-alpha float RGBA with clean edges."""
    rgb = frame[..., :3].astype(np.float64)
    alpha = fill_pinholes(frame[..., 3].astype(np.float64))
    outline, olive, _, top = classify(rgb, alpha)
    outside = background(rgb, alpha)
    kept = drop_specks(np.where(outside, 0.0, alpha))

    # Cutting the band leaves a stepped edge. Blurring the mask and re-thresholding it
    # gives a smooth antialiased curve, and only near the cut so effects keep their alpha.
    removed = outside & (alpha >= 8)
    cut = ndimage.binary_dilation(removed, iterations=2)
    smooth = ndimage.gaussian_filter((kept > 8).astype(np.float64), 1.0)
    kept = np.where(cut, np.clip((smooth - 0.36) / 0.30, 0.0, 1.0) * 255.0, kept)

    # The new edge is the outline, so colour it from the line itself, not from the band.
    ink = outline & (top < 125) & (rgb[..., 2] >= rgb[..., 1])
    if not ink.any():
        return np.dstack((rgb, kept))
    distance, (rows, columns) = ndimage.distance_transform_edt(~ink, return_indices=True)
    stained = ndimage.binary_dilation(removed, iterations=3) & (outside | olive | (kept < SOLID)) & ~ink & (distance <= 6)
    return np.dstack((np.where(stained[..., None], rgb[rows, columns], rgb), kept))
