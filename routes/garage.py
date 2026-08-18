from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    render_template,
    jsonify,
    request,
    flash,
    redirect,
    url_for,
)
from flask_login import login_required, current_user

from models import (
    Vehicle,
    ServiceRecord,
    FuelRecord,
    VehicleDocument,
)
from helpers import (
    predict_next_service,
    get_insurance_status,
    get_puc_status,
    get_vehicle_twin_data,
)
from extensions import db


garage_bp = Blueprint("garage", __name__)


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _status_value(status):
    """
    Convert insurance/PUC helper output to a simple lowercase status
    for internal comparisons, while still allowing the original helper
    value to be passed to templates unchanged.
    """
    if isinstance(status, dict):
        value = (
            status.get("status")
            or status.get("state")
            or status.get("value")
            or ""
        )
        return str(value).strip().lower()

    return str(status or "").strip().lower()


def _extract_digital_twin_components(twin_data):
    """
    Safely extract the component dictionary from get_vehicle_twin_data().
    Supports several common response shapes.
    """
    if not isinstance(twin_data, dict):
        return {}

    components = twin_data.get("digital_twin_components")
    if isinstance(components, dict):
        return components

    components = twin_data.get("components")
    if isinstance(components, dict):
        return components

    # If the helper itself already returns the component mapping.
    component_like_keys = {
        "engine",
        "battery",
        "front_brake",
        "rear_brake",
        "front_tyre",
        "rear_tyre",
        "chain",
        "suspension",
        "lights",
    }

    if any(key in twin_data for key in component_like_keys):
        return twin_data

    return {}


def _calculate_health_score(
    prediction,
    service_count,
    insurance_status,
    puc_status,
):
    """Calculate the overall vehicle-health score used by the garage."""
    score = 95

    if (prediction or {}).get("is_overdue", False):
        score -= 25

    if service_count == 0:
        score -= 10

    if _status_value(insurance_status) == "expired":
        score -= 15

    if _status_value(puc_status) == "expired":
        score -= 15

    return max(min(score, 100), 0)


def _load_twin_data(vehicle):
    """Load digital-twin data without breaking the garage if it fails."""
    try:
        twin_data = get_vehicle_twin_data(vehicle) or {}

        if not isinstance(twin_data, dict):
            return {}

        return twin_data

    except Exception as error:
        print("Digital Twin Error:", error)
        return {}


# ============================================================
# GARAGE PAGE
# ============================================================

@garage_bp.route("/garage/<int:vehicle_id>")
@login_required
def garage(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    prediction = predict_next_service(vehicle) or {}

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

    fuel_records = (
        FuelRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            FuelRecord.refill_date.desc(),
            FuelRecord.odometer.desc(),
            FuelRecord.id.desc(),
        )
        .all()
    )

    insurance_status = get_insurance_status(vehicle)
    puc_status = get_puc_status(vehicle)

    health_score = _calculate_health_score(
        prediction,
        service_count,
        insurance_status,
        puc_status,
    )

    twin_data = _load_twin_data(vehicle)

    digital_twin_components = _extract_digital_twin_components(
        twin_data
    )

    return render_template(
        "garage/garage.html",
        vehicle=vehicle,
        prediction=prediction,
        service_records=service_records,
        total_cost=total_cost,
        service_count=service_count,
        health_score=health_score,
        insurance_status=insurance_status,
        puc_status=puc_status,
        fuel_records=fuel_records,
        twin_data=twin_data,
        digital_twin_components=digital_twin_components,
    )

# ============================================================
# AUTOCARE AI VEHICLE INSIGHT API
# ============================================================

@garage_bp.route("/api/vehicle-insight/<int:vehicle_id>")
@login_required
def vehicle_insight(vehicle_id):
    """
    Generate a vehicle-maintenance insight from the records already
    stored in AutoCare AI. This works locally without an external API key.
    """

    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    prediction = predict_next_service(vehicle) or {}

    service_records = (
        ServiceRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            ServiceRecord.service_date.desc(),
            ServiceRecord.id.desc(),
        )
        .all()
    )

    fuel_records = (
        FuelRecord.query
        .filter_by(vehicle_id=vehicle.id)
        .order_by(
            FuelRecord.refill_date.desc(),
            FuelRecord.odometer.desc(),
            FuelRecord.id.desc(),
        )
        .all()
    )

    insurance_status = get_insurance_status(vehicle)
    puc_status = get_puc_status(vehicle)

    insurance_value = _status_value(insurance_status)
    puc_value = _status_value(puc_status)

    health_score = _calculate_health_score(
        prediction,
        len(service_records),
        insurance_status,
        puc_status,
    )

    insights = []
    latest_mileage = None

    # --------------------------------------------------------
    # SERVICE PREDICTION
    # --------------------------------------------------------

    if prediction.get("supported"):
        if prediction.get("is_overdue"):
            insights.append(
                "Your scheduled service is overdue. "
                "Arrange maintenance as soon as possible."
            )
        else:
            remaining_km = prediction.get("remaining_km")
            service_km = prediction.get("service_km")
            service_name = prediction.get("service_name")

            if remaining_km is not None:
                try:
                    remaining_km = max(int(remaining_km), 0)

                    if remaining_km <= 500:
                        insights.append(
                            f"Your next service is very close: "
                            f"approximately {remaining_km:,} km remaining."
                        )
                    else:
                        insights.append(
                            f"Approximately {remaining_km:,} km remain "
                            f"before the next scheduled service."
                        )
                except (TypeError, ValueError):
                    pass

            elif service_km is not None:
                try:
                    insights.append(
                        f"Next scheduled service target: "
                        f"{int(service_km):,} km."
                    )
                except (TypeError, ValueError):
                    pass

            if service_name:
                insights.append(
                    f"Upcoming maintenance stage: {service_name}."
                )
    else:
        insights.append(
            "A manufacturer-specific service schedule is not "
            "available for this vehicle yet."
        )

    # --------------------------------------------------------
    # SERVICE HISTORY
    # --------------------------------------------------------

    if not service_records:
        insights.append(
            "No service history is saved. Add previous maintenance "
            "records to improve predictions."
        )
    else:
        latest_service = service_records[0]

        latest_date = (
            latest_service.service_date.strftime("%d %b %Y")
            if latest_service.service_date
            else "an unknown date"
        )

        insights.append(
            f"Latest recorded service: {latest_date} at "
            f"{int(latest_service.odometer or 0):,} km."
        )

        total_service_cost = sum(
            float(record.total_cost or 0)
            for record in service_records
        )

        if total_service_cost > 0:
            insights.append(
                f"Recorded maintenance spending is "
                f"₹{total_service_cost:,.2f}."
            )

    # --------------------------------------------------------
    # INSURANCE
    # --------------------------------------------------------

    if insurance_value == "expired":
        insights.append(
            "Insurance is marked as expired. Renew it before driving."
        )
    elif insurance_value in {
        "expiring_soon",
        "expiring soon",
        "due_soon",
        "due soon",
    }:
        insights.append(
            "Insurance is approaching expiry. Plan the renewal soon."
        )
    elif insurance_value in {"active", "valid"}:
        insights.append(
            "Insurance status is currently valid."
        )

    # --------------------------------------------------------
    # PUC
    # --------------------------------------------------------

    if puc_value == "expired":
        insights.append(
            "PUC is marked as expired. Renew the certificate soon."
        )
    elif puc_value in {
        "expiring_soon",
        "expiring soon",
        "due_soon",
        "due soon",
    }:
        insights.append(
            "PUC is approaching expiry. Plan the renewal soon."
        )
    elif puc_value in {"active", "valid"}:
        insights.append(
            "PUC status is currently valid."
        )

    # --------------------------------------------------------
    # FUEL / MILEAGE
    # --------------------------------------------------------

    if len(fuel_records) == 0:
        insights.append(
            "No fuel records are saved. Add refills to start "
            "tracking mileage and running cost."
        )

    elif len(fuel_records) == 1:
        insights.append(
            "One fuel refill is saved. Add another refill with a "
            "newer odometer reading to calculate mileage."
        )

    else:
        latest = fuel_records[0]
        previous = fuel_records[1]

        try:
            distance = (
                int(latest.odometer or 0)
                - int(previous.odometer or 0)
            )

            litres = float(latest.litres or 0)

            if distance > 0 and litres > 0:
                latest_mileage = distance / litres

                insights.append(
                    f"Latest estimated mileage is "
                    f"{latest_mileage:.1f} km/l over "
                    f"approximately {distance:,} km."
                )
            else:
                insights.append(
                    "More valid fuel entries are needed to calculate "
                    "the latest mileage."
                )

        except (TypeError, ValueError, AttributeError):
            insights.append(
                "Fuel records are available, but mileage could not "
                "be calculated from the saved values."
            )

    # --------------------------------------------------------
    # DIGITAL TWIN COMPONENT WARNINGS
    # --------------------------------------------------------

    twin_data = _load_twin_data(vehicle)
    components = _extract_digital_twin_components(twin_data)

    component_alerts = []

    for key, component in components.items():
        if not isinstance(component, dict):
            continue

        label = (
            component.get("label")
            or str(key).replace("_", " ").title()
        )

        level_value = str(
            component.get("level")
            or component.get("status")
            or ""
        ).strip().lower()

        try:
            component_health = float(component.get("health"))
        except (TypeError, ValueError):
            component_health = None

        needs_attention = (
            level_value in {
                "warning",
                "danger",
                "critical",
                "poor",
                "replace",
                "service",
            }
            or (
                component_health is not None
                and component_health < 65
            )
        )

        if needs_attention:
            recommendation = str(
                component.get("recommendation")
                or "Inspect this component."
            ).strip()

            component_alerts.append(
                f"{label}: {recommendation}"
            )

    if component_alerts:
        insights.extend(component_alerts[:3])

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    if health_score >= 85:
        level = "good"
        summary = (
            "Your vehicle appears to be in good condition based "
            "on the records currently available."
        )

    elif health_score >= 65:
        level = "warning"
        summary = (
            "Your vehicle is generally usable, but some maintenance "
            "or document items need attention."
        )

    else:
        level = "danger"
        summary = (
            "Your vehicle needs attention. Review overdue maintenance, "
            "documents and component condition."
        )

    return jsonify(
        {
            "success": True,
            "vehicle": vehicle.vehicle_name,
            "health_score": health_score,
            "level": level,
            "summary": summary,
            "latest_mileage": (
                round(latest_mileage, 1)
                if latest_mileage is not None
                else None
            ),
            "insights": insights,
        }
    )

# ============================================================
# VEHICLE DIGITAL TWIN PAGE
# ============================================================

@garage_bp.route("/vehicle-twin/<int:vehicle_id>")
@login_required
def vehicle_twin(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    twin_data = _load_twin_data(vehicle)

    digital_twin_components = _extract_digital_twin_components(
        twin_data
    )

    return render_template(
        "garage/vehicle_twin.html",
        vehicle=vehicle,
        twin_data=twin_data,
        digital_twin_components=digital_twin_components,
    )


# ============================================================
# VEHICLE DIGITAL TWIN API
# ============================================================

@garage_bp.route("/api/vehicle-twin-data/<int:vehicle_id>")
@login_required
def api_vehicle_twin_data(vehicle_id):
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    twin_data = _load_twin_data(vehicle)

    return jsonify(twin_data)


# ============================================================
# INSURANCE & PUC
# ============================================================

@garage_bp.route(
    "/insurance-puc/<int:vehicle_id>",
    methods=["GET", "POST"],
)
@login_required
def insurance_puc(vehicle_id):
    """
    Insurance & PUC management — registered under the garage blueprint
    so url_for('garage.insurance_puc', vehicle_id=...) works.
    """
    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        try:
            # ------------------------------------------------
            # INSURANCE
            # ------------------------------------------------

            vehicle.insurance_provider = (
                request.form.get(
                    "insurance_provider",
                    "",
                ).strip()
                or None
            )

            vehicle.insurance_policy_number = (
                request.form.get(
                    "insurance_policy_number",
                    "",
                ).strip()
                or None
            )

            start_date_str = request.form.get(
                "insurance_start_date",
                "",
            ).strip()

            if start_date_str:
                vehicle.insurance_start_date = datetime.strptime(
                    start_date_str,
                    "%Y-%m-%d",
                ).date()
            else:
                vehicle.insurance_start_date = None

            expiry_str = request.form.get(
                "insurance_expiry",
                "",
            ).strip()

            if expiry_str:
                vehicle.insurance_expiry = datetime.strptime(
                    expiry_str,
                    "%Y-%m-%d",
                ).date()
            else:
                vehicle.insurance_expiry = None

            premium_str = request.form.get(
                "insurance_premium",
                "",
            ).strip()

            if premium_str:
                premium = Decimal(premium_str)

                if premium < 0:
                    raise ValueError(
                        "Premium cannot be negative"
                    )

                vehicle.insurance_premium = premium
            else:
                vehicle.insurance_premium = None

            # ------------------------------------------------
            # PUC
            # ------------------------------------------------

            vehicle.puc_certificate_number = (
                request.form.get(
                    "puc_certificate_number",
                    "",
                ).strip()
                or None
            )

            puc_issue_str = request.form.get(
                "puc_issue_date",
                "",
            ).strip()

            if puc_issue_str:
                vehicle.puc_issue_date = datetime.strptime(
                    puc_issue_str,
                    "%Y-%m-%d",
                ).date()
            else:
                vehicle.puc_issue_date = None

            puc_expiry_str = request.form.get(
                "puc_expiry",
                "",
            ).strip()

            if puc_expiry_str:
                vehicle.puc_expiry = datetime.strptime(
                    puc_expiry_str,
                    "%Y-%m-%d",
                ).date()
            else:
                vehicle.puc_expiry = None

            db.session.commit()

            flash(
                "Insurance and PUC details updated successfully.",
                "success",
            )

            return redirect(
                url_for(
                    "garage.insurance_puc",
                    vehicle_id=vehicle.id,
                )
            )

        except (ValueError, InvalidOperation):
            db.session.rollback()

            flash(
                "Invalid data provided. Please check dates and numbers.",
                "danger",
            )

        except Exception as error:
            db.session.rollback()

            print(
                "Insurance / PUC Error:",
                error,
            )

            flash(
                "Unable to update insurance and PUC details.",
                "danger",
            )

    documents = (
        VehicleDocument.query
        .filter_by(vehicle_id=vehicle.id)
        .filter(
            VehicleDocument.document_type.in_(
                ["insurance", "puc"]
            )
        )
        .all()
    )

    return render_template(
        "garage/insurance_puc.html",
        vehicle=vehicle,
        documents=documents,
    )