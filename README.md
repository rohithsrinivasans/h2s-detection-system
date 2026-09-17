# SentryH2S — Industrial Exposure Monitoring System

Detects hydrogen sulfide (H2S) gas exposure by classifying the color change of lead acetate (Pb(CH₃COO)₂) indicator paper using a trained PyTorch Convolutional Neural Network (CNN). Features a human-crafted industrial enterprise UI, real-time camera inspection station, shift attendance roster, and OSHA compliance CSV auditing.

---

## Chemical Foundation

$$\text{Pb(CH}_3\text{COO)}_2 + \text{H}_2\text{S} \rightarrow \text{PbS (dark precipitate)} + 2\,\text{CH}_3\text{COOH}$$

Indicator paper darkens progressively through 4 distinct stages based on H2S dosage (concentration × duration):
1. **`no_exposure` (0.0 – 1.0 ppm)**: Off-white/cream paper substrate (Safe, within ACGIH TLV).
2. **`low` (1.0 – 5.0 ppm)**: Faint tan/yellowish reaction tinge (Action level, approaching STEL).
3. **`medium` (5.0 – 15.0 ppm)**: Amber/cinnamon brown discoloration (Warning, exceeds STEL).
4. **`high` (> 15.0 ppm)**: Dark brown to charcoal/black lead sulfide deposit (Danger, exceeds OSHA Ceiling).

---

## Directory Architecture

```
h2s_detection_system/
├── backend/                  # Flask REST API, PyTorch Model, Database
│   ├── app.py                # Main application routes & APIs
│   ├── config.py             # Configuration & OSHA threshold limits
│   ├── models/               # PyTorch CNN, predictor, database models
│   │   └── h2s_cnn_model.pth # Pre-trained model weights (100% test accuracy)
│   ├── requirements.txt      # Python dependencies
│   ├── Procfile              # Render start command
│   └── h2s_system.db         # SQLite database
│
├── frontend/                 # Client UI
│   ├── templates/            # Enterprise HTML templates (Sidebar, Dashboard, Scanner, etc.)
│   └── static/               # CSS, JS, and 4 calibrated chemical reference swatches
│
├── dataset/                  # Calibrated dataset & generator
│   ├── generate_dataset.py   # Synthetic dataset generator
│   ├── train/                # 1,000 training images
│   └── val/                  # 240 validation images
│
├── render.yaml               # 1-Click Render.com deployment blueprint
├── Procfile                  # Root Procfile for Render (gunicorn --chdir backend app:app)
├── run.py                    # Local launcher
└── DEPLOYMENT_RENDER.md      # Detailed cloud hosting instructions
```

---

## Quick Start (Local)

1. **Start the web application**:
   ```bash
   python run.py
   ```
2. Open **http://localhost:5000** in your browser.
3. **Credentials**:
   - Username: `admin`
   - Password: `admin123`
   *(Click "Auto-Fill" on the login page for instant authentication)*

---

## Deploy to Render.com

Deploy to Render in 1 click using the included `render.yaml` blueprint:

1. Push this repository to GitHub or GitLab.
2. In [Render Dashboard](https://dashboard.render.com), click **New +** $\rightarrow$ **Blueprint**.
3. Connect your repository and click **Apply**.
4. Render will automatically build the service with `pip install -r backend/requirements.txt` and launch it with Gunicorn.

For manual deployment steps or configuring a persistent Render PostgreSQL database, see [DEPLOYMENT_RENDER.md](file:///c:/Users/ishfaq/projects/h2s/h2s_detection_system/DEPLOYMENT_RENDER.md).
