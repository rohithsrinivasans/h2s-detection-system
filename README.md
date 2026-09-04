# H2S Exposure Monitoring System (Lead Acetate Paper + CNN + Web App)

Detects H2S gas exposure by classifying the color change of lead acetate
(Pb(CH3COO)2) indicator paper via a CNN, and tracks it per worker with a
login-protected website (daily attendance + hour-wise exposure log).

## How it works

1. Lead acetate paper darkens on contact with H2S: `Pb(CH3COO)2 + H2S -> PbS (black) + 2 CH3COOH`.
2. A camera (phone, or fixed webcam near the paper strip) photographs the paper.
3. A CNN classifies the photo into `no_exposure / low / medium / high`.
4. The result is logged against the worker, tagged with the hour, for daily
   attendance + hour-wise exposure history and dashboard alerts.

## Project layout

```
h2s_detection_system/
  app.py                     # Flask app: routes, auth, dashboard, attendance, exposure
  config.py                  # settings, class names, placeholder ppm ranges
  requirements.txt
  models/
    database_models.py       # User, Worker, Attendance, ExposureReading (SQLAlchemy)
    cnn_model.py              # CNN architecture (Keras)
    train_cnn.py              # training script
    predict.py                 # inference used by the Flask app
  templates/                  # Jinja2 HTML pages
  static/css/style.css
  static/uploads/             # captured photos land here
  dataset/train|val/<class>/  # put your labeled training photos here
```

## 1. Install

```bash
cd h2s_detection_system
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## 2. Run the website (works immediately, before you train a model)

```bash
python app.py
```

Visit `http://localhost:5000`. First run auto-creates:
- **admin / admin123** — change this password immediately (there's no
  "change password" UI yet; simplest is to update it directly via a Python
  shell using `User.set_password()`, or add a settings page).

Until you've trained the CNN, `models/predict.py` automatically falls back
to a simple brightness heuristic so the whole workflow (upload → classify →
log → dashboard) is testable end-to-end. **Do not use the heuristic for
real safety decisions** — it's a placeholder.

## 3. Add workers

Log in as admin → **Workers** → add each worker's name, employee code,
department/zone, and a login username/password. This also creates their
personal login so they can view their own exposure history if desired.

## 4. Collect a labeled dataset for the real CNN

This is the part that determines real-world accuracy — the code is only as
good as the photos you train it on.

- Set up a **fixed, enclosed light box** for photographing the paper strip:
  consistent lighting eliminates the #1 source of misclassification (shadows
  and mixed daylight/LED color casts).
- Expose lead acetate paper strips to **known H2S concentrations** for known
  durations (e.g. using calibration gas / a controlled test chamber) and
  photograph each resulting strip.
- Sort photos into `dataset/train/<class>/` and `dataset/val/<class>/` where
  `<class>` is one of `no_exposure`, `low`, `medium`, `high`.
- Aim for at least ~100–200 images per class if possible; more is better.
  Vary paper batches and slight timing differences within each class so the
  model generalizes.

## 5. Train the CNN

```bash
cd models
python train_cnn.py --train_dir ../dataset/train --val_dir ../dataset/val --epochs 30
```

This saves the best model to `models/h2s_cnn_model.h5`. The Flask app picks
it up automatically on next restart (`predict.py` loads it if present).

## 6. Calibrate ppm ranges — important

`config.py` has an `EXPOSURE_PPM_ESTIMATE` dict with **placeholder** ppm
ranges per class. These must be replaced with values derived from your
actual calibration-gas exposure tests, matched to your specific lead
acetate paper's sensitivity and your camera/lighting setup. Do not treat the
shipped numbers as real occupational exposure limits — verify against
OSHA/ACGIH or your local regulatory H2S exposure limits and your industrial
hygienist's guidance before using this for compliance decisions.

## 7. Deployment notes

- For production, run behind Gunicorn + Nginx (or similar), set a real
  `SECRET_KEY` env var, and switch `SQLALCHEMY_DATABASE_URI` to Postgres/MySQL
  instead of SQLite once you have concurrent users.
- If workers capture photos from phones on the shop floor, consider a
  lightweight PWA wrapper or just the mobile browser — the file input already
  uses `capture="environment"` so tapping it opens the phone camera directly.
- Add HTTPS (required for camera access on most mobile browsers except on
  localhost).
- This system is a **detection aid**, not a certified continuous gas
  monitor — pair it with proper fixed/portable H2S gas detectors per your
  safety program; don't rely on it as the sole safety control for a
  IDLH-capable gas like H2S.

## Extending

- Add shift-based reporting (e.g. TWA exposure per shift) by aggregating
  `ExposureReading` rows by worker + date.
- Add email/SMS alerts on `medium`/`high` classifications (hook into the
  `exposure()` route in `app.py` where the alert flash is currently set).
- Add a password-change / worker self-service page.
- Swap SQLite for Postgres for multi-site deployments.
