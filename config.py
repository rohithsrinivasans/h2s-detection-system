import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'h2s_system.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}

    MODEL_PATH = os.path.join(BASE_DIR, "models", "h2s_cnn_model.h5")
    IMG_SIZE = (128, 128)

    # Exposure classes the CNN predicts, in increasing order of severity.
    # These correspond to the visible discoloration stages of lead acetate
    # (Pb(CH3COO)2) paper as it reacts with H2S to form black lead sulfide (PbS):
    #   no_exposure -> off-white/cream, unreacted paper
    #   low         -> faint tan/yellow tinge
    #   medium      -> visible light-to-mid brown
    #   high        -> dark brown / black
    CLASS_NAMES = ["no_exposure", "low", "medium", "high"]

    # IMPORTANT: These ppm ranges are placeholders for illustration only.
    # They must be calibrated against certified H2S gas standards and your
    # lead acetate paper's actual response curve (exposure time x concentration)
    # before being used for real occupational safety decisions.
    EXPOSURE_PPM_ESTIMATE = {
        "no_exposure": (0, 1),
        "low": (1, 5),
        "medium": (5, 15),
        "high": (15, None),  # None = "and above"
    }

    # OSHA/typical reference thresholds you may want to align alerts to
    # (verify against your local regulatory limits, e.g. OSHA PEL / ACGIH TLV):
    #   ~10 ppm  - short-term exposure limit territory
    #   ~20 ppm+ - considered dangerous, needs immediate action
    ALERT_THRESHOLD_CLASS = "medium"
