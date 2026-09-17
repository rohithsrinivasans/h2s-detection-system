# SentryH2S — Deployment Guide for Render.com

This project is partitioned into distinct `backend/` and `frontend/` directories, preconfigured for deployment on [Render](https://render.com).

---

## Project Structure

```
h2s_detection_system/
├── backend/                       # Python Backend & Deep Learning Model
│   ├── app.py                     # Flask application & REST API routes
│   ├── config.py                  # Settings, OSHA thresholds, dynamic pathing
│   ├── requirements.txt           # Production dependencies (PyTorch, Flask, Gunicorn)
│   ├── Procfile                   # Process file for standalone backend deployment
│   ├── runtime.txt                # Python runtime definition (python-3.11.9)
│   ├── h2s_system.db              # SQLite Database (seeded with workforce & readings)
│   └── models/
│       ├── h2s_model_pytorch.py   # PyTorch CNN Architecture
│       ├── predict.py             # Optical colorimetric inference pipeline
│       ├── train_pytorch.py       # Training script
│       ├── database_models.py     # SQLAlchemy models (User, Worker, Attendance, ExposureReading)
│       └── h2s_cnn_model.pth      # Trained Deep Learning model weights (100% accuracy)
│
├── frontend/                      # Presentation Layer
│   ├── templates/                 # Jinja2 HTML Templates
│   │   ├── base.html              # Enterprise sidebar shell & top bar
│   │   ├── dashboard.html         # Telemetry dashboard & Chart.js visualizations
│   │   ├── exposure.html          # Camera scanner, optical viewport, reference swatches
│   │   ├── attendance.html        # Shift attendance roster
│   │   ├── workers.html           # Personnel management directory
│   │   └── login.html             # Corporate authentication portal
│   │
│   └── static/                    # Client Assets
│       ├── css/style.css          # Human-crafted enterprise industrial stylesheet
│       ├── js/main.js             # Client controller (camera, Chart.js, API client)
│       ├── sample_strips/         # 4 Calibrated reference chemical strips for 1-click test
│       └── uploads/               # Stored strip uploads
│
├── dataset/                       # Training & Validation Data
│   ├── generate_dataset.py        # Chemical image generator (Pb(CH3COO)2 + H2S -> PbS)
│   ├── train/                     # 1,000 training images (250/class)
│   └── val/                       # 240 validation images (60/class)
│
├── render.yaml                    # 1-Click Render Blueprint specification
├── Procfile                       # Root Procfile for Render (gunicorn --chdir backend app:app)
├── run.py                         # Local development runner
└── README.md
```

---

## Method 1: 1-Click Deployment via Render Blueprint (Recommended)

1. Push this repository to your **GitHub** or **GitLab** account:
   ```bash
   git add .
   git commit -m "Organize backend and frontend for Render deployment"
   git push origin main
   ```
2. Log into [dashboard.render.com](https://dashboard.render.com).
3. Click **New +** in the top right and select **Blueprint**.
4. Connect your repository. Render will automatically detect `render.yaml` and configure:
   - **Service Name**: `sentry-h2s-monitor`
   - **Environment**: `Python 3.11.9`
   - **Build Command**: `pip install -r backend/requirements.txt`
   - **Start Command**: `gunicorn --chdir backend app:app`
   - **Health Check**: `/healthz`
5. Click **Apply**. Render will build and deploy the application.

---

## Method 2: Manual Web Service Setup on Render

If you prefer setting up the Web Service manually:

1. In Render Dashboard, click **New +** $\rightarrow$ **Web Service**.
2. Connect your Git repository.
3. Configure the following settings:

| Setting | Value |
| :--- | :--- |
| **Name** | `sentry-h2s-monitor` (or your preferred name) |
| **Region** | Choose the closest region (e.g., Oregon, Frankfurt, Singapore) |
| **Branch** | `main` |
| **Root Directory** | *(Leave blank or enter `.`, the configuration handles paths)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r backend/requirements.txt` |
| **Start Command** | `gunicorn --chdir backend app:app` |
| **Instance Type** | Free (or Starter) |

4. Scroll down to **Environment Variables** and add:
   - `PYTHON_VERSION`: `3.11.9`
   - `SECRET_KEY`: *(Click "Generate" or enter a secure random string)*
   - `FLASK_ENV`: `production`

5. In **Advanced Settings**, set:
   - **Health Check Path**: `/healthz`

6. Click **Create Web Service**.

---

## Database Configuration

### Option A: SQLite (Default, Included)
Out of the box, the app runs on SQLite stored at `backend/h2s_system.db`. On Render's Free tier, the filesystem is ephemeral (it resets when the instance restarts). This is great for testing and demonstrations because the database auto-seeds on first boot!

### Option B: Render Managed PostgreSQL (Production)
For persistent multi-user data storage across restarts:
1. In Render Dashboard, click **New +** $\rightarrow$ **PostgreSQL**.
2. Create a Free PostgreSQL database instance (e.g. `sentry-h2s-db`).
3. Copy the **Internal Database URL** (format: `postgres://user:password@host/dbname`).
4. In your `sentry-h2s-monitor` Web Service settings, add an Environment Variable:
   - **Key**: `DATABASE_URL`
   - **Value**: *(Paste the Internal Database URL)*
5. The backend (`backend/config.py`) automatically translates `postgres://` to `postgresql://` and creates all tables and seed data on launch.

---

## Running Locally

To run the application locally on your machine:
```bash
python run.py
```
Or directly from the backend directory:
```bash
cd backend
python app.py
```
Open **http://localhost:5000** in your browser.
- **Username**: `admin`
- **Password**: `admin123`
