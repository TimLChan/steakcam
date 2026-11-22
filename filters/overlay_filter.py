"""Remove the CCTV date/time overlay from clock crops.

The camera burns a neutral white timestamp into the frame which can sit on top
of the red LED timer. The LED digits' bright cores are pink (R well above G),
while the overlay is near-neutral white (R ~= G), so the overlay can be picked
out by colour and inpainted from its surroundings - red where it crosses a
digit segment, dark where it sits on the background.
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image

from filters import dilation

# All channels above this value counts as "bright".
OVERLAY_MIN_CHANNEL = 170
# Bright pixels with R-G below this are neutral white (overlay); above it they
# are the pink cores of the LED digits.
OVERLAY_MAX_RG_DIFF = 30
# Extra pixels around the detected overlay to catch JPEG fringing.
MASK_GROW_ITERATIONS = 1
INPAINT_RADIUS = 3
# Bright pink LED cores (left behind by dilation.replace_with_white, which only
# whitens the darker red glow) are whitened so digits come out solid.
CORE_MIN_RED = 245
CORE_MIN_BLUE = 210
# Passes of "second darkest in 3x3" thinning (same operation as
# dilation.apply_filter) run on the whitened digits.
THIN_ITERATIONS = 1


def overlay_mask(img_array: np.ndarray) -> np.ndarray:
    """Return a uint8 mask (255 = overlay) for an RGB image array."""
    c = img_array.astype(np.int16)
    r, g = c[..., 0], c[..., 1]
    mask = (c.min(axis=2) > OVERLAY_MIN_CHANNEL) & ((r - g) < OVERLAY_MAX_RG_DIFF)
    mask = mask.astype(np.uint8) * 255
    if MASK_GROW_ITERATIONS:
        mask = cv2.dilate(mask, np.ones((3, 3), np.uint8), iterations=MASK_GROW_ITERATIONS)
    return mask


def thin(img_array: np.ndarray, iterations: int = 1) -> np.ndarray:
    """Vectorised version of dilation.apply_filter.

    Each pixel takes the colour of the second darkest (by luminosity) pixel in
    its 3x3 neighbourhood, which shaves a pixel off the edge of bright strokes.
    Out-of-bounds neighbours are padded with infinite luminosity so they are
    never picked, matching dilation.py's clipped neighbourhoods at the edges.
    """
    result = img_array
    h, w = img_array.shape[:2]
    for _ in range(iterations):
        lum = result @ np.array([0.299, 0.587, 0.114])
        lum_p = np.pad(lum, 1, constant_values=np.inf)
        pix_p = np.pad(result, ((1, 1), (1, 1), (0, 0)), mode="edge")
        offsets = [(dy, dx) for dy in range(3) for dx in range(3)]
        lum_stack = np.stack([lum_p[dy:dy + h, dx:dx + w] for dy, dx in offsets])
        pix_stack = np.stack([pix_p[dy:dy + h, dx:dx + w] for dy, dx in offsets])
        second = np.argsort(lum_stack, axis=0, kind="stable")[1]
        result = np.take_along_axis(pix_stack, second[None, ..., None], axis=0)[0]
    return result


def apply_filter(image_path, output_path=None):
    """Remove the white CCTV overlay from an image by inpainting over it.

    Args:
        image_path: Path to the input image
        output_path: Path to save the output image (optional)

    Returns:
        The filtered PIL Image object
    """
    img_array = np.array(Image.open(image_path).convert("RGB"))
    mask = overlay_mask(img_array)
    result_array = cv2.inpaint(img_array, mask, INPAINT_RADIUS, cv2.INPAINT_TELEA)

    result_img = Image.fromarray(result_array)
    if output_path:
        result_img.save(output_path)
    return result_img


def replace_with_white(image_path, output_path=None, **kwargs):
    """Whiten the red digit glow (via dilation.replace_with_white) and the pink
    digit cores, then thin the strokes slightly.

    Extra keyword arguments are passed through to ``dilation.replace_with_white``.
    """
    img_array = np.array(dilation.replace_with_white(image_path, **kwargs))
    c = img_array.astype(np.int16)
    core = (c[..., 0] > CORE_MIN_RED) & (c[..., 2] > CORE_MIN_BLUE)
    img_array[core] = [255, 255, 255]
    if THIN_ITERATIONS:
        img_array = thin(img_array, THIN_ITERATIONS)

    result_img = Image.fromarray(img_array)
    if output_path:
        result_img.save(output_path)
    return result_img


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m filters.overlay_filter <input_image_path> [output_image_path]")
        return

    input_path = sys.argv[1]
    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        name, ext = os.path.splitext(input_path)
        output_path = f"{name}_overlay{ext}"

    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' not found.")
        return

    apply_filter(input_path, output_path)
    print(f"Overlay removed: '{input_path}' -> '{output_path}'")


if __name__ == "__main__":
    main()
