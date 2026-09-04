"""
Inference wrapper: load the trained CNN once, run predictions on new
lead-acetate-paper photos captured from the web app (camera upload).

Falls back to a simple HSV-darkness heuristic if no trained model file
exists yet, so the website is runnable end-to-end before you have
collected/labeled a real dataset.
"""

import os
import numpy as np
from PIL import Image

from config import Config

_model = None


def _load_model():
    global _model
    if _model is None and os.path.exists(Config.MODEL_PATH):
        import tensorflow as tf

        _model = tf.keras.models.load_model(Config.MODEL_PATH)
    return _model


def _heuristic_predict(img: Image.Image):
    """Fallback classifier used only when no trained model is present yet.
    Buckets by how dark/brown the average pixel is (crude proxy for
    lead-sulfide darkening). Replace with the trained CNN as soon as you
    have labeled data -- this heuristic is NOT a substitute for a
    calibrated safety-monitoring model."""
    arr = np.array(img.convert("RGB").resize((64, 64))).astype(np.float32)
    brightness = arr.mean()  # 0 (black) - 255 (white)

    if brightness > 200:
        idx, conf = 0, 0.55
    elif brightness > 160:
        idx, conf = 1, 0.5
    elif brightness > 110:
        idx, conf = 2, 0.5
    else:
        idx, conf = 3, 0.55

    probs = [0.1, 0.1, 0.1, 0.1]
    probs[idx] = conf
    return idx, conf, probs


def predict_exposure(image_path):
    """Returns dict: predicted_class, confidence, ppm_low, ppm_high, all_probs."""
    img = Image.open(image_path)
    model = _load_model()

    if model is not None:
        img_resized = img.convert("RGB").resize(Config.IMG_SIZE)
        arr = np.expand_dims(np.array(img_resized).astype(np.float32), axis=0)
        preds = model.predict(arr, verbose=0)[0]
        idx = int(np.argmax(preds))
        confidence = float(preds[idx])
        all_probs = preds.tolist()
    else:
        idx, confidence, all_probs = _heuristic_predict(img)

    class_name = Config.CLASS_NAMES[idx]
    ppm_low, ppm_high = Config.EXPOSURE_PPM_ESTIMATE[class_name]

    return {
        "predicted_class": class_name,
        "confidence": confidence,
        "ppm_estimate_low": ppm_low,
        "ppm_estimate_high": ppm_high,
        "all_probs": dict(zip(Config.CLASS_NAMES, all_probs)),
        "using_trained_model": model is not None,
    }
