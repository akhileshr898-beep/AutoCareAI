from datetime import date
from dateutil.relativedelta import relativedelta


SERVICE_SCHEDULES = {
    "royal enfield": {
        "hunter 350": [
            {
                "service_number": 1,
                "distance_km": 500,
                "months": 1.5,
                "service_name": "First Service"
            },
            {
                "service_number": 2,
                "distance_km": 5000,
                "months": 6,
                "service_name": "Second Service"
            },
            {
                "service_number": 3,
                "distance_km": 10000,
                "months": 12,
                "service_name": "Third Service"
            },
            {
                "service_number": 4,
                "distance_km": 15000,
                "months": 18,
                "service_name": "Fourth Service"
            },
            {
                "service_number": 5,
                "distance_km": 20000,
                "months": 24,
                "service_name": "Fifth Service"
            },
            {
                "service_number": 6,
                "distance_km": 25000,
                "months": 30,
                "service_name": "Sixth Service"
            },
            {
                "service_number": 7,
                "distance_km": 30000,
                "months": 36,
                "service_name": "Seventh Service"
            },
            {
                "service_number": 8,
                "distance_km": 35000,
                "months": 42,
                "service_name": "Eighth Service"
            },
            {
                "service_number": 9,
                "distance_km": 40000,
                "months": 48,
                "service_name": "Ninth Service"
            },
            {
                "service_number": 10,
                "distance_km": 45000,
                "months": 54,
                "service_name": "Tenth Service"
            },
            {
                "service_number": 11,
                "distance_km": 50000,
                "months": 60,
                "service_name": "Eleventh Service"
            }
        ]
    }
}


def normalize_text(value):
    if not value:
        return ""

    return value.strip().lower()


def add_service_months(start_date, months):
    whole_months = int(months)
    remaining_fraction = months - whole_months

    predicted_date = start_date + relativedelta(
        months=whole_months
    )

    if remaining_fraction:
        predicted_date += relativedelta(days=15)

    return predicted_date


def get_service_schedule(company, model):
    company_key = normalize_text(company)
    model_key = normalize_text(model)

    company_schedules = SERVICE_SCHEDULES.get(
        company_key,
        {}
    )

    return company_schedules.get(
        model_key,
        []
    )


def predict_next_service(vehicle):
    schedule = get_service_schedule(
        vehicle.company,
        vehicle.vehicle_name
    )

    if not schedule:
        schedule = get_service_schedule(
            vehicle.company,
            vehicle.model
        )

    if not schedule:
        return {
            "supported": False,
            "message": (
                "Official service schedule is not yet available "
                "for this company and model."
            )
        }

    current_odometer = vehicle.odometer or 0
    purchase_date = vehicle.purchase_date

    today = date.today()

    for service in schedule:
        distance_due = (
            current_odometer >= service["distance_km"]
        )

        service_date = None
        time_due = False

        if purchase_date:
            service_date = add_service_months(
                purchase_date,
                service["months"]
            )

            time_due = today >= service_date

        if not distance_due and not time_due:
            remaining_km = max(
                service["distance_km"] - current_odometer,
                0
            )

            remaining_days = None

            if service_date:
                remaining_days = (
                    service_date - today
                ).days

            return {
                "supported": True,
                "service_number": service["service_number"],
                "service_name": service["service_name"],
                "service_km": service["distance_km"],
                "service_date": service_date,
                "remaining_km": remaining_km,
                "remaining_days": remaining_days,
                "is_overdue": False,
                "due_reason": None
            }

    last_service = schedule[-1]

    return {
        "supported": True,
        "service_number": last_service["service_number"],
        "service_name": "Service overdue",
        "service_km": last_service["distance_km"],
        "service_date": None,
        "remaining_km": 0,
        "remaining_days": 0,
        "is_overdue": True,
        "due_reason": (
            "The vehicle has crossed the available official "
            "service schedule range."
        )
    }