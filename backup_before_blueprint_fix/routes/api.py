from flask import Blueprint, jsonify, request, current_app
from flask_login import login_required, current_user
from urllib.parse import quote
import urllib.request
import urllib.error
import json
from extensions import csrf, db
from models import Reminder
from helpers import normalize_text

api = Blueprint('api', __name__, url_prefix='/api')

VPIC_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

def fetch_vpic_json(endpoint):
    url = f"{VPIC_BASE_URL}/{endpoint}"
    request_object = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AutoCareAI/1.0 (student vehicle-maintenance project)",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request_object, timeout=15) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload)
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
    ) as error:
        current_app.logger.warning("Vehicle catalogue request failed: %s", error)
        return None

def map_catalog_vehicle_type(vehicle_type):
    vehicle_type = normalize_text(vehicle_type)
    if vehicle_type in {"bike", "motorcycle", "scooter"}:
        return "motorcycle"
    if vehicle_type in {"car", "passenger car"}:
        return "passenger car"
    return vehicle_type or "vehicle"

@api.route("/vehicle-makes")
@login_required
@csrf.exempt
def api_vehicle_makes():
    vehicle_type = request.args.get("vehicle_type", "Car")
    vpic_type = map_catalog_vehicle_type(vehicle_type)
    endpoint = f"GetMakesForVehicleType/{quote(vpic_type)}?format=json"
    
    payload = fetch_vpic_json(endpoint)
    if not payload:
        return jsonify({
            "success": False,
            "message": "Online vehicle catalogue is temporarily unavailable.",
            "makes": [],
        }), 503

    makes = {}
    for item in payload.get("Results", []):
        make_name = (item.get("MakeName") or item.get("Make_Name") or "").strip()
        make_id = item.get("MakeId") or item.get("Make_ID")
        if make_name:
            makes[make_name.casefold()] = {
                "id": make_id,
                "name": make_name,
            }

    sorted_makes = sorted(makes.values(), key=lambda item: item["name"].casefold())
    return jsonify({
        "success": True,
        "makes": sorted_makes,
    })

@api.route("/vehicle-models")
@login_required
@csrf.exempt
def api_vehicle_models():
    make = request.args.get("make", "").strip()
    year = request.args.get("year", "").strip()
    vehicle_type = request.args.get("vehicle_type", "").strip()

    if not make:
        return jsonify({
            "success": False,
            "message": "Manufacturer is required.",
            "models": [],
        }), 400

    encoded_make = quote(make)

    if year.isdigit() and int(year) > 1995:
        endpoint = f"GetModelsForMakeYear/make/{encoded_make}/modelyear/{year}"
        if vehicle_type:
            endpoint += f"/vehicletype/{quote(map_catalog_vehicle_type(vehicle_type))}"
        endpoint += "?format=json"
    else:
        endpoint = f"GetModelsForMake/{encoded_make}?format=json"

    payload = fetch_vpic_json(endpoint)
    if not payload:
        return jsonify({
            "success": False,
            "message": "Online vehicle catalogue is temporarily unavailable.",
            "models": [],
        }), 503

    models = {}
    for item in payload.get("Results", []):
        model_name = (item.get("Model_Name") or item.get("ModelName") or "").strip()
        model_id = item.get("Model_ID") or item.get("ModelId")
        if model_name:
            models[model_name.casefold()] = {
                "id": model_id,
                "name": model_name,
            }

    sorted_models = sorted(models.values(), key=lambda item: item["name"].casefold())
    return jsonify({
        "success": True,
        "models": sorted_models,
    })

@api.route("/decode-vin")
@login_required
@csrf.exempt
def api_decode_vin():
    vin = request.args.get("vin", "").strip().upper()
    model_year = request.args.get("year", "").strip()

    if len(vin) < 5:
        return jsonify({
            "success": False,
            "message": "Enter a valid VIN.",
        }), 400

    endpoint = f"DecodeVinValuesExtended/{quote(vin)}?format=json"
    if model_year.isdigit():
        endpoint += f"&modelyear={model_year}"

    payload = fetch_vpic_json(endpoint)
    if not payload:
        return jsonify({
            "success": False,
            "message": "VIN service is temporarily unavailable.",
        }), 503

    results = payload.get("Results", [])
    if not results:
        return jsonify({
            "success": False,
            "message": "No vehicle information was found.",
        }), 404

    result = results[0]
    details = {
        "make": result.get("Make") or "",
        "model": result.get("Model") or "",
        "year": result.get("ModelYear") or "",
        "vehicle_type": result.get("VehicleType") or result.get("BodyClass") or "",
        "fuel_type": result.get("FuelTypePrimary") or "",
        "engine_cc": result.get("DisplacementCC") or "",
        "engine_cylinders": result.get("EngineCylinders") or "",
        "transmission": result.get("TransmissionStyle") or "",
        "drive_type": result.get("DriveType") or "",
        "body_class": result.get("BodyClass") or "",
        "manufacturer": result.get("Manufacturer") or "",
        "plant_country": result.get("PlantCountry") or "",
    }
    return jsonify({
        "success": True,
        "details": details,
    })

@api.route("/reminders/dismiss/<int:reminder_id>", methods=["GET", "POST"])
@login_required
@csrf.exempt
def dismiss_reminder(reminder_id):
    reminder = Reminder.query.filter_by(id=reminder_id, user_id=current_user.id).first()
    if reminder:
        reminder.is_dismissed = True
        db.session.commit()
        return jsonify({"success": True})
    return jsonify({"success": False, "message": "Reminder not found"}), 404
