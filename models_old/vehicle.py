from datetime import datetime

from models import db


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    vehicle_name = db.Column(
        db.String(100),
        nullable=False
    )

    company = db.Column(
        db.String(100),
        nullable=False
    )

    model = db.Column(
        db.String(100),
        nullable=False
    )

    registration_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    vehicle_type = db.Column(
        db.String(30),
        nullable=False
    )

    fuel_type = db.Column(
        db.String(30),
        nullable=False
    )

    purchase_date = db.Column(
        db.Date,
        nullable=True
    )

    odometer = db.Column(
        db.Integer,
        default=0,
        nullable=False
    )

    vehicle_image = db.Column(
        db.String(255),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
    service_records = db.relationship(
    "ServiceRecord",
    backref="vehicle",
    lazy=True,
    cascade="all, delete-orphan"
)