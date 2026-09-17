import os
import io
import json
import base64
import csv
from datetime import datetime, date, timedelta

from flask import (
    Flask, render_template, redirect, url_for, request, flash, jsonify, abort, Response
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename
from PIL import Image

# Support running from backend directory or from repository root
import sys
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from config import Config
from models.database_models import db, User, Worker, Attendance, ExposureReading
from models.predict import predict_exposure


def create_app():
    template_dir = os.path.join(Config.FRONTEND_DIR, "templates")
    static_dir = os.path.join(Config.FRONTEND_DIR, "static")

    app = Flask(
        __name__,
        template_folder=template_dir,
        static_folder=static_dir,
    )
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["SAMPLE_STRIPS_DIR"], exist_ok=True)
    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = "login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    def allowed_file(filename):
        return (
            "." in filename
            and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]
        )

    def admin_required(fn):
        from functools import wraps

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated or current_user.role != "admin":
                abort(403)
            return fn(*args, **kwargs)

        return wrapper

    # ------------------------------------------------------------- HEALTH CHECK
    @app.route("/healthz")
    @app.route("/api/health")
    def health_check():
        """Render / automated health check endpoint."""
        model_exists = os.path.exists(Config.MODEL_PATH)
        return jsonify({
            "status": "healthy",
            "model_present": model_exists,
            "timestamp": datetime.utcnow().isoformat(),
        }), 200

    # ---------------------------------------------------------------- AUTH
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard"))
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                login_user(user)
                flash("Authenticated session initiated.", "success")
                return redirect(url_for("dashboard"))
            flash("Invalid operator credentials. Access denied.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("Session terminated successfully.", "success")
        return redirect(url_for("login"))

    # ----------------------------------------------------------- DASHBOARD
    @app.route("/")
    @login_required
    def dashboard():
        today = date.today()
        if current_user.role == "admin":
            total_workers = Worker.query.count()
            present_today = Attendance.query.filter_by(
                work_date=today, status="present"
            ).count()
            recent_readings = (
                ExposureReading.query.order_by(ExposureReading.timestamp.desc())
                .limit(20)
                .all()
            )
            alerts_today = (
                ExposureReading.query.filter(
                    db.func.date(ExposureReading.timestamp) == today,
                    ExposureReading.predicted_class.in_(["low", "medium", "high"]),
                ).count()
            )
            high_alerts_today = (
                ExposureReading.query.filter(
                    db.func.date(ExposureReading.timestamp) == today,
                    ExposureReading.predicted_class == "high",
                ).count()
            )
            safe_count = (
                ExposureReading.query.filter(
                    db.func.date(ExposureReading.timestamp) == today,
                    ExposureReading.predicted_class == "no_exposure",
                ).count()
            )
            return render_template(
                "dashboard.html",
                total_workers=total_workers,
                present_today=present_today,
                recent_readings=recent_readings,
                alerts_today=alerts_today,
                high_alerts_today=high_alerts_today,
                safe_count=safe_count,
            )
        else:
            worker = current_user.worker_profile
            today_readings = []
            if worker:
                today_readings = (
                    ExposureReading.query.filter(
                        ExposureReading.worker_id == worker.id,
                        db.func.date(ExposureReading.timestamp) == today,
                    )
                    .order_by(ExposureReading.timestamp.asc())
                    .all()
                )
            return render_template(
                "dashboard.html",
                worker=worker,
                recent_readings=today_readings,
                total_workers=1,
                present_today=1,
                alerts_today=sum(1 for r in today_readings if r.predicted_class != "no_exposure"),
                high_alerts_today=sum(1 for r in today_readings if r.predicted_class == "high"),
                safe_count=sum(1 for r in today_readings if r.predicted_class == "no_exposure"),
            )

    # ------------------------------------------------------ EXPOSURE SCANNER
    @app.route("/exposure", methods=["GET", "POST"])
    @login_required
    def exposure():
        workers = Worker.query.all()
        selected_worker_id = request.args.get("worker_id", type=int)

        if not selected_worker_id and workers:
            selected_worker_id = workers[0].id

        history = []
        if selected_worker_id:
            history = (
                ExposureReading.query.filter_by(worker_id=selected_worker_id)
                .order_by(ExposureReading.timestamp.desc())
                .limit(50)
                .all()
            )

        return render_template(
            "exposure.html",
            workers=workers,
            history=history,
            selected_worker_id=selected_worker_id,
        )

    # ------------------------------------------------- REST API: ANALYZE STRIP
    @app.route("/api/analyze", methods=["POST"])
    @login_required
    def api_analyze():
        worker_id = None
        save_path = None
        rel_path = None

        if request.is_json:
            data = request.get_json()
            worker_id = data.get("worker_id")
            base64_str = data.get("image_base64", "")

            if not base64_str:
                return jsonify({"success": False, "error": "No image data received"}), 400

            try:
                if "," in base64_str:
                    base64_str = base64_str.split(",", 1)[1]
                image_bytes = base64.b64decode(base64_str)
                img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

                filename = f"scan_{int(datetime.utcnow().timestamp())}_{os.urandom(3).hex()}.jpg"
                save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                img.save(save_path, "JPEG", quality=95)
                rel_path = f"uploads/{filename}"
            except Exception as e:
                return jsonify({"success": False, "error": f"Corrupt image stream: {e}"}), 400

        elif "photo" in request.files:
            worker_id = request.form.get("worker_id")
            file = request.files.get("photo")

            if not file or file.filename == "" or not allowed_file(file.filename):
                return jsonify({"success": False, "error": "Invalid image format (JPG/PNG only)"}), 400

            filename = secure_filename(
                f"upload_{int(datetime.utcnow().timestamp())}_{file.filename}"
            )
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)
            rel_path = f"uploads/{filename}"
        else:
            return jsonify({"success": False, "error": "No image provided"}), 400

        if not worker_id:
            worker = Worker.query.first()
            worker_id = worker.id if worker else 1

        try:
            diagnosis = predict_exposure(save_path)
            now = datetime.utcnow()

            reading = ExposureReading(
                worker_id=int(worker_id),
                timestamp=now,
                image_path=rel_path,
                predicted_class=diagnosis["predicted_class"],
                confidence=diagnosis["confidence"],
                ppm_estimate_low=diagnosis["ppm_estimate_low"],
                ppm_estimate_high=diagnosis["ppm_estimate_high"],
                hour_of_day=now.hour,
            )
            db.session.add(reading)
            db.session.commit()

            return jsonify({
                "success": True,
                "diagnosis": diagnosis,
                "reading": reading.to_dict(),
            })
        except Exception as e:
            return jsonify({"success": False, "error": f"AI model inference error: {e}"}), 500

    # ------------------------------------------------ REST API: SAMPLE STRIPS
    @app.route("/api/sample-strips")
    def api_sample_strips():
        samples = [
            {
                "id": "no_exposure",
                "name": "Fresh / Unreacted",
                "ppm": "0.0 – 1.0 ppm",
                "class_name": "no_exposure",
                "url": url_for("static", filename="sample_strips/sample_no_exposure.jpg"),
            },
            {
                "id": "low",
                "name": "Low Discoloration",
                "ppm": "1.0 – 5.0 ppm",
                "class_name": "low",
                "url": url_for("static", filename="sample_strips/sample_low.jpg"),
            },
            {
                "id": "medium",
                "name": "Moderate Reaction",
                "ppm": "5.0 – 15.0 ppm",
                "class_name": "medium",
                "url": url_for("static", filename="sample_strips/sample_medium.jpg"),
            },
            {
                "id": "high",
                "name": "Heavy PbS Deposit",
                "ppm": "> 15.0 ppm",
                "class_name": "high",
                "url": url_for("static", filename="sample_strips/sample_high.jpg"),
            },
        ]
        return jsonify(samples)

    # --------------------------------------------- REST API: DASHBOARD STATS
    @app.route("/api/stats")
    @login_required
    def api_stats():
        today = date.today()
        readings = ExposureReading.query.filter(
            db.func.date(ExposureReading.timestamp) == today
        ).all()

        hourly_counts = [0] * 24
        class_breakdown = {"no_exposure": 0, "low": 0, "medium": 0, "high": 0}

        for r in readings:
            if 0 <= r.hour_of_day < 24:
                hourly_counts[r.hour_of_day] += 1
            if r.predicted_class in class_breakdown:
                class_breakdown[r.predicted_class] += 1

        total_workers = Worker.query.count()
        present_today = Attendance.query.filter_by(
            work_date=today, status="present"
        ).count()

        return jsonify({
            "total_workers": total_workers,
            "present_today": present_today,
            "hourly_counts": hourly_counts,
            "class_breakdown": class_breakdown,
            "total_readings_today": len(readings),
        })

    # --------------------------------------------- EXPORT CSV COMPLIANCE LOG
    @app.route("/export/csv")
    @login_required
    def export_csv():
        readings = (
            ExposureReading.query.join(Worker)
            .order_by(ExposureReading.timestamp.desc())
            .all()
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Reading ID",
            "Timestamp (UTC)",
            "Employee Code",
            "Worker Name",
            "Department",
            "Work Zone",
            "Predicted Exposure Class",
            "Confidence Score",
            "Est PPM Low",
            "Est PPM High",
            "Hour of Day",
        ])

        for r in readings:
            w = r.worker
            writer.writerow([
                r.id,
                r.timestamp.isoformat(),
                w.employee_code if w else "N/A",
                w.full_name if w else "N/A",
                w.department if w else "",
                w.work_zone if w else "",
                r.predicted_class,
                f"{(r.confidence or 0.95):.4f}",
                r.ppm_estimate_low,
                r.ppm_estimate_high or "None",
                r.hour_of_day,
            ])

        output.seek(0)
        filename = f"h2s_exposure_audit_{date.today().strftime('%Y%m%d')}.csv"
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"},
        )

    # ---------------------------------------------------------- ATTENDANCE
    @app.route("/attendance", methods=["GET", "POST"])
    @login_required
    def attendance():
        if request.method == "POST" and current_user.role == "admin":
            worker_id = request.form.get("worker_id")
            action = request.form.get("action")
            today = date.today()
            record = Attendance.query.filter_by(
                worker_id=worker_id, work_date=today
            ).first()
            if not record:
                record = Attendance(worker_id=worker_id, work_date=today)
                db.session.add(record)

            if action == "check_in":
                record.check_in = datetime.utcnow()
                record.status = "present"
            elif action == "check_out":
                record.check_out = datetime.utcnow()
            elif action == "absent":
                record.status = "absent"

            db.session.commit()
            flash("Personnel attendance registry updated.", "success")
            return redirect(url_for("attendance"))

        workers = Worker.query.all()
        today = date.today()
        records = {
            r.worker_id: r
            for r in Attendance.query.filter_by(work_date=today).all()
        }
        return render_template(
            "attendance.html", workers=workers, records=records, today=today
        )

    @app.route("/api/attendance/quick", methods=["POST"])
    @login_required
    def api_attendance_quick():
        if current_user.role != "admin":
            return jsonify({"success": False, "error": "Admin required"}), 403

        worker_id = request.form.get("worker_id")
        action = request.form.get("action")
        today = date.today()

        record = Attendance.query.filter_by(
            worker_id=worker_id, work_date=today
        ).first()
        if not record:
            record = Attendance(worker_id=worker_id, work_date=today)
            db.session.add(record)

        if action == "check_in":
            record.check_in = datetime.utcnow()
            record.status = "present"
        elif action == "check_out":
            record.check_out = datetime.utcnow()
        elif action == "absent":
            record.status = "absent"

        db.session.commit()
        worker = Worker.query.get(worker_id)
        return jsonify({
            "success": True,
            "worker_name": worker.full_name if worker else "",
            "status": record.status,
        })

    @app.route("/api/attendance/qr-scan", methods=["POST"])
    @login_required
    def api_attendance_qr_scan():
        """Process QR badge scan from plant kiosk camera or mobile device."""
        if current_user.role != "admin":
            return jsonify({"success": False, "error": "Safety Officer authorization required"}), 403

        data = request.get_json(silent=True) or request.form
        qr_payload = data.get("qr_data") or data.get("code") or data.get("employee_code", "")
        qr_payload = str(qr_payload).strip()

        if not qr_payload:
            return jsonify({"success": False, "error": "No QR badge data detected"}), 400

        # Extract target code (supports raw code, JSON payload, or prefixed 'H2S:EMP-101')
        target_code = qr_payload
        if qr_payload.startswith("{") and qr_payload.endswith("}"):
            try:
                parsed = json.loads(qr_payload)
                target_code = parsed.get("code") or parsed.get("employee_code") or qr_payload
            except Exception:
                pass
        elif ":" in qr_payload:
            target_code = qr_payload.split(":")[-1].strip()

        worker = Worker.query.filter(
            db.or_(
                Worker.employee_code.ilike(target_code),
                Worker.employee_code.ilike(qr_payload),
                Worker.full_name.ilike(target_code)
            )
        ).first()

        if not worker:
            return jsonify({
                "success": False,
                "error": f"Worker code '{target_code}' not found in registered roster."
            }), 404

        today = date.today()
        record = Attendance.query.filter_by(
            worker_id=worker.id, work_date=today
        ).first()

        now = datetime.utcnow()
        req_action = data.get("action", "auto")
        action_performed = "check_in"

        if not record:
            record = Attendance(
                worker_id=worker.id,
                work_date=today,
                check_in=now,
                status="present"
            )
            db.session.add(record)
            action_performed = "check_in"
        else:
            if req_action == "check_out" or (req_action == "auto" and record.check_in and not record.check_out):
                record.check_out = now
                action_performed = "check_out"
            else:
                record.check_in = now
                record.status = "present"
                action_performed = "check_in"

        db.session.commit()

        return jsonify({
            "success": True,
            "action": action_performed,
            "timestamp": now.strftime("%H:%M"),
            "status": record.status,
            "worker_code": worker.employee_code,
            "worker_name": worker.full_name,
            "worker": {
                "id": worker.id,
                "full_name": worker.full_name,
                "employee_code": worker.employee_code,
                "department": worker.department or "Operations",
                "work_zone": worker.work_zone or "General",
            },
            "message": f"Successfully {'checked in' if action_performed == 'check_in' else 'checked out'} {worker.full_name} ({worker.employee_code})"
        })

    # ------------------------------------------------------------- WORKERS
    @app.route("/workers", methods=["GET", "POST"])
    @login_required
    @admin_required
    def workers():
        if request.method == "POST":
            username = request.form.get("username").strip()
            password = request.form.get("password")
            full_name = request.form.get("full_name").strip()
            employee_code = request.form.get("employee_code").strip()
            department = request.form.get("department", "").strip()
            work_zone = request.form.get("work_zone", "").strip()

            if User.query.filter_by(username=username).first():
                flash("Username already exists.", "error")
                return redirect(url_for("workers"))

            user = User(username=username, role="worker")
            user.set_password(password)
            db.session.add(user)
            db.session.flush()

            worker = Worker(
                user_id=user.id,
                employee_code=employee_code,
                full_name=full_name,
                department=department,
                work_zone=work_zone,
            )
            db.session.add(worker)
            db.session.commit()
            flash(f"Enrolled {full_name} ({employee_code}).", "success")
            return redirect(url_for("workers"))

        all_workers = Worker.query.all()
        return render_template("workers.html", workers=all_workers)

    @app.route("/workers/<int:worker_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def delete_worker(worker_id):
        worker = Worker.query.get_or_404(worker_id)
        name = worker.full_name
        code = worker.employee_code
        user = worker.user

        db.session.delete(worker)
        if user:
            db.session.delete(user)
        db.session.commit()

        flash(f"Worker {name} ({code}) and associated records deleted.", "success")
        return redirect(url_for("workers"))

    @app.route("/api/workers/<int:worker_id>/delete", methods=["DELETE", "POST"])
    @login_required
    @admin_required
    def api_delete_worker(worker_id):
        worker = Worker.query.get(worker_id)
        if not worker:
            return jsonify({"success": False, "error": "Worker not found"}), 404

        name = worker.full_name
        code = worker.employee_code
        user = worker.user

        db.session.delete(worker)
        if user:
            db.session.delete(user)
        db.session.commit()

        return jsonify({
            "success": True,
            "message": f"Worker {name} ({code}) removed.",
            "worker_id": worker_id,
        })

    return app


app = create_app()


def init_admin():
    """Ensure initial admin account exists if no admin is present."""
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()
        print("[Init] Created initial safety officer account -> admin / admin123")


# Initialize DB on load (essential for Gunicorn / Render)
with app.app_context():
    db.create_all()
    init_admin()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"[SentryH2S] Server starting on http://0.0.0.0:{port}")
    app.run(debug=True, host="0.0.0.0", port=port)
