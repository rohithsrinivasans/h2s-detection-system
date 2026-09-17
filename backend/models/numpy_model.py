"""
Pure NumPy inference engine for H2S Lead Acetate CNN.
Provides zero-dependency model inference using weights extracted directly from PyTorch checkpoints.
Works in restricted environments (such as Windows Smart App Control where unsigned C extensions are blocked).
"""

import io
import os
import pickle
import zipfile
import numpy as np
from PIL import Image


class _TorchUnpickler(pickle.Unpickler):
    """Safely extracts float32 weight arrays from PyTorch zip checkpoints without PyTorch installed."""
    def __init__(self, f, zfile):
        super().__init__(f)
        self.zfile = zfile

    def persistent_load(self, pid):
        typename, data_type, root_key, location, size = pid
        raw_bytes = self.zfile.read(f"h2s_cnn_model/data/{root_key}")
        return np.frombuffer(raw_bytes, dtype=np.float32).copy()

    def find_class(self, module, name):
        if module == "torch._utils" and name == "_rebuild_tensor_v2":
            def rebuild(storage, storage_offset, size, stride, requires_grad, backward_hooks):
                numel = int(np.prod(size))
                arr = storage[storage_offset:storage_offset + numel]
                return arr.reshape(size)
            return rebuild
        if module == "torch" and "Storage" in name:
            return None
        return super().find_class(module, name)


def load_numpy_weights(checkpoint_path):
    """Loads weights dictionary from PyTorch checkpoint (.pth) into pure NumPy arrays."""
    with zipfile.ZipFile(checkpoint_path, "r") as z:
        pkl_bytes = z.read("h2s_cnn_model/data.pkl")
        obj = _TorchUnpickler(io.BytesIO(pkl_bytes), z).load()
        if isinstance(obj, dict) and "model_state_dict" in obj:
            return obj["model_state_dict"]
        return obj


class NumpyCNN:
    """Evaluates the 4-stage H2SLeadAcetateCNN architecture using pure NumPy operations."""

    def __init__(self, weights):
        self.weights = weights

    @staticmethod
    def _conv2d(x, w, b):
        C, H, W = x.shape
        OutC, InC, _, _ = w.shape
        xp = np.pad(x, ((0, 0), (1, 1), (1, 1)), mode="constant")
        out = np.zeros((OutC, H, W), dtype=np.float32)
        for c in range(InC):
            wc = w[:, c, :, :]
            for i in range(3):
                for j in range(3):
                    out += wc[:, i, j, None, None] * xp[c, i:i + H, j:j + W][None, :, :]
        out += b[:, None, None]
        return out

    @staticmethod
    def _bn(x, w, b, mean, var, eps=1e-5):
        std = np.sqrt(var + eps)
        return (x - mean[:, None, None]) / std[:, None, None] * w[:, None, None] + b[:, None, None]

    @staticmethod
    def _maxpool2x2(x):
        C, H, W = x.shape
        return x.reshape(C, H // 2, 2, W // 2, 2).max(axis=(2, 4))

    @staticmethod
    def _leaky_relu(x, slope=0.1):
        return np.where(x >= 0, x, x * slope)

    def predict(self, img: Image.Image):
        # Resize to 128x128 and normalize with ImageNet statistics
        img_resized = img.convert("RGB").resize((128, 128))
        arr = np.array(img_resized, dtype=np.float32) / 255.0
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
        x = ((arr - mean) / std).transpose(2, 0, 1)

        # Block 1
        x = self._conv2d(x, self.weights["conv1.weight"], self.weights["conv1.bias"])
        x = self._bn(x, self.weights["bn1.weight"], self.weights["bn1.bias"], self.weights["bn1.running_mean"], self.weights["bn1.running_var"])
        x = self._maxpool2x2(self._leaky_relu(x))

        # Block 2
        x = self._conv2d(x, self.weights["conv2.weight"], self.weights["conv2.bias"])
        x = self._bn(x, self.weights["bn2.weight"], self.weights["bn2.bias"], self.weights["bn2.running_mean"], self.weights["bn2.running_var"])
        x = self._maxpool2x2(self._leaky_relu(x))

        # Block 3
        x = self._conv2d(x, self.weights["conv3.weight"], self.weights["conv3.bias"])
        x = self._bn(x, self.weights["bn3.weight"], self.weights["bn3.bias"], self.weights["bn3.running_mean"], self.weights["bn3.running_var"])
        x = self._maxpool2x2(self._leaky_relu(x))

        # Block 4
        x = self._conv2d(x, self.weights["conv4.weight"], self.weights["conv4.bias"])
        x = self._bn(x, self.weights["bn4.weight"], self.weights["bn4.bias"], self.weights["bn4.running_mean"], self.weights["bn4.running_var"])
        x = self._maxpool2x2(self._leaky_relu(x))

        # Global Avg Pool (128,)
        x = x.mean(axis=(1, 2))

        # Classification Head: FC1 + ReLU
        x = np.maximum(0, np.dot(self.weights["fc1.weight"], x) + self.weights["fc1.bias"])

        # FC2
        logits = np.dot(self.weights["fc2.weight"], x) + self.weights["fc2.bias"]

        # Softmax
        exp_l = np.exp(logits - np.max(logits))
        probs = (exp_l / exp_l.sum()).tolist()
        idx = int(np.argmax(probs))
        confidence = float(probs[idx])
        return idx, confidence, probs
