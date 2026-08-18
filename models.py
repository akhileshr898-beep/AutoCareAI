from datetime import datetime, timezone, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db, login_manager


def utc_now():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(
        db.String(150),
        unique=True,
        nullable=False,
        index=True,
    )
    password_hash = db.Column(
        db.String(255),
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    vehicles = db.relationship(
        "Vehicle",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    reminders = db.relationship(
        "Reminder",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(
            password
        )

    def check_password(self, password):
        return check_password_hash(
            self.password_hash,
            password,
        )


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    vehicle_name = db.Column(
        db.String(100),
        nullable=False,
    )
    company = db.Column(
        db.String(100),
        nullable=False,
    )
    model = db.Column(
        db.String(100),
        nullable=False,
    )
    variant = db.Column(
        db.String(100),
        nullable=True,
    )
    vehicle_type = db.Column(
        db.String(30),
        nullable=False,
    )
    fuel_type = db.Column(
        db.String(30),
        nullable=False,
    )
    transmission = db.Column(
        db.String(30),
        nullable=True,
    )
    manufacturing_year = db.Column(
        db.Integer,
        nullable=True,
    )

    registration_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
    )

    purchase_date = db.Column(
        db.Date,
        nullable=True,
    )
    odometer = db.Column(
        db.Integer,
        default=0,
        nullable=False,
    )

    last_service_date = db.Column(
        db.Date,
        nullable=True,
    )
    last_service_odometer = db.Column(
        db.Integer,
        nullable=True,
    )
    avg_daily_km = db.Column(
        db.Integer,
        default=30,
    )
    service_interval_km = db.Column(
        db.Integer,
        default=5000,
    )
    service_interval_months = db.Column(
        db.Integer,
        default=6,
    )

    insurance_provider = db.Column(
        db.String(150),
        nullable=True,
    )
    insurance_policy_number = db.Column(
        db.String(100),
        nullable=True,
    )
    insurance_start_date = db.Column(
        db.Date,
        nullable=True,
    )
    insurance_expiry = db.Column(
        db.Date,
        nullable=True,
    )
    insurance_premium = db.Column(
        db.Numeric(10, 2),
        nullable=True,
    )

    puc_certificate_number = db.Column(
        db.String(100),
        nullable=True,
    )
    puc_issue_date = db.Column(
        db.Date,
        nullable=True,
    )
    puc_expiry = db.Column(
        db.Date,
        nullable=True,
    )

    vehicle_image = db.Column(
        db.String(255),
        nullable=True,
    )
    nickname = db.Column(
        db.String(100),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    owner = db.relationship(
        "User",
        back_populates="vehicles",
    )
    service_records = db.relationship(
        "ServiceRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    fuel_records = db.relationship(
        "FuelRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    component_records = db.relationship(
        "ComponentRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    documents = db.relationship(
        "VehicleDocument",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
    reminders = db.relationship(
        "Reminder",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )


class ServiceRecord(db.Model):
    __tablename__ = "service_records"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    service_date = db.Column(
        db.Date,
        nullable=False,
    )
    odometer = db.Column(
        db.Integer,
        nullable=False,
    )
    service_type = db.Column(
        db.String(100),
        nullable=False,
    )
    service_center = db.Column(
        db.String(150),
        nullable=True,
    )
    work_done = db.Column(
        db.Text,
        nullable=True,
    )
    engine_oil = db.Column(
        db.String(150),
        nullable=True,
    )
    total_cost = db.Column(
        db.Numeric(10, 2),
        default=0,
    )
    invoice_file = db.Column(
        db.String(255),
        nullable=True,
    )
    notes = db.Column(
        db.Text,
        nullable=True,
    )
    parts_replaced = db.Column(
        db.Text,
        nullable=True,
    )
    mechanic_notes = db.Column(
        db.Text,
        nullable=True,
    )
    next_service_date = db.Column(
        db.Date,
        nullable=True,
    )
    next_service_odometer = db.Column(
        db.Integer,
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="service_records",
    )
    component_records = db.relationship(
        "ComponentRecord",
        back_populates="service_record",
        cascade="all, delete-orphan",
    )


class FuelRecord(db.Model):
    __tablename__ = "fuel_records"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    refill_date = db.Column(
        db.Date,
        nullable=False,
    )
    odometer = db.Column(
        db.Integer,
        nullable=False,
    )
    litres = db.Column(
        db.Numeric(8, 2),
        nullable=False,
    )
    total_amount = db.Column(
        db.Numeric(10, 2),
        nullable=False,
    )
    price_per_litre = db.Column(
        db.Numeric(8, 2),
        nullable=True,
    )
    fuel_station = db.Column(
        db.String(150),
        nullable=True,
    )
    full_tank = db.Column(
        db.Boolean,
        default=True,
        nullable=False,
    )
    notes = db.Column(
        db.Text,
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="fuel_records",
    )


class ComponentRecord(db.Model):
    __tablename__ = "component_records"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    service_record_id = db.Column(
        db.Integer,
        db.ForeignKey("service_records.id"),
        nullable=True,
        index=True,
    )
    component_name = db.Column(
        db.String(100),
        nullable=False,
    )
    action = db.Column(
        db.String(30),
        nullable=False,
        default="replaced",
    )
    service_date = db.Column(
        db.Date,
        nullable=False,
    )
    odometer = db.Column(
        db.Integer,
        nullable=False,
    )
    expected_life_km = db.Column(
        db.Integer,
        nullable=False,
    )
    notes = db.Column(
        db.Text,
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="component_records",
    )
    service_record = db.relationship(
        "ServiceRecord",
        back_populates="component_records",
    )


class VehicleDocument(db.Model):
    __tablename__ = "vehicle_documents"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    document_type = db.Column(
        db.String(50),
        nullable=False,
    )
    document_name = db.Column(
        db.String(255),
        nullable=False,
    )
    file_data = db.Column(
        db.LargeBinary,
        nullable=True,
    )
    file_path = db.Column(
        db.String(255),
        nullable=True,
    )
    mime_type = db.Column(
        db.String(100),
        nullable=False,
    )
    file_size = db.Column(
        db.Integer,
        nullable=False,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="documents",
    )


class Reminder(db.Model):
    __tablename__ = "reminders"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    vehicle_id = db.Column(
        db.Integer,
        db.ForeignKey("vehicles.id"),
        nullable=False,
        index=True,
    )
    reminder_type = db.Column(
        db.String(50),
        nullable=False,
    )
    title = db.Column(
        db.String(200),
        nullable=False,
    )
    message = db.Column(
        db.Text,
        nullable=False,
    )
    is_read = db.Column(
        db.Boolean,
        default=False,
    )
    is_dismissed = db.Column(
        db.Boolean,
        default=False,
    )
    due_date = db.Column(
        db.Date,
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime,
        default=utc_now,
    )

    user = db.relationship(
        "User",
        back_populates="reminders",
    )
    vehicle = db.relationship(
        "Vehicle",
        back_populates="reminders",
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(
        User,
        int(user_id),
    )