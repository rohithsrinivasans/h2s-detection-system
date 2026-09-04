import os
from datetime import datetime, date

from flask import (
    Flask, render_template, redirect, url_for, request, flash, jsonify, abort
)
from flask_login import (
    LoginManager, login_user, logout_user, login_required, current_user
)
from werkzeug.utils import secure_filename

from config import Config
from models.database_models import db, User, Worker, Attendance, ExposureReading
from models.predict import predict_exposure


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
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

    # ---------------------------------------------------------------- auth
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
                return redirect(url_for("dashboard"))
            flash("Invalid username or password.", "error")
        return render_template("login.html")

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        return redirect(url_for("login"))

    # ----------------------------------------------------------- dashboard
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
                .limit(15)
                .all()
            )
            high_alerts_today = (
                ExposureReading.query.filter(
                    db.func.date(ExposureReading.timestamp) == today,
                    ExposureReading.predicted_class.in_(["medium", "high"]),
                ).count()
            )
            return render_template(
                "dashboard.html",
                total_workers=total_workers,
                present_today=present_today,
                recent_readings=recent_readings,
                high_alerts_today=high_alerts_today,
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
                "dashboard.html", worker=worker, today_readings=today_readings
            )

    # ---------------------------------------------------------- attendance
    @app.route("/attendance", methods=["GET", "POST"])
    @login_required
    def attendance():
        if request.method == "POST" and current_user.role == "admin":
            worker_id = request.form.get("worker_id")
            action = request.form.get("action")  # check_in / check_out / absent
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
            flash("Attendance updated.", "success")
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

    # ------------------------------------------------------ exposure pages
    @app.route("/exposure", methods=["GET", "POST"])
    @login_required
    def exposure():
        if request.method == "POST":
            worker_id = request.form.get("worker_id")
            file = request.files.get("photo")

            if not worker_id:
                flash("Select a worker.", "error")
                return redirect(url_for("exposure"))
            if not file or file.filename == "" or not allowed_file(file.filename):
                flash("Upload a valid image (jpg/png) of the lead acetate paper.", "error")
                return redirect(url_for("exposure"))

            filename = secure_filename(
                f"{worker_id}_{int(datetime.utcnow().timestamp())}_{file.filename}"
            )
            save_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(save_path)

            result = predict_exposure(save_path)
            now = datetime.utcnow()

            reading = ExposureReading(
                worker_id=worker_id,
                timestamp=now,
                image_path=f"uploads/{filename}",
                predicted_class=result["predicted_class"],
                confidence=result["confidence"],
                ppm_estimate_low=result["ppm_estimate_low"],
                ppm_estimate_high=result["ppm_estimate_high"],
                hour_of_day=now.hour,
            )
            db.session.add(reading)
            db.session.commit()

            if result["predicted_class"] in ("medium", "high"):
                flash(
                    f"ALERT: {result['predicted_class'].upper()} H2S exposure "
                    f"detected (confidence {result['confidence']:.0%}). "
                    f"Notify the safety officer immediately.",
                    "alert",
                )
            else:
                flash(
                    f"Reading logged: {result['predicted_class']} "
                    f"(confidence {result['confidence']:.0%}).",
                    "success",
                )
            return redirect(url_for("exposure", worker_id=worker_id))

        workers = Worker.query.all()
        selected_worker_id = request.args.get("worker_id", type=int)
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

    @app.route("/api/worker/<int:worker_id>/hourly")
    @login_required
    def worker_hourly(worker_id):
        """Hour-wise exposure aggregation for today, used by the dashboard chart."""
        today = date.today()
        readings = (
            ExposureReading.query.filter(
                ExposureReading.worker_id == worker_id,
                db.func.date(ExposureReading.timestamp) == today,
            )
            .order_by(ExposureReading.timestamp.asc())
            .all()
        )
        by_hour = {h: None for h in range(24)}
        for r in readings:
            by_hour[r.hour_of_day] = r.to_dict()
        return jsonify(by_hour)

    # -------------------------------------------------------- worker admin
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
            db.session.flush()  # get user.id before commit

            worker = Worker(
                user_id=user.id,
                employee_code=employee_code,
                full_name=full_name,
                department=department,
                work_zone=work_zone,
            )
            db.session.add(worker)
            db.session.commit()
            flash(f"Worker {full_name} added.", "success")
            return redirect(url_for("workers"))

        all_workers = Worker.query.all()
        return render_template("workers.html", workers=all_workers)

    return app


app = create_app()


def seed_admin():
    """Create a default admin account on first run, if none exists."""
    if not User.query.filter_by(role="admin").first():
        admin = User(username="admin", role="admin")
        admin.set_password("admin123")  # CHANGE THIS after first login
        db.session.add(admin)
        db.session.commit()
        print("Created default admin -> username: admin / password: admin123")
        print("CHANGE THIS PASSWORD IMMEDIATELY.")


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_admin()
    app.run(debug=True, host="0.0.0.0", port=5000)
