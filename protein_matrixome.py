#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Matrix Protein Rain
===================
Generates a "Matrix digital rain" animation where falling characters
(letters, numbers, symbols) trace the silhouette of a protein from a PyMOL
render (green protein on black background).

Outputs:
  1. matrix_protein.gif  → animated GIF (digital rain effect)
  2. matrix_protein.png   → static frame (best coverage)
  3. matrix_protein.txt    → plain-text matrix of characters

Author: Jesus Seco, PhD
Year:   2026 (October)
"""

import sys
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont

# Configuration: characters and colors
# Character pool used for the digital rain (ASCII letters, digits, symbols)
# ──────────────────────────────────────────────────────────────────────────────
MATRIX_CHARS = (
    "0123456789"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "abcdefghijklmnopqrstuvwxyz"
    "@#$%&*+=<>?/|\\:;~^!"
    "{}[]()_-"
)

# Color palette — bright green at the stream head, fading to dark green tail
GREEN_BRIGHT = (220, 255, 220)
GREEN_HEAD   = (150, 255, 150)
GREEN_MID    = (0, 255, 70)
GREEN_DIM    = (0, 180, 50)
GREEN_DARK   = (0, 120, 35)
GREEN_DARKER = (0, 70, 20)
BLACK        = (0, 0, 0)



# Image loading and protein detection
# ────────────────────────────────────

def load_and_detect(path, threshold=20):
    """Load image and detect the green-protein mask against black background.

    A pixel is considered part of the protein when the green channel
    dominates over red and blue by at least ``threshold`` units, and the
    green value itself is above ``threshold`` (to reject near-black noise).
    """
    img = Image.open(path).convert("RGB")
    rgb = np.array(img)
    r, g, b = rgb[:, :, 0], rgb[:, :, 1], rgb[:, :, 2]
    mask = (g > r + threshold) & (g > b + threshold) & (g > threshold)
    return mask.astype(np.uint8), rgb


def crop_to_protein(mask, rgb, padding=12):
    """Crop image and mask to the bounding box of the protein (zoom in).

    ``padding`` is a percentage of the protein dimensions added as margin
    around the bounding box so the structure is not flush with the edges.
    """
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if not rows.any():
        return mask, rgb

    rmin, rmax = np.where(rows)[0][[0, -1]]
    cmin, cmax = np.where(cols)[0][[0, -1]]

    ph = int((rmax - rmin) * padding / 100)
    pw = int((cmax - cmin) * padding / 100)
    rmin = max(0, rmin - ph)
    rmax = min(mask.shape[0], rmax + ph)
    cmin = max(0, cmin - pw)
    cmax = min(mask.shape[1], cmax + pw)

    return mask[rmin:rmax, cmin:cmax], rgb[rmin:rmax, cmin:cmax]


def downsample_mask(mask, block_size):
    """Downsample the binary mask by grouping pixels into blocks.

    Each block is averaged; if more than 30% of its pixels are protein,
    the block is marked as protein (1), otherwise background (0).
    """
    h, w = mask.shape
    nh, nw = h // block_size, w // block_size
    cropped = mask[: nh * block_size, : nw * block_size]
    reshaped = cropped.reshape(nh, block_size, nw, block_size)
    return (reshaped.mean(axis=(1, 3)) > 0.3).astype(np.uint8)


def get_font(size):
    """Load a monospaced TrueType font; fall back to PIL default."""
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        try:
            return ImageFont.truetype(fp, size)
        except Exception:
            continue
    return ImageFont.load_default()


# Matrix rain engine
# ───────────────────

class MatrixRain:
    """Digital-rain engine that respects a protein mask.

    Each column that contains protein pixels gets one or more streams.
    Streams fall slowly and characters persist with a decaying brightness
    so the secondary structure (helices, loops) remains visible.
    """

    def __init__(self, mask, char_size=16, density=3.0, fade_rate=0.92):
        self.mask = mask
        self.rows, self.cols = mask.shape
        self.char_size = char_size
        self.img_w = self.cols * char_size
        self.img_h = self.rows * char_size
        self.font = get_font(char_size + 2)
        self.fade_rate = fade_rate  # higher = characters persist longer

        # Character grid: current glyph per cell (persistent, not cleared each frame)
        self.char_grid = [
            [random.choice(MATRIX_CHARS) for _ in range(self.cols)]
            for _ in range(self.rows)
        ]
        # Brightness buffer: float per cell, decays each frame
        self.brightness = np.zeros((self.rows, self.cols), dtype=np.float32)

        # Create streams for columns that contain protein
        self.streams = []
        for c in range(self.cols):
            if not mask[:, c].any():
                self.streams.append(None)
                continue

            # Multiple streams per column for higher density
            num_streams = max(1, int(density * 2))
            col_streams = []
            for _ in range(num_streams):
                col_streams.append({
                    "y": random.uniform(-self.rows * 0.3, self.rows * 0.9),
                    "length": random.randint(12, 35),
                    "speed": random.uniform(0.15, 0.5),  # slow fall
                    "chars": [random.choice(MATRIX_CHARS) for _ in range(50)],
                })
            self.streams.append(col_streams)

    # ── Core step: advance one frame ───────────────────────────────────────
    def step(self):
        """Advance one animation frame.

        1. Decay all existing brightness (slow fade → structure stays visible).
        2. Move each stream downward and write bright characters into cells
           that belong to the protein mask.
        """
        # 1 — Fade existing brightness (persists structure between frames)
        self.brightness *= self.fade_rate

        # 2 — Advance streams
        for col, col_streams in enumerate(self.streams):
            if col_streams is None:
                continue

            for stream in col_streams:
                stream["y"] += stream["speed"]

                # Reset stream when it has fully exited the bottom
                if stream["y"] - stream["length"] > self.rows:
                    stream["y"] = random.uniform(-15, -2)
                    stream["length"] = random.randint(12, 35)
                    stream["speed"] = random.uniform(0.15, 0.5)
                    stream["chars"] = [random.choice(MATRIX_CHARS) for _ in range(50)]

                head_y = int(stream["y"])
                length = stream["length"]

                # Write the stream's character trail into the grid
                for i in range(length):
                    y = head_y - i
                    if not (0 <= y < self.rows):
                        continue
                    if not self.mask[y, col]:
                        continue

                    # Occasionally mutate a character for visual flicker
                    if random.random() < 0.05:
                        stream["chars"][i % len(stream["chars"])] = random.choice(MATRIX_CHARS)
                    self.char_grid[y][col] = stream["chars"][i % len(stream["chars"])]

                    # Brightness: bright at the head, fading toward the tail
                    if i == 0:
                        brightness = 5.0
                    elif i == 1:
                        brightness = 4.0
                    elif i < 3:
                        brightness = 3.0
                    elif i < length * 0.5:
                        brightness = 2.0
                    else:
                        brightness = 1.5

                    # Only increase brightness (never overwrite a brighter cell)
                    if brightness > self.brightness[y, col]:
                        self.brightness[y, col] = brightness

    # ── Rendering ─────────────────────────────────────────────────────────
    def render_frame(self):
        """Render the current state as a PIL RGB image."""
        img = Image.new("RGB", (self.img_w, self.img_h), BLACK)
        draw = ImageDraw.Draw(img)
        cs = self.char_size

        for y in range(self.rows):
            for x in range(self.cols):
                b = self.brightness[y, x]
                if b < 0.3:
                    continue

                char = self.char_grid[y][x]

                # Map brightness level to color (head → tail)
                if b >= 4.5:
                    color = GREEN_BRIGHT
                elif b >= 3.5:
                    color = GREEN_HEAD
                elif b >= 2.5:
                    color = GREEN_MID
                elif b >= 1.5:
                    color = GREEN_DIM
                elif b >= 0.8:
                    color = GREEN_DARK
                else:
                    color = GREEN_DARKER

                draw.text((x * cs, y * cs), char, fill=color, font=self.font)

        return img

    def render_text(self):
        """Render the current state as plain text (non-protein cells = space)."""
        lines = []
        for y in range(self.rows):
            line = ""
            for x in range(self.cols):
                if self.brightness[y, x] >= 0.5:
                    line += self.char_grid[y][x]
                else:
                    line += " "
            lines.append(line)
        return "\n".join(lines)


# Main entry point
# ──────────────────
def main():
    if len(sys.argv) < 2:
        print("Usage: python matrix_protein.py <image> [duration=5] [block=6]")
        print("  image    : path to PyMOL protein PNG/JPG")
        print("  duration : GIF duration in seconds")
        print("  block    : block size (smaller = more detail, slower)")
        sys.exit(1)

    image_path = sys.argv[1]
    duration   = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
    block_size = int(sys.argv[3]) if len(sys.argv) > 3 else 6
    char_size  = 16

    # 1 — Load image and detect green protein mask
    print(f"Loading image: {image_path}")
    mask, rgb = load_and_detect(image_path)
    print(f"  Original resolution: {mask.shape[1]} x {mask.shape[0]}")
    print(f"  Green pixels: {mask.sum()} ({mask.sum() / mask.size * 100:.1f}%)")

    # 2 — Zoom: crop to the protein bounding box
    mask, rgb = crop_to_protein(mask, rgb, padding=12)
    print(f"  Cropped to: {mask.shape[1]} x {mask.shape[0]}")

    # 3 — Downsample mask into a coarser grid
    smask = downsample_mask(mask, block_size)
    rows, cols = smask.shape
    print(f"  Grid: {cols} x {rows}")
    print(f"  Output image: {cols * char_size} x {rows * char_size} px")

    # 4 — Initialise the Matrix rain engine
    #     fade_rate=0.92 keeps characters visible long enough to show
    #     secondary structure (helices as vertical columns, loops as
    #     sparse connections between them).
    rain = MatrixRain(smask, char_size=char_size, density=3.0, fade_rate=0.92)

    # 5 — Warm-up: run several frames so streams fill the protein before capture
    warmup = 60
    print(f"\nWarming up {warmup} frames...")
    for _ in range(warmup):
        rain.step()

    # 6 — Generate animation frames
    fps = 12  # lower fps → visually slower movement
    total_frames = int(duration * fps)
    print(f"Generating {total_frames} frames at {fps} fps...")

    frames = []
    for frame_num in range(total_frames):
        rain.step()
        frames.append(rain.render_frame())
        if (frame_num + 1) % 10 == 0 or frame_num == 0:
            print(f"  Frame {frame_num + 1}/{total_frames}")

    # 7 — Save GIF animation
    gif_path = "matrix_protein.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=True,
    )
    print(f"\nGIF saved: {gif_path}")

    # 8 — Save best static frame (highest pixel coverage)
    best_frame = max(frames, key=lambda f: np.array(f).sum())
    static_path = "matrix_protein.png"
    best_frame.save(static_path)
    print(f"Static image saved: {static_path}")

    # 9 — Save plain-text matrix
    text_path = "matrix_protein.txt"
    with open(text_path, "w") as f:
        f.write(rain.render_text())
    print(f"Text file saved: {text_path}")

    # 10 — Console preview (subsampled to fit terminal width)
    print("\n" + "=" * 70)
    print("TEXT PREVIEW (Matrix format)")
    print("=" * 70 + "\n")
    sx = max(1, cols // 90)
    sy = max(1, rows // 45)
    for y in range(0, rows, sy):
        line = ""
        for x in range(0, cols, sx):
            if rain.brightness[y, x] >= 0.5:
                line += rain.char_grid[y][x]
            else:
                line += " "
        print(line)

    # 11 — Summary statistics
    visible      = int((rain.brightness >= 0.5).sum())
    protein_cells = int(smask.sum())
    print(f"\nSummary:")
    print(f"  Visible characters : {visible} / {rows * cols}")
    print(f"  Protein coverage   : {visible}/{protein_cells} ({visible / max(1, protein_cells) * 100:.1f}%)")
    print(f"  Output resolution  : {cols * char_size} x {rows * char_size}")
    print(f"  Stream speed       : slow (0.15-0.5)")
    print(f"  Fade rate          : 0.92 (structure visible)")


if __name__ == "__main__":
    main()
