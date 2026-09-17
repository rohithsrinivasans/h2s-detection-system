from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model, UserMixin):
    """Login account. role = 'admin' (safety officer) or 'worker'."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="worker")

    worker_profile = db.relationship(
        "Worker", backref="user", uselist=False, cascade="all, delete-orphan"
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f"<User {self.username} ({self.role})>"


class Worker(db.Model):
    """Worker profile tied to a login account."""

    __tablename__ = "workers"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    employee_code = db.Column(db.String(50), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    department = db.Column(db.String(100))
    work_zone = db.Column(db.String(100))  # e.g. "Sulfur Recovery Unit - Zone A"

    attendance_records = db.relationship(
        "Attendance", backref="worker", cascade="all, delete-orphan"
    )
    exposure_readings = db.relationship(
        "ExposureReading", backref="worker", cascade="all, delete-orphan"
    )

    def to_dict(self):
        return {
            "id": self.id,
            "employee_code": self.employee_code,
            "full_name": self.full_name,
            "department": self.department or "Operations",
            "work_zone": self.work_zone or "General",
        }

    def __repr__(self):
        return f"<Worker {self.employee_code} {self.full_name}>"


class Attendance(db.Model):
    """One row per worker per day."""

    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    work_date = db.Column(db.Date, nullable=False, default=date.today)
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    status = db.Column(db.String(20), default="present")  # present/absent/leave

    __table_args__ = (
        db.UniqueConstraint("worker_id", "work_date", name="uq_worker_date"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "work_date": self.work_date.isoformat() if self.work_date else None,
            "check_in": self.check_in.strftime("%H:%M") if self.check_in else None,
            "check_out": self.check_out.strftime("%H:%M") if self.check_out else None,
            "status": self.status,
        }


class ExposureReading(db.Model):
    """One row per lead-acetate-paper photo analyzed for a worker."""

    __tablename__ = "exposure_readings"

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey("workers.id"), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    image_path = db.Column(db.String(255))
    predicted_class = db.Column(db.String(20))  # no_exposure/low/medium/high
    confidence = db.Column(db.Float)
    ppm_estimate_low = db.Column(db.Float)
    ppm_estimate_high = db.Column(db.Float)
    hour_of_day = db.Column(db.Integer)  # 0-23, for hour-wise aggregation

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "predicted_class": self.predicted_class,
            "confidence": round(self.confidence, 3) if self.confidence else None,
            "ppm_estimate_low": self.ppm_estimate_low,
            "ppm_estimate_high": self.ppm_estimate_high,
            "hour_of_day": self.hour_of_day,
        }
