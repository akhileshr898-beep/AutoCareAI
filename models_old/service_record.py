from datetime import datetime

from models import db


class ServiceRecord(db.Model):
    __tablename__ = "service_records"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True
    )

    service_date = db.Column(
        db.Date,
        nullable=False
    )

    odometer = db.Column(
        db.Integer,
        nullable=False
    )

    service_type = db.Column(
        db.String(100),
        nullable=False
    )

    service_center = db.Column(
        db.String(150),
        nullable=True
    )

    work_done = db.Column(
        db.Text,
        nullable=True
    )

    engine_oil = db.Column(
        db.String(150),
        nullable=True
    )

    total_cost = db.Column(
        db.Numeric(10, 2),
        default=0,
        nullable=False
    )

    invoice_file = db.Column(
        db.String(255),
        nullable=True
    )

    notes = db.Column(
        db.Text,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )