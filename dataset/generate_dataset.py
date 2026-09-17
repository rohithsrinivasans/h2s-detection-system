"""
Synthetic Dataset Generator for Lead Acetate H2S Detection Paper.

Chemical basis:
Pb(CH3COO)2 (lead acetate, white/cream) + H2S (gas) -> PbS (lead sulfide, black) + 2 CH3COOH

Classes:
1. no_exposure: (0-1 ppm) Off-white/cream paper texture, unreacted lead acetate.
2. low:         (1-5 ppm) Faint tan/yellowish tinge, subtle early reaction.
3. medium:      (5-15 ppm) Noticeable honey/amber/cinnamon brown reaction patches.
4. high:        (15+ ppm) Heavy dark brown to charcoal/black PbS precipitation.

Generates realistic paper fiber grain, uneven chemical exposure patches, illumination gradients,
and camera sensor noise.
"""

import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


# Class visual definitions: base RGB colors and reaction spot ranges
CLASS_CONFIGS = {
    "no_exposure": {
        "base_rgb": (244, 240, 230),  # Off-white / cream paper
        "rgb_jitter": (8, 8, 10),
        "spot_rgb": (238, 232, 218),
        "spot_intensity": 0.05,
        "darkening_factor": (0.96, 1.02),
        "num_spots": (2, 6),
    },
    "low": {
        "base_rgb": (222, 200, 155),  # Faint tan / yellow tinge
        "rgb_jitter": (12, 14, 15),
        "spot_rgb": (195, 170, 120),
        "spot_intensity": 0.35,
        "darkening_factor": (0.85, 0.95),
        "num_spots": (10, 25),
    },
    "medium": {
        "base_rgb": (155, 108, 62),   # Visible amber/cinnamon brown
        "rgb_jitter": (15, 15, 12),
        "spot_rgb": (115, 75, 40),
        "spot_intensity": 0.65,
        "darkening_factor": (0.65, 0.80),
        "num_spots": (20, 45),
    },
    "high": {
        "base_rgb": (48, 36, 28),     # Dark brown to black lead sulfide (PbS)
        "rgb_jitter": (10, 8, 8),
        "spot_rgb": (22, 18, 15),
        "spot_intensity": 0.92,
        "darkening_factor": (0.25, 0.45),
        "num_spots": (35, 70),
    },
}


def generate_paper_strip(cls_name, size=(128, 128), is_sample=False):
    cfg = CLASS_CONFIGS[cls_name]
    w, h = size

    # 1. Base color with slight random shift
    base_r = int(np.clip(cfg["base_rgb"][0] + random.randint(-cfg["rgb_jitter"][0], cfg["rgb_jitter"][0]), 0, 255))
    base_g = int(np.clip(cfg["base_rgb"][1] + random.randint(-cfg["rgb_jitter"][1], cfg["rgb_jitter"][1]), 0, 255))
    base_b = int(np.clip(cfg["base_rgb"][2] + random.randint(-cfg["rgb_jitter"][2], cfg["rgb_jitter"][2]), 0, 255))

    arr = np.zeros((h, w, 3), dtype=np.float32)
    arr[:, :, 0] = base_r
    arr[:, :, 1] = base_g
    arr[:, :, 2] = base_b

    # 2. Add realistic paper fiber texture (fine grain)
    grain = np.random.normal(0, 4.5, (h, w, 1))
    arr += grain

    # 3. Add smooth illumination gradient (simulates light box / phone flashlight angle)
    angle = random.uniform(0, 2 * np.pi)
    x_coords, y_coords = np.meshgrid(np.linspace(-1, 1, w), np.linspace(-1, 1, h))
    grad = np.cos(angle) * x_coords + np.sin(angle) * y_coords
    grad_intensity = random.uniform(8.0, 18.0)
    arr += grad[:, :, np.newaxis] * grad_intensity

    # Convert to PIL for spot and reaction zone drawing
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    img = Image.fromarray(arr, mode="RGB")
    draw = ImageDraw.Draw(img)

    # 4. Chemical reaction spot heterogeneity (PbS precipitation forms clusters)
    num_spots = random.randint(*cfg["num_spots"])
    spot_r, spot_g, spot_b = cfg["spot_rgb"]

    for _ in range(num_spots):
        sx = random.randint(5, w - 5)
        sy = random.randint(5, h - 5)
        rad = random.randint(3, int(w * 0.35))
        alpha = random.uniform(0.2, cfg["spot_intensity"])
        
        # Color of this particular reaction spot
        cr = int(np.clip(spot_r + random.randint(-10, 10), 0, 255))
        cg = int(np.clip(spot_g + random.randint(-8, 8), 0, 255))
        cb = int(np.clip(spot_b + random.randint(-6, 6), 0, 255))

        # Overlay elliptical reaction patch
        bbox = [sx - rad, sy - rad, sx + rad, sy + rad]
        draw.ellipse(bbox, fill=(cr, cg, cb))

    # Apply slight gaussian blur to blend chemical reaction smoothly into paper
    img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(2.5, 4.5)))

    # 5. Optional paper edge border (simulates realistic physical strip margin)
    if random.random() < 0.35 or is_sample:
        # Add subtle paper border or shadow at one edge
        arr_img = np.array(img, dtype=np.float32)
        border_side = random.choice(["top", "bottom", "left", "right"])
        thickness = random.randint(3, 8)
        if border_side == "top":
            arr_img[:thickness, :, :] *= 0.85
        elif border_side == "bottom":
            arr_img[-thickness:, :, :] *= 0.85
        elif border_side == "left":
            arr_img[:, :thickness, :] *= 0.85
        elif border_side == "right":
            arr_img[:, -thickness:, :] *= 0.85
        img = Image.fromarray(np.clip(arr_img, 0, 255).astype(np.uint8))

    return img


def generate_full_dataset(base_dir, train_count=250, val_count=60):
    """Generate train and val split for all 4 classes."""
    train_dir = os.path.join(base_dir, "train")
    val_dir = os.path.join(base_dir, "val")

    classes = ["no_exposure", "low", "medium", "high"]

    for c in classes:
        os.makedirs(os.path.join(train_dir, c), exist_ok=True)
        os.makedirs(os.path.join(val_dir, c), exist_ok=True)

    print(f"Generating training set ({train_count} images/class)...")
    for c in classes:
        target_dir = os.path.join(train_dir, c)
        for i in range(train_count):
            img = generate_paper_strip(c, size=(128, 128))
            img.save(os.path.join(target_dir, f"{c}_train_{i:04d}.jpg"), quality=94)

    print(f"Generating validation set ({val_count} images/class)...")
    for c in classes:
        target_dir = os.path.join(val_dir, c)
        for i in range(val_count):
            img = generate_paper_strip(c, size=(128, 128))
            img.save(os.path.join(target_dir, f"{c}_val_{i:04d}.jpg"), quality=94)

    print("Dataset generation complete!")


def generate_curated_samples(sample_dir):
    """Generates high-resolution sample strips for 1-click browser testing."""
    os.makedirs(sample_dir, exist_ok=True)
    classes = ["no_exposure", "low", "medium", "high"]
    for c in classes:
        img = generate_paper_strip(c, size=(256, 256), is_sample=True)
        img.save(os.path.join(sample_dir, f"sample_{c}.jpg"), quality=95)
    print(f"Curated reference samples saved to {sample_dir}")


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(current_dir)
    static_sample_dir = os.path.join(project_dir, "static", "sample_strips")

    generate_full_dataset(current_dir, train_count=250, val_count=60)
    generate_curated_samples(static_sample_dir)
