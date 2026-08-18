import json
import os
import urllib.error
import urllib.request

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib.parse import quote, quote_plus
from uuid import uuid4

from dateutil.relativedelta import relativedelta

from flask import (
    Blueprint,
    Flask,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from flask_sqlalchemy import SQLAlchemy

from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)

from werkzeug.utils import secure_filename


# =========================================================
# APPLICATION CONFIGURATION
# =========================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = "autocare-ai-secret-key"

mysql_password = quote_plus("akhi@123")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"mysql+pymysql://root:{mysql_password}"
    "@localhost:3306/autocare_ai"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static",
    "uploads",
)

app.config["INVOICE_UPLOAD_FOLDER"] = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "invoices",
)

app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


# =========================================================
# DATABASE
# =========================================================

db = SQLAlchemy(app)


# =========================================================
# LOGIN MANAGER
# =========================================================

login_manager = LoginManager(app)

login_manager.login_view = "login"
login_manager.login_message = "Please log in first."
login_manager.login_message_category = "warning"


# =========================================================
# ALLOWED FILE TYPES
# =========================================================

ALLOWED_IMAGE_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp",
}

ALLOWED_INVOICE_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
}


# =========================================================
# DATABASE MODELS
# =========================================================

class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    full_name = db.Column(
        db.String(100),
        nullable=False,
    )

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
        default=datetime.utcnow,
        nullable=False,
    )

    vehicles = db.relationship(
        "Vehicle",
        back_populates="owner",
        cascade="all, delete-orphan",
        lazy=True,
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

    registration_number = db.Column(
        db.String(30),
        unique=True,
        nullable=False,
    )

    vehicle_type = db.Column(
        db.String(30),
        nullable=False,
    )

    fuel_type = db.Column(
        db.String(30),
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

    vehicle_image = db.Column(
        db.String(255),
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    owner = db.relationship(
        "User",
        back_populates="vehicles",
    )

    service_records = db.relationship(
        "ServiceRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy=True,
    )

    fuel_records = db.relationship(
        "FuelRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy=True,
    )

    component_records = db.relationship(
        "ComponentRecord",
        back_populates="vehicle",
        cascade="all, delete-orphan",
        lazy=True,
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
        nullable=False,
    )

    invoice_file = db.Column(
        db.String(255),
        nullable=True,
    )

    notes = db.Column(
        db.Text,
        nullable=True,
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="service_records",
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
        default=datetime.utcnow,
        nullable=False,
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
        default=datetime.utcnow,
        nullable=False,
    )

    vehicle = db.relationship(
        "Vehicle",
        back_populates="component_records",
    )

    service_record = db.relationship(
        "ServiceRecord",
        backref=db.backref(
            "component_records",
            lazy=True,
            cascade="all, delete-orphan",
        ),
        single_parent=True,
    )


# =========================================================
# USER LOADER
# =========================================================

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(
        User,
        int(user_id),
    )


# =========================================================
# FILE HELPERS
# =========================================================

def allowed_image(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_IMAGE_EXTENSIONS
    )


def allowed_invoice(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_INVOICE_EXTENSIONS
    )


def save_uploaded_file(
    uploaded_file,
    upload_folder,
    validation_function,
):
    if not uploaded_file or not uploaded_file.filename:
        return None

    if not validation_function(uploaded_file.filename):
        return None

    safe_name = secure_filename(
        uploaded_file.filename
    )

    extension = safe_name.rsplit(
        ".",
        1,
    )[1].lower()

    filename = f"{uuid4().hex}.{extension}"

    os.makedirs(
        upload_folder,
        exist_ok=True,
    )

    uploaded_file.save(
        os.path.join(
            upload_folder,
            filename,
        )
    )

    return filename


# =========================================================
# HUNTER 350 SERVICE SCHEDULE
# =========================================================

HUNTER_350_SERVICE_SCHEDULE = [
    {
        "number": 1,
        "name": "First Service",
        "km": 500,
        "months": 1.5,
    },
    {
        "number": 2,
        "name": "Second Service",
        "km": 5000,
        "months": 6,
    },
    {
        "number": 3,
        "name": "Third Service",
        "km": 10000,
        "months": 12,
    },
    {
        "number": 4,
        "name": "Fourth Service",
        "km": 15000,
        "months": 18,
    },
    {
        "number": 5,
        "name": "Fifth Service",
        "km": 20000,
        "months": 24,
    },
    {
        "number": 6,
        "name": "Sixth Service",
        "km": 25000,
        "months": 30,
    },
    {
        "number": 7,
        "name": "Seventh Service",
        "km": 30000,
        "months": 36,
    },
    {
        "number": 8,
        "name": "Eighth Service",
        "km": 35000,
        "months": 42,
    },
    {
        "number": 9,
        "name": "Ninth Service",
        "km": 40000,
        "months": 48,
    },
    {
        "number": 10,
        "name": "Tenth Service",
        "km": 45000,
        "months": 54,
    },
    {
        "number": 11,
        "name": "Eleventh Service",
        "km": 50000,
        "months": 60,
    },
]


COMPONENT_LIFE_KM = {
    "engine_oil": 5000,
    "oil_filter": 10000,
    "air_filter": 12000,
    "front_brake_pad": 18000,
    "rear_brake_pad": 20000,
    "chain_sprocket": 20000,
    "spark_plug": 15000,
    "battery": 30000,
    "tyre_front": 25000,
    "tyre_rear": 20000,
    "coolant": 20000,
    "clutch_plate": 30000,
}


COMPONENT_DISPLAY_NAMES = {
    "engine_oil": "Engine Oil",
    "oil_filter": "Oil Filter",
    "air_filter": "Air Filter",
    "front_brake_pad": "Front Brake Pad",
    "rear_brake_pad": "Rear Brake Pad",
    "chain_sprocket": "Chain and Sprocket",
    "spark_plug": "Spark Plug",
    "battery": "Battery",
    "tyre_front": "Front Tyre",
    "tyre_rear": "Rear Tyre",
    "coolant": "Coolant",
    "clutch_plate": "Clutch Plate",
}



def normalize_text(value):
    if not value:
        return ""

    return value.strip().lower()


def calculate_service_date(
    purchase_date,
    months,
):
    whole_months = int(months)

    service_date = purchase_date + relativedelta(
        months=whole_months
    )

    if months != whole_months:
        service_date += relativedelta(
            days=15
        )

    return service_date


def predict_next_service(vehicle):
    company = normalize_text(
        vehicle.company
    )

    vehicle_name = normalize_text(
        vehicle.vehicle_name
    )

    model = normalize_text(
        vehicle.model
    )

    is_hunter_350 = (
        company == "royal enfield"
        and (
            "hunter 350" in vehicle_name
            or "hunter 350" in model
            or vehicle_name == "hunter"
            or model == "hunter"
        )
    )

    if not is_hunter_350:
        return {
            "supported": False,
            "message": (
                "Official service schedule is not "
                "available for this vehicle yet."
            ),
        }

    current_odometer = vehicle.odometer or 0
    today = date.today()

    for service in HUNTER_350_SERVICE_SCHEDULE:
        service_date = None

        if vehicle.purchase_date:
            service_date = calculate_service_date(
                vehicle.purchase_date,
                service["months"],
            )

        distance_reached = (
            current_odometer >= service["km"]
        )

        time_reached = (
            service_date is not None
            and today >= service_date
        )

        if not distance_reached and not time_reached:
            remaining_days = None

            if service_date:
                remaining_days = (
                    service_date - today
                ).days

            return {
                "supported": True,
                "service_number": service["number"],
                "service_name": service["name"],
                "service_km": service["km"],
                "service_date": service_date,
                "remaining_km": max(
                    service["km"] - current_odometer,
                    0,
                ),
                "remaining_days": remaining_days,
                "is_overdue": False,
            }

    return {
        "supported": True,
        "service_number": None,
        "service_name": "Service overdue",
        "service_km": 50000,
        "service_date": None,
        "remaining_km": 0,
        "remaining_days": 0,
        "is_overdue": True,
    }


# =========================================================
# MAIN ROUTES
# =========================================================

@app.route("/")
def home():
    return render_template(
        "index.html"
    )


@app.route(
    "/register",
    methods=["GET", "POST"],
)
def register():
    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.dashboard")
        )

    if request.method == "POST":
        full_name = request.form.get(
            "full_name",
            "",
        ).strip()

        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        password = request.form.get(
            "password",
            "",
        )

        confirm_password = request.form.get(
            "confirm_password",
            "",
        )

        if not all([
            full_name,
            email,
            password,
            confirm_password,
        ]):
            flash(
                "All fields are required.",
                "danger",
            )

            return render_template(
                "auth/register.html"
            )

        if len(password) < 6:
            flash(
                "Password must contain at least 6 characters.",
                "danger",
            )

            return render_template(
                "auth/register.html"
            )

        if password != confirm_password:
            flash(
                "Passwords do not match.",
                "danger",
            )

            return render_template(
                "auth/register.html"
            )

        existing_user = User.query.filter_by(
            email=email
        ).first()

        if existing_user:
            flash(
                "Email is already registered.",
                "warning",
            )

            return render_template(
                "auth/register.html"
            )

        user = User(
            full_name=full_name,
            email=email,
        )

        user.set_password(
            password
        )

        db.session.add(
            user
        )

        db.session.commit()

        flash(
            "Registration successful. Please log in.",
            "success",
        )

        return redirect(
            url_for("login")
        )

    return render_template(
        "auth/register.html"
    )


@app.route(
    "/login",
    methods=["GET", "POST"],
)
def login():
    if current_user.is_authenticated:
        return redirect(
            url_for("dashboard.dashboard")
        )

    if request.method == "POST":
        email = request.form.get(
            "email",
            "",
        ).strip().lower()

        password = request.form.get(
            "password",
            "",
        )

        user = User.query.filter_by(
            email=email
        ).first()

        if user and user.check_password(
            password
        ):
            login_user(
                user
            )

            flash(
                "Login successful.",
                "success",
            )

            return redirect(
                url_for("home")
            )

        flash(
            "Invalid email or password.",
            "danger",
        )

    return render_template(
        "auth/login.html"
    )


@app.route("/logout")
@login_required
def logout():
    logout_user()

    flash(
        "You have been logged out.",
        "success",
    )

    return redirect(
        url_for("login")
    )


@app.route("/offline")
def offline():
    return render_template(
        "offline.html"
    )


@app.route("/service-worker.js")
def service_worker():
    return send_from_directory(
        "static",
        "service-worker.js",
        mimetype="application/javascript",
    )


# =========================================================
# ONLINE VEHICLE CATALOGUE API
# =========================================================

VPIC_BASE_URL = (
    "https://vpic.nhtsa.dot.gov/api/vehicles"
)


def fetch_vpic_json(endpoint):
    url = (
        f"{VPIC_BASE_URL}/{endpoint}"
    )

    request_object = urllib.request.Request(
        url,
        headers={
            "User-Agent": (
                "AutoCareAI/1.0 "
                "(student vehicle-maintenance project)"
            ),
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(
            request_object,
            timeout=15,
        ) as response:
            payload = response.read().decode(
                "utf-8"
            )

        return json.loads(
            payload
        )

    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        app.logger.warning(
            "Vehicle catalogue request failed: %s",
            error,
        )

        return None


def map_catalog_vehicle_type(vehicle_type):
    vehicle_type = normalize_text(
        vehicle_type
    )

    if vehicle_type in {
        "bike",
        "motorcycle",
        "scooter",
    }:
        return "motorcycle"

    if vehicle_type in {
        "car",
        "passenger car",
    }:
        return "passenger car"

    return vehicle_type or "vehicle"


@app.route("/api/vehicle-makes")
@login_required
def api_vehicle_makes():
    vehicle_type = request.args.get(
        "vehicle_type",
        "Car",
    )

    vpic_type = map_catalog_vehicle_type(
        vehicle_type
    )

    endpoint = (
        "GetMakesForVehicleType/"
        f"{quote(vpic_type)}"
        "?format=json"
    )

    payload = fetch_vpic_json(
        endpoint
    )

    if not payload:
        return jsonify({
            "success": False,
            "message": (
                "Online vehicle catalogue is "
                "temporarily unavailable."
            ),
            "makes": [],
        }), 503

    makes = {}

    for item in payload.get("Results", []):
        make_name = (
            item.get("MakeName")
            or item.get("Make_Name")
            or ""
        ).strip()

        make_id = (
            item.get("MakeId")
            or item.get("Make_ID")
        )

        if make_name:
            makes[make_name.casefold()] = {
                "id": make_id,
                "name": make_name,
            }

    sorted_makes = sorted(
        makes.values(),
        key=lambda item: item["name"].casefold(),
    )

    return jsonify({
        "success": True,
        "makes": sorted_makes,
    })


@app.route("/api/vehicle-models")
@login_required
def api_vehicle_models():
    make = request.args.get(
        "make",
        "",
    ).strip()

    year = request.args.get(
        "year",
        "",
    ).strip()

    vehicle_type = request.args.get(
        "vehicle_type",
        "",
    ).strip()

    if not make:
        return jsonify({
            "success": False,
            "message": "Manufacturer is required.",
            "models": [],
        }), 400

    encoded_make = quote(
        make
    )

    if year.isdigit() and int(year) > 1995:
        endpoint = (
            "GetModelsForMakeYear/"
            f"make/{encoded_make}/"
            f"modelyear/{year}"
        )

        if vehicle_type:
            endpoint += (
                "/vehicletype/"
                f"{quote(map_catalog_vehicle_type(vehicle_type))}"
            )

        endpoint += "?format=json"

    else:
        endpoint = (
            "GetModelsForMake/"
            f"{encoded_make}"
            "?format=json"
        )

    payload = fetch_vpic_json(
        endpoint
    )

    if not payload:
        return jsonify({
            "success": False,
            "message": (
                "Online vehicle catalogue is "
                "temporarily unavailable."
            ),
            "models": [],
        }), 503

    models = {}

    for item in payload.get("Results", []):
        model_name = (
            item.get("Model_Name")
            or item.get("ModelName")
            or ""
        ).strip()

        model_id = (
            item.get("Model_ID")
            or item.get("ModelId")
        )

        if model_name:
            models[model_name.casefold()] = {
                "id": model_id,
                "name": model_name,
            }

    sorted_models = sorted(
        models.values(),
        key=lambda item: item["name"].casefold(),
    )

    return jsonify({
        "success": True,
        "models": sorted_models,
    })


@app.route("/api/decode-vin")
@login_required
def api_decode_vin():
    vin = request.args.get(
        "vin",
        "",
    ).strip().upper()

    model_year = request.args.get(
        "year",
        "",
    ).strip()

    if len(vin) < 5:
        return jsonify({
            "success": False,
            "message": "Enter a valid VIN.",
        }), 400

    endpoint = (
        "DecodeVinValuesExtended/"
        f"{quote(vin)}"
        "?format=json"
    )

    if model_year.isdigit():
        endpoint += (
            f"&modelyear={model_year}"
        )

    payload = fetch_vpic_json(
        endpoint
    )

    if not payload:
        return jsonify({
            "success": False,
            "message": (
                "VIN service is temporarily "
                "unavailable."
            ),
        }), 503

    results = payload.get(
        "Results",
        [],
    )

    if not results:
        return jsonify({
            "success": False,
            "message": (
                "No vehicle information was found."
            ),
        }), 404

    result = results[0]

    details = {
        "make": result.get("Make") or "",
        "model": result.get("Model") or "",
        "year": result.get("ModelYear") or "",
        "vehicle_type": (
            result.get("VehicleType")
            or result.get("BodyClass")
            or ""
        ),
        "fuel_type": (
            result.get("FuelTypePrimary")
            or ""
        ),
        "engine_cc": (
            result.get("DisplacementCC")
            or ""
        ),
        "engine_cylinders": (
            result.get("EngineCylinders")
            or ""
        ),
        "transmission": (
            result.get("TransmissionStyle")
            or ""
        ),
        "drive_type": (
            result.get("DriveType")
            or ""
        ),
        "body_class": (
            result.get("BodyClass")
            or ""
        ),
        "manufacturer": (
            result.get("Manufacturer")
            or ""
        ),
        "plant_country": (
            result.get("PlantCountry")
            or ""
        ),
    }

    return jsonify({
        "success": True,
        "details": details,
    })


# =========================================================
# DASHBOARD BLUEPRINT
# =========================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
)


@dashboard_bp.route("/dashboard")
@login_required
def dashboard():
    vehicles = Vehicle.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Vehicle.created_at.desc()
    ).all()

    vehicle_predictions = []

    for vehicle in vehicles:
        prediction = predict_next_service(
            vehicle
        )

        total_service_cost = sum(
            float(record.total_cost or 0)
            for record in vehicle.service_records
        )

        vehicle_predictions.append({
            "vehicle": vehicle,
            "prediction": prediction,
            "total_service_cost": total_service_cost,
        })

    return render_template(
        "dashboard/dashboard.html",
        user=current_user,
        vehicles=vehicles,
        vehicle_predictions=vehicle_predictions,
    )


# =========================================================
# VEHICLE BLUEPRINT
# =========================================================

vehicle_bp = Blueprint(
    "vehicle",
    __name__,
    url_prefix="/vehicles",
)


@vehicle_bp.route(
    "/add",
    methods=["GET", "POST"],
)
@login_required
def add_vehicle():
    if request.method == "POST":
        vehicle_name = request.form.get(
            "vehicle_name",
            "",
        ).strip()

        company = request.form.get(
            "company",
            "",
        ).strip()

        model = request.form.get(
            "model",
            "",
        ).strip()

        registration_number = request.form.get(
            "registration_number",
            "",
        ).strip().upper()

        vehicle_type = request.form.get(
            "vehicle_type",
            "",
        ).strip()

        fuel_type = request.form.get(
            "fuel_type",
            "",
        ).strip()

        purchase_date_value = request.form.get(
            "purchase_date",
            "",
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "0",
        ).strip()

        if not all([
            vehicle_name,
            company,
            model,
            registration_number,
            vehicle_type,
            fuel_type,
        ]):
            flash(
                "Complete all required fields.",
                "danger",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        existing_vehicle = Vehicle.query.filter_by(
            registration_number=registration_number
        ).first()

        if existing_vehicle:
            flash(
                "This registration number already exists.",
                "warning",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        try:
            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        purchase_date = None

        if purchase_date_value:
            try:
                purchase_date = datetime.strptime(
                    purchase_date_value,
                    "%Y-%m-%d",
                ).date()

            except ValueError:
                flash(
                    "Enter a valid purchase date.",
                    "danger",
                )

                return render_template(
                    "vehicle/add_vehicle.html"
                )

        image_filename = None

        vehicle_image = request.files.get(
            "vehicle_image"
        )

        if vehicle_image and vehicle_image.filename:
            if not allowed_image(
                vehicle_image.filename
            ):
                flash(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "danger",
                )

                return render_template(
                    "vehicle/add_vehicle.html"
                )

            image_filename = save_uploaded_file(
                vehicle_image,
                current_app.config["UPLOAD_FOLDER"],
                allowed_image,
            )

        vehicle = Vehicle(
            user_id=current_user.id,
            vehicle_name=vehicle_name,
            company=company,
            model=model,
            registration_number=registration_number,
            vehicle_type=vehicle_type,
            fuel_type=fuel_type,
            purchase_date=purchase_date,
            odometer=odometer,
            vehicle_image=image_filename,
        )

        db.session.add(
            vehicle
        )

        db.session.commit()

        flash(
            "Vehicle added successfully.",
            "success",
        )

        return redirect(
            url_for("dashboard.dashboard")
        )

    return render_template(
        "vehicle/add_vehicle.html"
    )



@vehicle_bp.route(
    "/edit/<int:vehicle_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_vehicle(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        vehicle_name = request.form.get(
            "vehicle_name",
            "",
        ).strip()

        company = request.form.get(
            "company",
            "",
        ).strip()

        model = request.form.get(
            "model",
            "",
        ).strip()

        registration_number = request.form.get(
            "registration_number",
            "",
        ).strip().upper()

        vehicle_type = request.form.get(
            "vehicle_type",
            "",
        ).strip()

        fuel_type = request.form.get(
            "fuel_type",
            "",
        ).strip()

        purchase_date_value = request.form.get(
            "purchase_date",
            "",
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "0",
        ).strip()

        if not all([
            vehicle_name,
            company,
            model,
            registration_number,
            vehicle_type,
            fuel_type,
        ]):
            flash(
                "Complete all required fields.",
                "danger",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=vehicle,
            )

        duplicate_vehicle = (
            Vehicle.query
            .filter(
                Vehicle.registration_number
                == registration_number,
                Vehicle.id != vehicle.id,
            )
            .first()
        )

        if duplicate_vehicle:
            flash(
                "Another vehicle already uses this registration number.",
                "warning",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=vehicle,
            )

        try:
            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=vehicle,
            )

        purchase_date = None

        if purchase_date_value:
            try:
                purchase_date = datetime.strptime(
                    purchase_date_value,
                    "%Y-%m-%d",
                ).date()

            except ValueError:
                flash(
                    "Enter a valid purchase date.",
                    "danger",
                )

                return render_template(
                    "vehicle/edit_vehicle.html",
                    vehicle=vehicle,
                )

        vehicle_image = request.files.get(
            "vehicle_image"
        )

        if vehicle_image and vehicle_image.filename:
            if not allowed_image(
                vehicle_image.filename
            ):
                flash(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "danger",
                )

                return render_template(
                    "vehicle/edit_vehicle.html",
                    vehicle=vehicle,
                )

            old_image = vehicle.vehicle_image

            new_image_filename = save_uploaded_file(
                vehicle_image,
                current_app.config["UPLOAD_FOLDER"],
                allowed_image,
            )

            vehicle.vehicle_image = new_image_filename

            if old_image:
                old_image_path = os.path.join(
                    current_app.config["UPLOAD_FOLDER"],
                    old_image,
                )

                try:
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)

                except OSError:
                    current_app.logger.warning(
                        "Unable to remove old vehicle image: %s",
                        old_image_path,
                    )

        vehicle.vehicle_name = vehicle_name
        vehicle.company = company
        vehicle.model = model
        vehicle.registration_number = registration_number
        vehicle.vehicle_type = vehicle_type
        vehicle.fuel_type = fuel_type
        vehicle.purchase_date = purchase_date
        vehicle.odometer = odometer

        db.session.commit()

        flash(
            "Vehicle updated successfully.",
            "success",
        )

        return redirect(
            url_for("dashboard.dashboard")
        )

    return render_template(
        "vehicle/edit_vehicle.html",
        vehicle=vehicle,
    )


@vehicle_bp.route(
    "/delete/<int:vehicle_id>",
    methods=["POST"],
)
@login_required
def delete_vehicle(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    image_filename = vehicle.vehicle_image

    db.session.delete(
        vehicle
    )

    db.session.commit()

    if image_filename:
        image_path = os.path.join(
            current_app.config["UPLOAD_FOLDER"],
            image_filename,
        )

        try:
            if os.path.exists(image_path):
                os.remove(image_path)

        except OSError:
            current_app.logger.warning(
                "Unable to remove deleted vehicle image: %s",
                image_path,
            )

    flash(
        "Vehicle and its related records were deleted successfully.",
        "success",
    )

    return redirect(
        url_for("dashboard.dashboard")
    )


@app.route("/add-vehicle")
@login_required
def old_add_vehicle():
    return redirect(
        url_for("vehicle.add_vehicle")
    )


# =========================================================
# SERVICE BLUEPRINT
# =========================================================

service_bp = Blueprint(
    "service",
    __name__,
    url_prefix="/service",
)


@service_bp.route(
    "/add/<int:vehicle_id>",
    methods=["GET", "POST"],
)
@login_required
def add_service(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        service_date_value = request.form.get(
            "service_date",
            "",
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "",
        ).strip()

        service_type = request.form.get(
            "service_type",
            "",
        ).strip()

        service_center = request.form.get(
            "service_center",
            "",
        ).strip()

        work_done = request.form.get(
            "work_done",
            "",
        ).strip()

        engine_oil = request.form.get(
            "engine_oil",
            "",
        ).strip()

        total_cost_value = request.form.get(
            "total_cost",
            "0",
        ).strip()

        notes = request.form.get(
            "notes",
            "",
        ).strip()

        if not all([
            service_date_value,
            odometer_value,
            service_type,
        ]):
            flash(
                "Service date, odometer and service type are required.",
                "danger",
            )

            return render_template(
                "service/add_service.html",
                vehicle=vehicle,
            )

        try:
            service_date = datetime.strptime(
                service_date_value,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            flash(
                "Enter a valid service date.",
                "danger",
            )

            return render_template(
                "service/add_service.html",
                vehicle=vehicle,
            )

        try:
            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger",
            )

            return render_template(
                "service/add_service.html",
                vehicle=vehicle,
            )

        try:
            total_cost = Decimal(
                total_cost_value or "0"
            )

            if total_cost < 0:
                raise InvalidOperation

        except (
            InvalidOperation,
            ValueError,
        ):
            flash(
                "Enter a valid service cost.",
                "danger",
            )

            return render_template(
                "service/add_service.html",
                vehicle=vehicle,
            )

        invoice_filename = None

        invoice_file = request.files.get(
            "invoice_file"
        )

        if invoice_file and invoice_file.filename:
            if not allowed_invoice(
                invoice_file.filename
            ):
                flash(
                    "Invoice must be PDF, PNG, JPG or JPEG.",
                    "danger",
                )

                return render_template(
                    "service/add_service.html",
                    vehicle=vehicle,
                )

            invoice_filename = save_uploaded_file(
                invoice_file,
                current_app.config[
                    "INVOICE_UPLOAD_FOLDER"
                ],
                allowed_invoice,
            )

        service_record = ServiceRecord(
            vehicle_id=vehicle.id,
            service_date=service_date,
            odometer=odometer,
            service_type=service_type,
            service_center=service_center or None,
            work_done=work_done or None,
            engine_oil=engine_oil or None,
            total_cost=total_cost,
            invoice_file=invoice_filename,
            notes=notes or None,
        )

        db.session.add(
            service_record
        )

        if odometer > vehicle.odometer:
            vehicle.odometer = odometer

        db.session.commit()

        flash(
            "Service record saved successfully.",
            "success",
        )

        return redirect(
            url_for(
                "service.service_history",
                vehicle_id=vehicle.id,
            )
        )

    return render_template(
        "service/add_service.html",
        vehicle=vehicle,
    )


@service_bp.route(
    "/history/<int:vehicle_id>"
)
@login_required
def service_history(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    records = ServiceRecord.query.filter_by(
        vehicle_id=vehicle.id
    ).order_by(
        ServiceRecord.service_date.desc(),
        ServiceRecord.created_at.desc(),
    ).all()

    total_spent = sum(
        float(record.total_cost or 0)
        for record in records
    )

    prediction = predict_next_service(
        vehicle
    )

    return render_template(
        "service/history.html",
        vehicle=vehicle,
        records=records,
        total_spent=total_spent,
        prediction=prediction,
    )


# =========================================================
# FUEL BLUEPRINT
# =========================================================

fuel_bp = Blueprint(
    "fuel",
    __name__,
    url_prefix="/fuel",
)


def calculate_fuel_statistics(records):
    total_litres = sum(
        float(record.litres or 0)
        for record in records
    )

    total_amount = sum(
        float(record.total_amount or 0)
        for record in records
    )

    for record in records:
        record.distance_travelled = None
        record.calculated_mileage = None
        record.cost_per_km = None

    sorted_records = sorted(
        records,
        key=lambda record: (
            record.odometer,
            record.refill_date,
            record.id,
        ),
    )

    mileage_entries = []

    for index in range(1, len(sorted_records)):
        previous_record = sorted_records[index - 1]
        current_record = sorted_records[index]

        distance = (
            current_record.odometer
            - previous_record.odometer
        )

        litres_used = float(
            current_record.litres or 0
        )

        amount_paid = float(
            current_record.total_amount or 0
        )

        if distance > 0 and litres_used > 0:
            mileage = distance / litres_used
            cost_per_km = amount_paid / distance

            current_record.distance_travelled = distance
            current_record.calculated_mileage = mileage
            current_record.cost_per_km = cost_per_km

            mileage_entries.append(mileage)

    average_mileage = 0

    if mileage_entries:
        average_mileage = (
            sum(mileage_entries)
            / len(mileage_entries)
        )

    return {
        "total_litres": total_litres,
        "total_amount": total_amount,
        "average_mileage": average_mileage,
        "record_count": len(records),
    }


@fuel_bp.route(
    "/add/<int:vehicle_id>",
    methods=["GET", "POST"],
)
@login_required
def add_fuel(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        refill_date_value = request.form.get(
            "refill_date",
            "",
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "",
        ).strip()

        price_per_litre_value = request.form.get(
            "price_per_litre",
            "",
        ).strip()

        total_amount_value = request.form.get(
            "total_amount",
            "",
        ).strip()

        fuel_station = request.form.get(
            "fuel_station",
            "",
        ).strip()

        notes = request.form.get(
            "notes",
            "",
        ).strip()

        full_tank = (
            request.form.get("full_tank")
            == "on"
        )

        if not all([
            refill_date_value,
            odometer_value,
            price_per_litre_value,
            total_amount_value,
        ]):
            flash(
                "Date, odometer, price per litre and amount are required.",
                "danger",
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle,
            )

        try:
            refill_date = datetime.strptime(
                refill_date_value,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            flash(
                "Enter a valid refill date.",
                "danger",
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle,
            )

        try:
            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger",
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle,
            )

        try:
            price_per_litre = Decimal(
                price_per_litre_value
            )

            total_amount = Decimal(
                total_amount_value
            )

            if price_per_litre <= 0 or total_amount <= 0:
                raise InvalidOperation

            litres = (
                total_amount
                / price_per_litre
            )

        except (
            InvalidOperation,
            ValueError,
            ZeroDivisionError,
        ):
            flash(
                "Enter a valid fuel price and total amount.",
                "danger",
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle,
            )

        latest_record = (
            FuelRecord.query
            .filter_by(vehicle_id=vehicle.id)
            .order_by(
                FuelRecord.odometer.desc(),
                FuelRecord.refill_date.desc(),
            )
            .first()
        )

        if latest_record and odometer < latest_record.odometer:
            flash(
                "Odometer cannot be lower than the previous fuel entry.",
                "danger",
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle,
            )

        fuel_record = FuelRecord(
            vehicle_id=vehicle.id,
            refill_date=refill_date,
            odometer=odometer,
            litres=litres,
            total_amount=total_amount,
            price_per_litre=price_per_litre,
            fuel_station=fuel_station or None,
            full_tank=full_tank,
            notes=notes or None,
        )

        db.session.add(
            fuel_record
        )

        if odometer > vehicle.odometer:
            vehicle.odometer = odometer

        db.session.commit()

        flash(
            "Fuel record added successfully.",
            "success",
        )

        return redirect(
            url_for(
                "fuel.fuel_history",
                vehicle_id=vehicle.id,
            )
        )

    return render_template(
        "fuel/add_fuel.html",
        vehicle=vehicle,
    )


@fuel_bp.route(
    "/history/<int:vehicle_id>"
)
@login_required
def fuel_history(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    records = (
        FuelRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            FuelRecord.refill_date.desc(),
            FuelRecord.odometer.desc(),
            FuelRecord.id.desc(),
        )
        .all()
    )

    statistics = calculate_fuel_statistics(
        records
    )

    return render_template(
        "fuel/history.html",
        vehicle=vehicle,
        records=records,
        statistics=statistics,
    )



@fuel_bp.route(
    "/edit/<int:fuel_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_fuel(fuel_id):
    fuel_record = (
        FuelRecord.query
        .join(Vehicle)
        .filter(
            FuelRecord.id == fuel_id,
            Vehicle.user_id == current_user.id,
        )
        .first_or_404()
    )

    vehicle = fuel_record.vehicle

    if request.method == "POST":
        refill_date_value = request.form.get(
            "refill_date",
            "",
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "",
        ).strip()

        price_per_litre_value = request.form.get(
            "price_per_litre",
            "",
        ).strip()

        total_amount_value = request.form.get(
            "total_amount",
            "",
        ).strip()

        fuel_station = request.form.get(
            "fuel_station",
            "",
        ).strip()

        notes = request.form.get(
            "notes",
            "",
        ).strip()

        full_tank = (
            request.form.get("full_tank")
            == "on"
        )

        if not all([
            refill_date_value,
            odometer_value,
            price_per_litre_value,
            total_amount_value,
        ]):
            flash(
                "Date, odometer, price per litre and amount are required.",
                "danger",
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record,
            )

        try:
            refill_date = datetime.strptime(
                refill_date_value,
                "%Y-%m-%d",
            ).date()

        except ValueError:
            flash(
                "Enter a valid refill date.",
                "danger",
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record,
            )

        try:
            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger",
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record,
            )

        try:
            price_per_litre = Decimal(
                price_per_litre_value
            )

            total_amount = Decimal(
                total_amount_value
            )

            if price_per_litre <= 0 or total_amount <= 0:
                raise InvalidOperation

            litres = (
                total_amount
                / price_per_litre
            )

        except (
            InvalidOperation,
            ValueError,
            ZeroDivisionError,
        ):
            flash(
                "Enter a valid fuel price and total amount.",
                "danger",
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record,
            )

        other_records = (
            FuelRecord.query
            .filter(
                FuelRecord.vehicle_id == vehicle.id,
                FuelRecord.id != fuel_record.id,
            )
            .order_by(
                FuelRecord.odometer.asc(),
                FuelRecord.refill_date.asc(),
            )
            .all()
        )

        lower_records = [
            record
            for record in other_records
            if record.refill_date <= refill_date
        ]

        upper_records = [
            record
            for record in other_records
            if record.refill_date >= refill_date
        ]

        if lower_records:
            previous_record = max(
                lower_records,
                key=lambda record: (
                    record.refill_date,
                    record.odometer,
                ),
            )

            if odometer < previous_record.odometer:
                flash(
                    "Odometer cannot be lower than the previous fuel entry.",
                    "danger",
                )

                return render_template(
                    "fuel/edit_fuel.html",
                    vehicle=vehicle,
                    fuel_record=fuel_record,
                )

        if upper_records:
            next_record = min(
                upper_records,
                key=lambda record: (
                    record.refill_date,
                    record.odometer,
                ),
            )

            if odometer > next_record.odometer:
                flash(
                    "Odometer cannot be higher than the next fuel entry.",
                    "danger",
                )

                return render_template(
                    "fuel/edit_fuel.html",
                    vehicle=vehicle,
                    fuel_record=fuel_record,
                )

        fuel_record.refill_date = refill_date
        fuel_record.odometer = odometer
        fuel_record.litres = litres
        fuel_record.total_amount = total_amount
        fuel_record.price_per_litre = price_per_litre
        fuel_record.fuel_station = fuel_station or None
        fuel_record.full_tank = full_tank
        fuel_record.notes = notes or None

        highest_odometer = (
            db.session.query(
                db.func.max(FuelRecord.odometer)
            )
            .filter(
                FuelRecord.vehicle_id == vehicle.id
            )
            .scalar()
        )

        vehicle.odometer = max(
            highest_odometer or 0,
            odometer,
        )

        db.session.commit()

        flash(
            "Fuel record updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "fuel.fuel_history",
                vehicle_id=vehicle.id,
            )
        )

    return render_template(
        "fuel/edit_fuel.html",
        vehicle=vehicle,
        fuel_record=fuel_record,
    )


@fuel_bp.route(
    "/delete/<int:fuel_id>",
    methods=["POST"],
)
@login_required
def delete_fuel(fuel_id):
    fuel_record = (
        FuelRecord.query
        .join(Vehicle)
        .filter(
            FuelRecord.id == fuel_id,
            Vehicle.user_id == current_user.id,
        )
        .first_or_404()
    )

    vehicle = fuel_record.vehicle
    vehicle_id = vehicle.id

    db.session.delete(
        fuel_record
    )

    db.session.flush()

    highest_fuel_odometer = (
        db.session.query(
            db.func.max(FuelRecord.odometer)
        )
        .filter(
            FuelRecord.vehicle_id == vehicle_id
        )
        .scalar()
    )

    highest_service_odometer = (
        db.session.query(
            db.func.max(ServiceRecord.odometer)
        )
        .filter(
            ServiceRecord.vehicle_id == vehicle_id
        )
        .scalar()
    )

    vehicle.odometer = max(
        highest_fuel_odometer or 0,
        highest_service_odometer or 0,
        vehicle.odometer or 0,
    )

    db.session.commit()

    flash(
        "Fuel record deleted successfully.",
        "success",
    )

    return redirect(
        url_for(
            "fuel.fuel_history",
            vehicle_id=vehicle_id,
        )
    )



@fuel_bp.route(
    "/analytics/<int:vehicle_id>"
)
@login_required
def fuel_analytics(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    records = (
        FuelRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            FuelRecord.refill_date.asc(),
            FuelRecord.odometer.asc(),
            FuelRecord.id.asc(),
        )
        .all()
    )

    statistics = calculate_fuel_statistics(
        records
    )

    valid_distances = [
        record.distance_travelled
        for record in records
        if record.distance_travelled
    ]

    valid_mileages = [
        record.calculated_mileage
        for record in records
        if record.calculated_mileage
    ]

    total_distance = (
        sum(valid_distances)
        if valid_distances
        else 0
    )

    cost_per_km = 0

    if total_distance > 0:
        cost_per_km = (
            statistics["total_amount"]
            / total_distance
        )

    best_mileage = (
        max(valid_mileages)
        if valid_mileages
        else 0
    )

    amounts = [
        float(record.total_amount or 0)
        for record in records
    ]

    prices = [
        float(record.price_per_litre or 0)
        for record in records
        if record.price_per_litre
    ]

    highest_bill = (
        max(amounts)
        if amounts
        else 0
    )

    lowest_bill = (
        min(amounts)
        if amounts
        else 0
    )

    cheapest_price = (
        min(prices)
        if prices
        else 0
    )

    highest_price = (
        max(prices)
        if prices
        else 0
    )

    monthly_totals = {}

    for record in records:
        month_key = record.refill_date.strftime(
            "%b %Y"
        )

        monthly_totals.setdefault(
            month_key,
            {
                "amount": 0,
                "litres": 0,
            },
        )

        monthly_totals[month_key]["amount"] += float(
            record.total_amount or 0
        )

        monthly_totals[month_key]["litres"] += float(
            record.litres or 0
        )

    chart_labels = list(
        monthly_totals.keys()
    )

    monthly_spending = [
        round(
            monthly_totals[label]["amount"],
            2,
        )
        for label in chart_labels
    ]

    monthly_litres = [
        round(
            monthly_totals[label]["litres"],
            2,
        )
        for label in chart_labels
    ]

    mileage_labels = []
    mileage_values = []

    for record in records:
        if record.calculated_mileage:
            mileage_labels.append(
                record.refill_date.strftime(
                    "%d %b"
                )
            )

            mileage_values.append(
                round(
                    record.calculated_mileage,
                    2,
                )
            )

    refill_labels = [
        record.refill_date.strftime(
            "%d %b"
        )
        for record in records
    ]

    refill_litres = [
        round(
            float(record.litres or 0),
            2,
        )
        for record in records
    ]

    recent_record = (
        records[-1]
        if records
        else None
    )

    return render_template(
        "fuel/analytics.html",
        vehicle=vehicle,
        statistics=statistics,
        total_distance=total_distance,
        cost_per_km=cost_per_km,
        best_mileage=best_mileage,
        highest_bill=highest_bill,
        lowest_bill=lowest_bill,
        cheapest_price=cheapest_price,
        highest_price=highest_price,
        recent_record=recent_record,
        chart_labels=chart_labels,
        monthly_spending=monthly_spending,
        monthly_litres=monthly_litres,
        mileage_labels=mileage_labels,
        mileage_values=mileage_values,
        refill_labels=refill_labels,
        refill_litres=refill_litres,
    )



def get_latest_component_record(
    vehicle,
    component_names,
):
    normalized_names = {
        normalize_text(name)
        for name in component_names
    }

    matching_records = [
        record
        for record in vehicle.component_records
        if normalize_text(
            record.component_name
        ) in normalized_names
    ]

    if not matching_records:
        return None

    return max(
        matching_records,
        key=lambda record: (
            record.service_date,
            record.odometer,
            record.id,
        ),
    )


def calculate_component_status(
    vehicle,
    component_key,
    label,
    expected_life_km,
    component_names,
    default_last_km=0,
    inspect_interval_km=None,
):
    current_odometer = int(
        vehicle.odometer or 0
    )

    latest_record = get_latest_component_record(
        vehicle,
        component_names,
    )

    if latest_record:
        last_service_km = int(
            latest_record.odometer or 0
        )

        last_service_date = (
            latest_record.service_date
        )

        last_action = (
            latest_record.action
            or "Recorded"
        )

    else:
        last_service_km = int(
            default_last_km or 0
        )

        last_service_date = None
        last_action = "No component record"

    used_km = max(
        current_odometer - last_service_km,
        0,
    )

    remaining_km = max(
        expected_life_km - used_km,
        0,
    )

    remaining_percent = max(
        min(
            round(
                (
                    remaining_km
                    / expected_life_km
                ) * 100
            ),
            100,
        ),
        0,
    )

    if remaining_percent <= 10:
        status = "Due"
        level = "danger"

        recommendation = (
            f"{label} has reached its estimated "
            "replacement or inspection limit."
        )

    elif remaining_percent <= 30:
        status = "Attention soon"
        level = "warning"

        recommendation = (
            f"Inspect {label.lower()} soon. "
            f"Estimated {remaining_km} km remaining."
        )

    else:
        status = "Healthy"
        level = "success"

        recommendation = (
            f"No urgent issue detected. "
            f"Estimated {remaining_km} km remaining."
        )

    next_inspection_km = None

    if inspect_interval_km:
        completed_intervals = (
            current_odometer
            // inspect_interval_km
        )

        next_inspection_km = (
            completed_intervals + 1
        ) * inspect_interval_km

        inspection_remaining = max(
            next_inspection_km
            - current_odometer,
            0,
        )

        if inspection_remaining <= 100:
            recommendation = (
                f"Inspect {label.lower()} within "
                f"{inspection_remaining} km."
            )

            if level == "success":
                level = "warning"
                status = "Inspection due soon"

    return {
        "key": component_key,
        "label": label,
        "health": remaining_percent,
        "status": status,
        "level": level,
        "used_km": used_km,
        "remaining_km": remaining_km,
        "expected_life_km": expected_life_km,
        "last_service_km": last_service_km,
        "last_service_date": last_service_date,
        "last_action": last_action,
        "next_inspection_km": next_inspection_km,
        "recommendation": recommendation,
    }


def build_digital_twin_components(
    vehicle,
):
    is_bike = normalize_text(
        vehicle.vehicle_type
    ) in {
        "bike",
        "motorcycle",
        "scooter",
    }

    components = {
        "engine": calculate_component_status(
            vehicle=vehicle,
            component_key="engine",
            label="Engine",
            expected_life_km=50000,
            component_names={
                "engine",
                "engine service",
                "engine repair",
            },
            inspect_interval_km=5000,
        ),
        "battery": calculate_component_status(
            vehicle=vehicle,
            component_key="battery",
            label="Battery",
            expected_life_km=COMPONENT_LIFE_KM[
                "battery"
            ],
            component_names={
                "battery",
            },
            inspect_interval_km=5000,
        ),
        "front_brake": calculate_component_status(
            vehicle=vehicle,
            component_key="front_brake",
            label="Front Brake Pad",
            expected_life_km=COMPONENT_LIFE_KM[
                "front_brake_pad"
            ],
            component_names={
                "front brake pad",
                "front brake",
                "brake pad front",
            },
            inspect_interval_km=5000,
        ),
        "rear_brake": calculate_component_status(
            vehicle=vehicle,
            component_key="rear_brake",
            label="Rear Brake Pad",
            expected_life_km=COMPONENT_LIFE_KM[
                "rear_brake_pad"
            ],
            component_names={
                "rear brake pad",
                "rear brake",
                "brake pad rear",
            },
            inspect_interval_km=5000,
        ),
        "front_tyre": calculate_component_status(
            vehicle=vehicle,
            component_key="front_tyre",
            label="Front Tyre",
            expected_life_km=COMPONENT_LIFE_KM[
                "tyre_front"
            ],
            component_names={
                "front tyre",
                "tyre front",
                "front tire",
            },
            inspect_interval_km=5000,
        ),
        "rear_tyre": calculate_component_status(
            vehicle=vehicle,
            component_key="rear_tyre",
            label="Rear Tyre",
            expected_life_km=COMPONENT_LIFE_KM[
                "tyre_rear"
            ],
            component_names={
                "rear tyre",
                "tyre rear",
                "rear tire",
            },
            inspect_interval_km=5000,
        ),
        "suspension": calculate_component_status(
            vehicle=vehicle,
            component_key="suspension",
            label="Suspension",
            expected_life_km=30000,
            component_names={
                "suspension",
                "front suspension",
                "rear suspension",
                "fork oil",
            },
            inspect_interval_km=10000,
        ),
        "lights": calculate_component_status(
            vehicle=vehicle,
            component_key="lights",
            label="Lights",
            expected_life_km=30000,
            component_names={
                "lights",
                "headlight",
                "tail light",
                "indicator",
            },
            inspect_interval_km=5000,
        ),
    }

    if is_bike:
        components["chain"] = (
            calculate_component_status(
                vehicle=vehicle,
                component_key="chain",
                label="Chain and Sprocket",
                expected_life_km=COMPONENT_LIFE_KM[
                    "chain_sprocket"
                ],
                component_names={
                    "chain",
                    "chain and sprocket",
                    "chain sprocket",
                    "drive chain",
                },
                inspect_interval_km=500,
            )
        )

    return components


# =========================================================
# SMART GARAGE ROUTE
# =========================================================

@app.route("/garage/<int:vehicle_id>")
@login_required
def garage(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    prediction = predict_next_service(vehicle)

    service_records = (
        ServiceRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(ServiceRecord.service_date.desc())
        .all()
    )

    total_cost = sum(
        float(record.total_cost or 0)
        for record in service_records
    )

    service_count = len(service_records)

    digital_twin_components = (
        build_digital_twin_components(
            vehicle
        )
    )

    health_score = 95

    if prediction.get("is_overdue", False):
        health_score -= 25

    if service_count == 0:
        health_score -= 10

    health_score = max(
        min(health_score, 100),
        0,
    )

    return render_template(
        "garage/garage.html",
        vehicle=vehicle,
        prediction=prediction,
        service_records=service_records,
        total_cost=total_cost,
        service_count=service_count,
        health_score=health_score,
        digital_twin_components=(
            digital_twin_components
        ),
    )


# =========================================================
# REGISTER BLUEPRINTS
# =========================================================

app.register_blueprint(
    dashboard_bp
)

app.register_blueprint(
    vehicle_bp
)

app.register_blueprint(
    service_bp
)

app.register_blueprint(
    fuel_bp
)


# =========================================================
# CREATE FOLDERS AND DATABASE TABLES
# =========================================================

with app.app_context():
    os.makedirs(
        app.config["UPLOAD_FOLDER"],
        exist_ok=True,
    )

    os.makedirs(
        app.config["INVOICE_UPLOAD_FOLDER"],
        exist_ok=True,
    )

    db.create_all()


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":
    print("RUNNING FILE:", __file__)
    print("PROJECT ROOT:", app.root_path)

    app.run(
        debug=True,
        use_reloader=False,
    )