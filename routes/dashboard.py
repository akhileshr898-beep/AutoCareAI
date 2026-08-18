from calendar import month_abbr
from datetime import date

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models import (
    Vehicle,
    ServiceRecord,
    FuelRecord,
    Reminder,
)

from helpers import (
    predict_next_service,
    get_insurance_status,
    get_puc_status,
    calculate_fuel_statistics,
    generate_reminders,
)


# ============================================================
# DASHBOARD BLUEPRINT
# ============================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
)


# ============================================================
# COMMON HELPERS
# ============================================================

def _to_float(value):
    """
    Safely convert Decimal / int / float / None to float.
    """
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value, default=0):
    """
    Safely convert a value to int.
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _status_value(status):
    """
    Normalize insurance / PUC helper responses.

    Supports:
        "expired"
        {"status": "expired"}
        {"state": "expired"}
        {"value": "expired"}
    """
    if isinstance(status, dict):
        status = (
            status.get("status")
            or status.get("state")
            or status.get("value")
            or status.get("label")
            or ""
        )

    return str(
        status or ""
    ).strip().lower()


def _shift_month(year, month, offset):
    """
    Shift a year/month pair by offset months.

    Example:
        2026, 1, -1 -> 2025, 12
    """
    month_index = (
        year * 12
        + month
        - 1
        + offset
    )

    shifted_year = (
        month_index // 12
    )

    shifted_month = (
        month_index % 12
        + 1
    )

    return (
        shifted_year,
        shifted_month,
    )


def _recent_months(count=6):
    """
    Return the most recent month buckets for charts.
    """
    today = date.today()

    months = []

    for offset in range(
        -(count - 1),
        1,
    ):
        year, month = _shift_month(
            today.year,
            today.month,
            offset,
        )

        months.append({
            "year": year,
            "month": month,
            "key": (
                year,
                month,
            ),
            "label": (
                f"{month_abbr[month]} "
                f"{str(year)[-2:]}"
            ),
        })

    return months


# ============================================================
# NORMALIZE SERVICE PREDICTION
# ============================================================

def normalize_prediction(
    vehicle,
    prediction,
):
    """
    Convert different helper response formats into the structure expected
    by dashboard.html.
    """

    prediction = (
        prediction
        if isinstance(
            prediction,
            dict,
        )
        else {}
    )

    current_km = _to_int(
        getattr(
            vehicle,
            "odometer",
            0,
        ),
        0,
    )

    default_interval = _to_int(
        getattr(
            vehicle,
            "service_interval_km",
            5000,
        ),
        5000,
    )

    if default_interval <= 0:
        default_interval = 5000

    # --------------------------------------------------------
    # Existing / old helper format
    # --------------------------------------------------------

    if "supported" in prediction:
        normalized = dict(
            prediction
        )

        normalized.setdefault(
            "supported",
            False,
        )

        normalized.setdefault(
            "is_overdue",
            False,
        )

        normalized.setdefault(
            "service_name",
            "Next Service",
        )

        service_km = _to_int(
            normalized.get(
                "service_km"
            ),
            0,
        )

        if service_km <= 0:
            service_km = (
                (
                    current_km
                    // default_interval
                )
                + 1
            ) * default_interval

        normalized[
            "service_km"
        ] = service_km

        if normalized.get(
            "remaining_km"
        ) is None:
            normalized[
                "remaining_km"
            ] = max(
                service_km
                - current_km,
                0,
            )

        normalized[
            "remaining_km"
        ] = max(
            _to_int(
                normalized.get(
                    "remaining_km"
                ),
                0,
            ),
            0,
        )

        normalized.setdefault(
            "remaining_days",
            None,
        )

        normalized.setdefault(
            "service_date",
            None,
        )

        normalized.setdefault(
            "tasks",
            [],
        )

        normalized.setdefault(
            "estimated_cost_min",
            0,
        )

        normalized.setdefault(
            "estimated_cost_max",
            0,
        )

        return normalized

    # --------------------------------------------------------
    # New helper format
    # --------------------------------------------------------

    status = str(
        prediction.get(
            "status",
            "unknown",
        )
        or "unknown"
    ).strip().lower()

    service_km = (
        prediction.get(
            "service_km"
        )
        or prediction.get(
            "next_service_odometer"
        )
        or prediction.get(
            "due_odometer"
        )
    )

    service_km = _to_int(
        service_km,
        0,
    )

    # If helper does not provide a km interval, build one from vehicle data.
    if service_km <= 0:
        service_km = (
            (
                current_km
                // default_interval
            )
            + 1
        ) * default_interval

    remaining_km = (
        prediction.get(
            "remaining_km"
        )
    )

    if remaining_km is None:
        remaining_km = max(
            service_km
            - current_km,
            0,
        )

    remaining_km = max(
        _to_int(
            remaining_km,
            0,
        ),
        0,
    )

    is_overdue = bool(
        status == "overdue"
        or prediction.get(
            "is_overdue",
            False,
        )
    )

    if is_overdue:
        remaining_km = 0

    service_date = (
        prediction.get(
            "service_date"
        )
        or prediction.get(
            "next_service_date"
        )
        or prediction.get(
            "due_date"
        )
    )

    service_name = (
        prediction.get(
            "service_name"
        )
        or prediction.get(
            "name"
        )
        or "Next Service"
    )

    supported = (
        status
        not in {
            "unknown",
            "unsupported",
            "unavailable",
        }
    )

    # We have a usable fallback schedule, so allow dashboard display.
    if service_km > 0:
        supported = True

    return {
        "supported": supported,
        "status": status,
        "is_overdue": is_overdue,
        "service_name": service_name,
        "service_km": service_km,
        "remaining_km": remaining_km,
        "remaining_days": (
            prediction.get(
                "remaining_days"
            )
        ),
        "service_date": (
            service_date
        ),
        "tasks": (
            prediction.get(
                "tasks",
                [],
            )
            or []
        ),
        "estimated_cost_min": (
            prediction.get(
                "estimated_cost_min",
                0,
            )
            or 0
        ),
        "estimated_cost_max": (
            prediction.get(
                "estimated_cost_max",
                0,
            )
            or 0
        ),
    }


# ============================================================
# VEHICLE HEALTH
# ============================================================

def calculate_dashboard_health(
    prediction,
    insurance_status="unknown",
    puc_status="unknown",
):
    """
    Calculate the health percentage shown on the dashboard.
    """

    if not prediction.get(
        "supported",
        False,
    ):
        score = 78

    elif prediction.get(
        "is_overdue",
        False,
    ):
        score = 65

    elif _to_int(
        prediction.get(
            "remaining_km"
        ),
        999999,
    ) <= 1000:
        score = 82

    else:
        score = 92

    insurance_value = (
        _status_value(
            insurance_status
        )
    )

    puc_value = (
        _status_value(
            puc_status
        )
    )

    if insurance_value == "expired":
        score -= 8

    if puc_value == "expired":
        score -= 8

    return max(
        min(
            int(score),
            100,
        ),
        0,
    )


# ============================================================
# DASHBOARD NOTIFICATION
# ============================================================

def create_notification(
    vehicle,
    prediction,
):
    """
    Build the service notification used by the bell dropdown.
    """

    helper_notification = (
        prediction.get(
            "notification"
        )
    )

    if isinstance(
        helper_notification,
        dict,
    ):
        return {
            "vehicle_id": (
                vehicle.id
            ),
            "vehicle_name": (
                vehicle.vehicle_name
            ),
            "registration_number": (
                vehicle.registration_number
            ),
            "level": str(
                helper_notification.get(
                    "level",
                    "info",
                )
                or "info"
            ),
            "title": str(
                helper_notification.get(
                    "title",
                    "Service update",
                )
                or "Service update"
            ),
            "message": str(
                helper_notification.get(
                    "message",
                    "",
                )
                or ""
            ),
        }

    if prediction.get(
        "is_overdue",
        False,
    ):
        return {
            "vehicle_id": (
                vehicle.id
            ),
            "vehicle_name": (
                vehicle.vehicle_name
            ),
            "registration_number": (
                vehicle.registration_number
            ),
            "level": "danger",
            "title": "Service overdue",
            "message": (
                "Schedule maintenance as soon as possible."
            ),
        }

    remaining = _to_int(
        prediction.get(
            "remaining_km"
        ),
        0,
    )

    if remaining <= 500:
        return {
            "vehicle_id": (
                vehicle.id
            ),
            "vehicle_name": (
                vehicle.vehicle_name
            ),
            "registration_number": (
                vehicle.registration_number
            ),
            "level": "danger",
            "title": "Service due soon",
            "message": (
                f"Only {remaining} km remaining."
            ),
        }

    if remaining <= 1000:
        return {
            "vehicle_id": (
                vehicle.id
            ),
            "vehicle_name": (
                vehicle.vehicle_name
            ),
            "registration_number": (
                vehicle.registration_number
            ),
            "level": "warning",
            "title": "Service approaching",
            "message": (
                f"{remaining} km remaining."
            ),
        }

    return {
        "vehicle_id": (
            vehicle.id
        ),
        "vehicle_name": (
            vehicle.vehicle_name
        ),
        "registration_number": (
            vehicle.registration_number
        ),
        "level": "success",
        "title": "Vehicle healthy",
        "message": (
            f"Next service in {remaining} km."
        ),
    }


# ============================================================
# DASHBOARD ROUTE
# ============================================================

@dashboard_bp.route(
    "/dashboard"
)
@login_required
def dashboard():

    # --------------------------------------------------------
    # Generate reminders
    # --------------------------------------------------------

    try:
        generate_reminders(
            current_user
        )

    except Exception as error:
        print(
            "Reminder warning:",
            error,
        )

    # --------------------------------------------------------
    # Get only logged-in user's vehicles
    # --------------------------------------------------------

    vehicles = (
        Vehicle.query
        .filter_by(
            user_id=current_user.id
        )
        .order_by(
            Vehicle.created_at.desc()
        )
        .all()
    )

    total_vehicles = len(
        vehicles
    )

    vehicle_predictions = []
    vehicle_data = {}
    notifications = []
    recent_activities = []
    mileage_values = []

    # --------------------------------------------------------
    # Dashboard totals
    # --------------------------------------------------------

    total_service_cost = 0.0
    total_fuel_cost = 0.0
    service_due_count = 0
    total_health = 0

    stats = {
        "total_vehicles": (
            total_vehicles
        ),
        "upcoming_services": 0,
        "overdue_services": 0,
        "insurance_renewals": 0,
        "puc_renewals": 0,
        "total_maintenance_cost": 0.0,
        "monthly_maintenance": 0.0,
        "total_fuel_cost": 0.0,
        "total_expenses": 0.0,
        "avg_mileage": 0.0,
        "average_health": 0,
    }

    # --------------------------------------------------------
    # Last six months for real chart
    # --------------------------------------------------------

    month_buckets = (
        _recent_months(
            6
        )
    )

    maintenance_by_month = {
        month["key"]: 0.0
        for month in month_buckets
    }

    fuel_by_month = {
        month["key"]: 0.0
        for month in month_buckets
    }

    current_month_key = (
        date.today().year,
        date.today().month,
    )

    # ========================================================
    # Process every vehicle
    # ========================================================

    for vehicle in vehicles:

        # ----------------------------------------------------
        # Service prediction
        # ----------------------------------------------------

        try:
            raw_prediction = (
                predict_next_service(
                    vehicle
                )
            )

        except Exception as error:
            print(
                "Prediction error for vehicle",
                vehicle.id,
                ":",
                error,
            )

            raw_prediction = {}

        prediction = (
            normalize_prediction(
                vehicle,
                raw_prediction,
            )
        )

        # ----------------------------------------------------
        # Service status counts
        # ----------------------------------------------------

        if prediction.get(
            "is_overdue",
            False,
        ):
            stats[
                "overdue_services"
            ] += 1

            service_due_count += 1

        elif (
            prediction.get(
                "supported",
                False,
            )
            and _to_int(
                prediction.get(
                    "remaining_km"
                ),
                999999,
            ) <= 1000
        ):
            stats[
                "upcoming_services"
            ] += 1

            service_due_count += 1

        # ----------------------------------------------------
        # Insurance status
        # ----------------------------------------------------

        try:
            insurance_status = (
                get_insurance_status(
                    vehicle
                )
            )

        except Exception as error:
            print(
                "Insurance status error:",
                vehicle.id,
                error,
            )

            insurance_status = (
                "unknown"
            )

        insurance_value = (
            _status_value(
                insurance_status
            )
        )

        if insurance_value in {
            "expiring_soon",
            "expiring soon",
            "expired",
        }:
            stats[
                "insurance_renewals"
            ] += 1

        # ----------------------------------------------------
        # PUC status
        # ----------------------------------------------------

        try:
            puc_status = (
                get_puc_status(
                    vehicle
                )
            )

        except Exception as error:
            print(
                "PUC status error:",
                vehicle.id,
                error,
            )

            puc_status = (
                "unknown"
            )

        puc_value = (
            _status_value(
                puc_status
            )
        )

        if puc_value in {
            "expiring_soon",
            "expiring soon",
            "expired",
        }:
            stats[
                "puc_renewals"
            ] += 1

        # ----------------------------------------------------
        # Service records
        # ----------------------------------------------------

        service_records = (
            ServiceRecord.query
            .filter_by(
                vehicle_id=vehicle.id
            )
            .order_by(
                ServiceRecord.service_date.desc()
            )
            .all()
        )

        vehicle_service_cost = sum(
            _to_float(
                record.total_cost
            )
            for record
            in service_records
        )

        total_service_cost += (
            vehicle_service_cost
        )

        # ----------------------------------------------------
        # Service activities + chart values
        # ----------------------------------------------------

        for record in service_records:

            if not record.service_date:
                continue

            service_key = (
                record.service_date.year,
                record.service_date.month,
            )

            amount = _to_float(
                record.total_cost
            )

            if (
                service_key
                in maintenance_by_month
            ):
                maintenance_by_month[
                    service_key
                ] += amount

            if (
                service_key
                == current_month_key
            ):
                stats[
                    "monthly_maintenance"
                ] += amount

            recent_activities.append({
                "date": (
                    record.service_date
                ),
                "type": "Service",
                "vehicle": (
                    vehicle.vehicle_name
                ),
                "cost": amount,
                "desc": (
                    record.service_type
                    or "Service"
                ),
            })

        # ----------------------------------------------------
        # Fuel records
        # ----------------------------------------------------

        fuel_records = (
            FuelRecord.query
            .filter_by(
                vehicle_id=vehicle.id
            )
            .order_by(
                FuelRecord.refill_date.desc()
            )
            .all()
        )

        vehicle_fuel_cost = sum(
            _to_float(
                record.total_amount
            )
            for record
            in fuel_records
        )

        average_mileage = 0.0

        # Use existing fuel helper when available.
        try:
            fuel_stats = (
                calculate_fuel_statistics(
                    fuel_records
                )
            )

            if isinstance(
                fuel_stats,
                dict,
            ):
                vehicle_fuel_cost = (
                    _to_float(
                        fuel_stats.get(
                            "total_cost",
                            vehicle_fuel_cost,
                        )
                    )
                )

                average_mileage = (
                    _to_float(
                        fuel_stats.get(
                            "avg_mileage",
                            0,
                        )
                    )
                )

        except Exception as error:
            print(
                "Fuel calculation error:",
                vehicle.id,
                error,
            )

        total_fuel_cost += (
            vehicle_fuel_cost
        )

        if average_mileage > 0:
            mileage_values.append(
                average_mileage
            )

        # ----------------------------------------------------
        # Fuel activities + chart values
        # ----------------------------------------------------

        for record in fuel_records:

            if not record.refill_date:
                continue

            fuel_key = (
                record.refill_date.year,
                record.refill_date.month,
            )

            amount = _to_float(
                record.total_amount
            )

            if fuel_key in fuel_by_month:
                fuel_by_month[
                    fuel_key
                ] += amount

            recent_activities.append({
                "date": (
                    record.refill_date
                ),
                "type": "Fuel",
                "vehicle": (
                    vehicle.vehicle_name
                ),
                "cost": amount,
                "desc": (
                    f"{record.litres} L - "
                    f"{record.fuel_station or 'Fuel Station'}"
                ),
            })

        # ----------------------------------------------------
        # Health
        # ----------------------------------------------------

        health_score = (
            calculate_dashboard_health(
                prediction,
                insurance_status,
                puc_status,
            )
        )

        total_health += (
            health_score
        )

        # ----------------------------------------------------
        # Data required by premium dashboard.html
        # ----------------------------------------------------

        vehicle_predictions.append({
            "vehicle": (
                vehicle
            ),
            "prediction": (
                prediction
            ),
            "total_service_cost": round(
                vehicle_service_cost,
                2,
            ),
            "total_fuel_cost": round(
                vehicle_fuel_cost,
                2,
            ),
            "avg_mileage": round(
                average_mileage,
                2,
            ),
            "health_score": (
                health_score
            ),
        })

        # Keep newer data structure for other templates/features.
        vehicle_data[
            vehicle.id
        ] = {
            "prediction": (
                prediction
            ),
            "total_service_cost": round(
                vehicle_service_cost,
                2,
            ),
            "total_fuel_cost": round(
                vehicle_fuel_cost,
                2,
            ),
            "avg_mileage": round(
                average_mileage,
                2,
            ),
            "insurance_status": (
                insurance_status
            ),
            "puc_status": (
                puc_status
            ),
            "health_score": (
                health_score
            ),
        }

        notifications.append(
            create_notification(
                vehicle,
                prediction,
            )
        )

    # ========================================================
    # Final calculations
    # ========================================================

    total_service_cost = round(
        total_service_cost,
        2,
    )

    total_fuel_cost = round(
        total_fuel_cost,
        2,
    )

    total_expenses = round(
        total_service_cost
        + total_fuel_cost,
        2,
    )

    if total_vehicles > 0:
        average_health = round(
            total_health
            / total_vehicles
        )
    else:
        average_health = 0

    if mileage_values:
        average_mileage = (
            sum(
                mileage_values
            )
            / len(
                mileage_values
            )
        )
    else:
        average_mileage = 0.0

    stats[
        "total_maintenance_cost"
    ] = (
        total_service_cost
    )

    stats[
        "total_fuel_cost"
    ] = (
        total_fuel_cost
    )

    stats[
        "total_expenses"
    ] = (
        total_expenses
    )

    stats[
        "avg_mileage"
    ] = round(
        average_mileage,
        2,
    )

    stats[
        "average_health"
    ] = (
        average_health
    )

    stats[
        "monthly_maintenance"
    ] = round(
        stats[
            "monthly_maintenance"
        ],
        2,
    )

    # --------------------------------------------------------
    # Sort recent activity
    # --------------------------------------------------------

    recent_activities.sort(
        key=lambda item: (
            item["date"]
        ),
        reverse=True,
    )

    recent_activities = (
        recent_activities[:10]
    )

    # --------------------------------------------------------
    # Real chart data
    # --------------------------------------------------------

    chart_labels = [
        month["label"]
        for month
        in month_buckets
    ]

    chart_service_costs = [
        round(
            maintenance_by_month[
                month["key"]
            ],
            2,
        )
        for month
        in month_buckets
    ]

    chart_fuel_costs = [
        round(
            fuel_by_month[
                month["key"]
            ],
            2,
        )
        for month
        in month_buckets
    ]

    chart_data = {
        "labels": (
            chart_labels
        ),
        "maintenance_by_month": [
            {
                "label": (
                    chart_labels[index]
                ),
                "amount": (
                    chart_service_costs[
                        index
                    ]
                ),
            }
            for index
            in range(
                len(
                    chart_labels
                )
            )
        ],
        "fuel_by_month": [
            {
                "label": (
                    chart_labels[index]
                ),
                "amount": (
                    chart_fuel_costs[
                        index
                    ]
                ),
            }
            for index
            in range(
                len(
                    chart_labels
                )
            )
        ],
        "mileage_trend": [],
        "expense_categories": [
            {
                "category": (
                    "Maintenance"
                ),
                "amount": (
                    total_service_cost
                ),
            },
            {
                "category": (
                    "Fuel"
                ),
                "amount": (
                    total_fuel_cost
                ),
            },
        ],
    }

    # --------------------------------------------------------
    # Reminders
    # --------------------------------------------------------

    try:
        reminders = (
            Reminder.query
            .filter_by(
                user_id=current_user.id,
                is_dismissed=False,
            )
            .order_by(
                Reminder.due_date
            )
            .all()
        )

    except Exception as error:
        print(
            "Reminder query error:",
            error,
        )

        reminders = []

    # ========================================================
    # Render
    # ========================================================

    return render_template(
        "dashboard/dashboard.html",

        user=current_user,

        vehicles=vehicles,

        vehicle_predictions=(
            vehicle_predictions
        ),

        vehicle_data=(
            vehicle_data
        ),

        notifications=(
            notifications
        ),

        stats=stats,

        reminders=reminders,

        chart_data=chart_data,

        recent_activities=(
            recent_activities
        ),

        # Direct values used by the corrected premium dashboard.
        total_vehicles=(
            total_vehicles
        ),

        service_due_count=(
            service_due_count
        ),

        total_service_cost=(
            total_service_cost
        ),

        total_fuel_cost=(
            total_fuel_cost
        ),

        total_expenses=(
            total_expenses
        ),

        average_health=(
            average_health
        ),

        chart_labels=(
            chart_labels
        ),

        chart_service_costs=(
            chart_service_costs
        ),

        chart_fuel_costs=(
            chart_fuel_costs
        ),
    )


# ============================================================
# COMPATIBILITY ALIAS
# ============================================================

# Some versions of routes/__init__.py import "dashboard",
# while the current app imports "dashboard_bp".
dashboard = dashboard_bp