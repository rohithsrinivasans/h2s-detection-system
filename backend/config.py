import os

# Base directories
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.abspath(os.path.join(BASE_DIR, ".."))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

# Ensure frontend fallback if packaged as standalone backend
if not os.path.exists(FRONTEND_DIR):
    FRONTEND_DIR = BASE_DIR


class Config:
    BASE_DIR = BASE_DIR
    FRONTEND_DIR = FRONTEND_DIR
    SECRET_KEY = os.environ.get("SECRET_KEY", "sentry-h2s-production-secret-982341")

    # Render PostgreSQL compatibility fix (Render sets postgres://, SQLAlchemy requires postgresql://)
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url and _db_url.startswith("postgres://"):
        _db_url = _db_url.replace("postgres://", "postgresql://", 1)

    SQLALCHEMY_DATABASE_URI = _db_url or f"sqlite:///{os.path.join(BASE_DIR, 'h2s_system.db')}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Frontend asset directories
    UPLOAD_FOLDER = os.path.join(FRONTEND_DIR, "static", "uploads")
    SAMPLE_STRIPS_DIR = os.path.join(FRONTEND_DIR, "static", "sample_strips")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

    # PyTorch Model
    MODEL_PATH = os.path.join(BASE_DIR, "models", "h2s_cnn_model.pth")
    IMG_SIZE = (128, 128)

    # Exposure classes in increasing order of severity:
    CLASS_NAMES = ["no_exposure", "low", "medium", "high"]

    # Calibrated ppm ranges associated with lead acetate colorimetry stages
    EXPOSURE_PPM_ESTIMATE = {
        "no_exposure": (0.0, 1.0),
        "low": (1.0, 5.0),
        "medium": (5.0, 15.0),
        "high": (15.0, 50.0),
    }

    # OSHA / ACGIH Regulatory & Occupational Safety Thresholds
    OSHA_STANDARDS = {
        "ACGIH_TLV_TWA": "1 ppm (8-hour Time-Weighted Average)",
        "ACGIH_STEL": "5 ppm (15-min Short-Term Exposure Limit)",
        "OSHA_CEILING": "20 ppm (Acceptable Ceiling Concentration)",
        "OSHA_PEAK": "50 ppm (10-minute Maximum Peak)",
        "NIOSH_IDLH": "100 ppm (Immediately Dangerous to Life or Health)",
    }

    # Detailed Hazard Metadata per class
    HAZARD_INFO = {
        "no_exposure": {
            "title": "Normal / Safe Condition",
            "level": "SAFE",
            "badge_class": "safe",
            "color": "#10b981",
            "bg_color": "rgba(16, 185, 129, 0.12)",
            "osha_status": "Within ACGIH TLV (≤ 1 ppm)",
            "recommendation": "Standard operation permitted. Maintain continuous monitor wear.",
        },
        "low": {
            "title": "Action Level Detected",
            "level": "CAUTION",
            "badge_class": "low",
            "color": "#f59e0b",
            "bg_color": "rgba(245, 158, 11, 0.12)",
            "osha_status": "Approaching STEL Limit (1 - 5 ppm)",
            "recommendation": "Notify area supervisor. Inspect local seals and valves. Verify ventilation.",
        },
        "medium": {
            "title": "Warning: Elevated Exposure",
            "level": "WARNING",
            "badge_class": "medium",
            "color": "#f97316",
            "bg_color": "rgba(249, 115, 22, 0.12)",
            "osha_status": "Exceeds 15-min STEL (5 - 15 ppm)",
            "recommendation": "Evacuate non-essential personnel. Don supplied-air respirator or SCBA.",
        },
        "high": {
            "title": "Critical Hazard: High H2S",
            "level": "DANGER",
            "badge_class": "high",
            "color": "#ef4444",
            "bg_color": "rgba(239, 68, 68, 0.15)",
            "osha_status": "Approaching/Exceeding OSHA Ceiling (> 15 ppm)",
            "recommendation": "IMMEDIATE EVACUATION. Sound plant alert, activate emergency deluge and ventilation.",
        },
    }
