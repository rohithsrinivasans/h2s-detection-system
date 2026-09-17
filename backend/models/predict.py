import os
import sys
import time
from PIL import Image

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import Config

# Try importing PyTorch; fall back smoothly if blocked by OS policy (e.g. Smart App Control)
TORCH_AVAILABLE = False
try:
    import torch
    import torch.nn.functional as F
    from torchvision import transforms
    from models.h2s_model_pytorch import get_model
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    F = None
    transforms = None
    get_model = None

# Import pure NumPy CNN engine for zero-dependency inference
try:
    from models.numpy_model import NumpyCNN, load_numpy_weights
    NUMPY_CNN_AVAILABLE = True
except Exception:
    NumpyCNN = None
    load_numpy_weights = None
    NUMPY_CNN_AVAILABLE = False


# Standard Normalization matching training (when torchvision is available)
if TORCH_AVAILABLE and transforms is not None:
    NORMALIZE = transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225],
    )
    INFERENCE_TRANSFORMS = transforms.Compose([
        transforms.Resize(Config.IMG_SIZE),
        transforms.ToTensor(),
        NORMALIZE,
    ])
    _device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
else:
    NORMALIZE = None
    INFERENCE_TRANSFORMS = None
    _device = None

_cached_model = None


def load_inference_model():
    """Loads and caches the trained model (PyTorch CNN or pure NumPy CNN)."""
    global _cached_model
    model_path = Config.MODEL_PATH

    if _cached_model is not None:
        return _cached_model

    if not os.path.exists(model_path):
        return None

    # 1. Try PyTorch first if available
    if TORCH_AVAILABLE and get_model is not None:
        try:
            model = get_model(num_classes=len(Config.CLASS_NAMES))
            checkpoint = torch.load(model_path, map_location=_device)
            if "model_state_dict" in checkpoint:
                model.load_state_dict(checkpoint["model_state_dict"])
            else:
                model.load_state_dict(checkpoint)
            model.to(_device)
            model.eval()
            _cached_model = model
            print(f"[AI Vision] PyTorch model loaded successfully from {model_path}")
            return _cached_model
        except Exception as e:
            print(f"[AI Vision Warning] PyTorch model load failed: {e}. Falling back to NumPy engine.")

    # 2. Try pure NumPy CNN engine (reads exact trained weights directly from .pth)
    if NUMPY_CNN_AVAILABLE and load_numpy_weights is not None:
        try:
            weights = load_numpy_weights(model_path)
            _cached_model = NumpyCNN(weights)
            print(f"[AI Vision] High-performance NumPy CNN loaded successfully from {model_path}")
            return _cached_model
        except Exception as e:
            print(f"[AI Vision Warning] NumPy CNN engine load failed: {e}")

    return None


def _colorimetric_heuristic(img: Image.Image):
    """Fallback colorimetry classifier if model file is not present."""
    arr = img.convert("RGB").resize((64, 64))
    import numpy as np
    pixels = np.array(arr, dtype=np.float32)

    brightness = float(pixels.mean())
    r, g, b = pixels[:, :, 0].mean(), pixels[:, :, 1].mean(), pixels[:, :, 2].mean()

    if brightness > 220 and b > 190:
        idx, conf = 0, 0.92
    elif brightness > 120:
        idx, conf = 1, 0.88
    elif brightness > 50:
        idx, conf = 2, 0.90
    else:
        idx, conf = 3, 0.94

    probs = [0.03, 0.03, 0.03, 0.03]
    probs[idx] = conf
    total = sum(probs)
    probs = [p / total for p in probs]
    return idx, conf, probs


def predict_exposure(image_source):
    """
    Analyzes an indicator paper image and returns detailed exposure diagnostics.
    
    image_source: filepath string or PIL Image object.
    Returns: dict with prediction results, calibrated ppm, hazard metadata, and timing.
    """
    start_time = time.perf_counter()

    if isinstance(image_source, str):
        if not os.path.exists(image_source):
            raise FileNotFoundError(f"Image not found: {image_source}")
        img = Image.open(image_source).convert("RGB")
    elif isinstance(image_source, Image.Image):
        img = image_source.convert("RGB")
    else:
        raise ValueError("Unsupported image source type")

    model = load_inference_model()
    is_trained = model is not None

    if is_trained:
        if NUMPY_CNN_AVAILABLE and isinstance(model, NumpyCNN):
            idx, confidence, probs = model.predict(img)
        elif TORCH_AVAILABLE and torch is not None:
            tensor = INFERENCE_TRANSFORMS(img).unsqueeze(0).to(_device)
            with torch.no_grad():
                logits = model(tensor)
                probs_tensor = F.softmax(logits, dim=1)[0]
                probs = probs_tensor.cpu().numpy().tolist()
                idx = int(torch.argmax(probs_tensor).item())
                confidence = float(probs[idx])
        else:
            idx, confidence, probs = _colorimetric_heuristic(img)
    else:
        idx, confidence, probs = _colorimetric_heuristic(img)

    elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
    class_name = Config.CLASS_NAMES[idx]
    ppm_low, ppm_high = Config.EXPOSURE_PPM_ESTIMATE[class_name]
    hazard = Config.HAZARD_INFO[class_name]

    # Probabilities mapped by class name
    all_probs = {cls_name: round(probs[i] * 100, 1) for i, cls_name in enumerate(Config.CLASS_NAMES)}

    return {
        "predicted_class": class_name,
        "confidence": round(confidence, 4),
        "confidence_pct": round(confidence * 100, 1),
        "ppm_estimate_low": ppm_low,
        "ppm_estimate_high": ppm_high,
        "ppm_formatted": f"{ppm_low} – {ppm_high} ppm" if ppm_high else f"> {ppm_low} ppm",
        "hazard": hazard,
        "all_probs": all_probs,
        "using_trained_model": is_trained,
        "inference_time_ms": elapsed_ms,
    }

