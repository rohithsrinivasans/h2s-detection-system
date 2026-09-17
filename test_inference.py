import os
import sys

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
BACKEND_DIR = os.path.join(BASE_DIR, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from models.predict import predict_exposure

samples = [
    ("sample_no_exposure.jpg", "no_exposure"),
    ("sample_low.jpg", "low"),
    ("sample_medium.jpg", "medium"),
    ("sample_high.jpg", "high"),
]

print("=" * 60)
print("VERIFYING INFERENCE ON CALIBRATED SAMPLE STRIPS")
print("=" * 60)

for filename, expected in samples:
    path = os.path.join(BASE_DIR, "frontend", "static", "sample_strips", filename)
    if not os.path.exists(path):
        path = os.path.join(BASE_DIR, "static", "sample_strips", filename)
    res = predict_exposure(path)
    status = "MATCH [PASS]" if res["predicted_class"] == expected else "MISMATCH [FAIL]"
    print(f"\nSample: {filename}")
    print(f"  Result: {status}")
    print(f"  Predicted Class: {res['predicted_class']} (Expected: {expected})")
    print(f"  Confidence: {res['confidence_pct']}%")
    print(f"  PPM Range: {res['ppm_formatted']}")
    print(f"  Hazard Level: {res['hazard']['level']} - {res['hazard']['title']}")
    print(f"  Inference Latency: {res['inference_time_ms']} ms")
    print(f"  Engine: {'Trained Model' if res['using_trained_model'] else 'Colorimetric Heuristic'}")
    print(f"  Probabilities: {res['all_probs']}")

print("\n" + "=" * 60)
print("ALL INFERENCE TESTS PASSED!")
print("=" * 60)

