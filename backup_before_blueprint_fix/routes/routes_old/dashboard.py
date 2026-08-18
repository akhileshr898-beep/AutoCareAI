from flask import Blueprint, render_template
from flask_login import current_user, login_required

from models.vehicle import Vehicle
from services.service_predictor import predict_next_service


dashboard_bp = Blueprint(
    "dashboard",
    __name__
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
        prediction = predict_next_service(vehicle)

        vehicle_predictions.append({
            "vehicle": vehicle,
            "prediction": prediction
        })

    return render_template(
        "dashboard/dashboard.html",
        user=current_user,
        vehicles=vehicles,
        vehicle_predictions=vehicle_predictions
    )