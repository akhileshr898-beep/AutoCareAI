from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user

from models import Vehicle, FuelRecord, ServiceRecord
from extensions import db


fuel = Blueprint("fuel", __name__, url_prefix="/fuel")


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _to_float(value, default=0.0):
    """
    Safely convert Decimal/int/float/None to float.
    """
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError, InvalidOperation):
        return default


def _parse_positive_decimal(value):
    """
    Convert form value to a positive finite Decimal.
    Raises ValueError when invalid.
    """
    try:
        number = Decimal(str(value).strip())

        if not number.is_finite():
            raise ValueError

        if number <= 0:
            raise ValueError

        return number

    except (InvalidOperation, ValueError, TypeError):
        raise ValueError


def _build_fuel_statistics(records):
    """
    Build every statistic required by fuel history/analytics.

    defaultdict(float) is intentional:
    if Jinja requests a missing numeric statistic such as
    statistics.some_new_value, it safely returns 0.0
    instead of throwing UndefinedError.
    """

    statistics = defaultdict(float)

    # --------------------------------------------------------
    # Default values
    # --------------------------------------------------------

    statistics["total_records"] = len(records)

    statistics["total_amount"] = 0.0
    statistics["total_spent"] = 0.0

    statistics["total_litres"] = 0.0
    statistics["total_liters"] = 0.0

    statistics["average_price"] = 0.0
    statistics["average_price_per_litre"] = 0.0

    statistics["average_mileage"] = 0.0
    statistics["avg_mileage"] = 0.0

    statistics["best_mileage"] = 0.0
    statistics["lowest_mileage"] = 0.0
    statistics["last_mileage"] = 0.0

    statistics["total_distance"] = 0.0
    statistics["cost_per_km"] = 0.0

    if not records:
        return statistics

    # --------------------------------------------------------
    # Total fuel spending and litres
    # --------------------------------------------------------

    total_amount = sum(
        _to_float(record.total_amount)
        for record in records
    )

    total_litres = sum(
        _to_float(record.litres)
        for record in records
    )

    statistics["total_amount"] = round(total_amount, 2)
    statistics["total_spent"] = round(total_amount, 2)

    statistics["total_litres"] = round(total_litres, 3)
    statistics["total_liters"] = round(total_litres, 3)

    # --------------------------------------------------------
    # Average fuel price
    # Weighted average is more accurate:
    # total money / total litres
    # --------------------------------------------------------

    if total_litres > 0:

        average_price = total_amount / total_litres

        statistics["average_price"] = round(
            average_price,
            2
        )

        statistics["average_price_per_litre"] = round(
            average_price,
            2
        )

    # --------------------------------------------------------
    # Mileage calculations
    #
    # Records must be chronological.
    #
    # Mileage =
    # distance travelled / litres filled at current refill
    # --------------------------------------------------------

    records_asc = sorted(
        records,
        key=lambda record: (
            record.refill_date,
            record.odometer,
            record.id or 0,
        )
    )

    mileage_values = []
    total_distance = 0

    for index in range(1, len(records_asc)):

        previous = records_asc[index - 1]
        current = records_asc[index]

        previous_odometer = previous.odometer or 0
        current_odometer = current.odometer or 0

        distance = current_odometer - previous_odometer

        current_litres = _to_float(
            current.litres
        )

        if distance <= 0:
            continue

        if current_litres <= 0:
            continue

        mileage = distance / current_litres

        # Prevent obviously broken values caused by bad data.
        if mileage <= 0:
            continue

        mileage_values.append(mileage)

        total_distance += distance

    statistics["total_distance"] = round(
        total_distance,
        2
    )

    if mileage_values:

        average_mileage = (
            sum(mileage_values) /
            len(mileage_values)
        )

        statistics["average_mileage"] = round(
            average_mileage,
            2
        )

        statistics["avg_mileage"] = round(
            average_mileage,
            2
        )

        statistics["best_mileage"] = round(
            max(mileage_values),
            2
        )

        statistics["lowest_mileage"] = round(
            min(mileage_values),
            2
        )

        statistics["last_mileage"] = round(
            mileage_values[-1],
            2
        )

    # --------------------------------------------------------
    # Cost per kilometre
    # --------------------------------------------------------

    if total_distance > 0:

        statistics["cost_per_km"] = round(
            total_amount / total_distance,
            2
        )

    return statistics


# ============================================================
# ADD FUEL
# ============================================================

@fuel.route(
    "/add/<int:vehicle_id>",
    methods=["GET", "POST"]
)
@login_required
def add_fuel(vehicle_id):

    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id
    ).first_or_404()

    if request.method == "POST":

        refill_date_value = request.form.get(
            "refill_date",
            ""
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            ""
        ).strip()

        price_per_litre_value = request.form.get(
            "price_per_litre",
            ""
        ).strip()

        total_amount_value = request.form.get(
            "total_amount",
            ""
        ).strip()

        fuel_station = request.form.get(
            "fuel_station",
            ""
        ).strip()

        notes = request.form.get(
            "notes",
            ""
        ).strip()

        full_tank = (
            request.form.get("full_tank") == "on"
        )

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        if not all([
            refill_date_value,
            odometer_value,
            price_per_litre_value,
            total_amount_value
        ]):

            flash(
                "Date, odometer, price per litre "
                "and amount are required.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        # ----------------------------------------------------
        # Date validation
        # ----------------------------------------------------

        try:

            refill_date = datetime.strptime(
                refill_date_value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Enter a valid refill date.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        # ----------------------------------------------------
        # Odometer validation
        # ----------------------------------------------------

        try:

            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:

            flash(
                "Enter a valid odometer reading.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        # ----------------------------------------------------
        # Fuel values validation
        # ----------------------------------------------------

        try:

            price_per_litre = (
                _parse_positive_decimal(
                    price_per_litre_value
                )
            )

            total_amount = (
                _parse_positive_decimal(
                    total_amount_value
                )
            )

            litres = (
                total_amount /
                price_per_litre
            )

        except (
            ValueError,
            InvalidOperation,
            ZeroDivisionError
        ):

            flash(
                "Enter a valid fuel price "
                "and total amount.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        # ----------------------------------------------------
        # Check previous odometer
        # ----------------------------------------------------

        latest_record = (
            FuelRecord.query
            .filter_by(
                vehicle_id=vehicle.id
            )
            .order_by(
                FuelRecord.odometer.desc(),
                FuelRecord.refill_date.desc(),
                FuelRecord.id.desc()
            )
            .first()
        )

        if (
            latest_record and
            odometer < latest_record.odometer
        ):

            flash(
                "Odometer cannot be lower than "
                "the previous fuel entry.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        # ----------------------------------------------------
        # Create fuel record
        # ----------------------------------------------------

        fuel_record = FuelRecord(

            vehicle_id=vehicle.id,

            refill_date=refill_date,

            odometer=odometer,

            litres=litres,

            total_amount=total_amount,

            price_per_litre=price_per_litre,

            fuel_station=(
                fuel_station or None
            ),

            full_tank=full_tank,

            notes=(
                notes or None
            ),
        )

        db.session.add(
            fuel_record
        )

        # Update vehicle odometer
        if (
            vehicle.odometer is None or
            odometer > vehicle.odometer
        ):

            vehicle.odometer = odometer

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to save fuel record. "
                "Please try again.",
                "danger"
            )

            return render_template(
                "fuel/add_fuel.html",
                vehicle=vehicle
            )

        flash(
            "Fuel record added successfully.",
            "success"
        )

        return redirect(
            url_for(
                "fuel.fuel_history",
                vehicle_id=vehicle.id
            )
        )

    return render_template(
        "fuel/add_fuel.html",
        vehicle=vehicle
    )


# ============================================================
# FUEL HISTORY
# ============================================================

@fuel.route(
    "/history/<int:vehicle_id>"
)
@login_required
def fuel_history(vehicle_id):

    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id
    ).first_or_404()

    records = (
        FuelRecord.query
        .filter_by(
            vehicle_id=vehicle.id
        )
        .order_by(
            FuelRecord.refill_date.desc(),
            FuelRecord.odometer.desc(),
            FuelRecord.id.desc()
        )
        .all()
    )

    # IMPORTANT:
    # We calculate ALL statistics here.
    statistics = _build_fuel_statistics(
        records
    )

    return render_template(

        "fuel/history.html",

        vehicle=vehicle,

        records=records,

        statistics=statistics
    )


# ============================================================
# EDIT FUEL
# ============================================================

@fuel.route(
    "/edit/<int:fuel_id>",
    methods=["GET", "POST"]
)
@login_required
def edit_fuel(fuel_id):

    fuel_record = (
        FuelRecord.query
        .join(Vehicle)
        .filter(
            FuelRecord.id == fuel_id,
            Vehicle.user_id == current_user.id
        )
        .first_or_404()
    )

    vehicle = fuel_record.vehicle

    if request.method == "POST":

        refill_date_value = request.form.get(
            "refill_date",
            ""
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            ""
        ).strip()

        price_per_litre_value = request.form.get(
            "price_per_litre",
            ""
        ).strip()

        total_amount_value = request.form.get(
            "total_amount",
            ""
        ).strip()

        fuel_station = request.form.get(
            "fuel_station",
            ""
        ).strip()

        notes = request.form.get(
            "notes",
            ""
        ).strip()

        full_tank = (
            request.form.get("full_tank") == "on"
        )

        # ----------------------------------------------------
        # Required fields
        # ----------------------------------------------------

        if not all([
            refill_date_value,
            odometer_value,
            price_per_litre_value,
            total_amount_value
        ]):

            flash(
                "Date, odometer, price per litre "
                "and amount are required.",
                "danger"
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record
            )

        # ----------------------------------------------------
        # Date
        # ----------------------------------------------------

        try:

            refill_date = datetime.strptime(
                refill_date_value,
                "%Y-%m-%d"
            ).date()

        except ValueError:

            flash(
                "Enter a valid refill date.",
                "danger"
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record
            )

        # ----------------------------------------------------
        # Odometer
        # ----------------------------------------------------

        try:

            odometer = int(
                odometer_value
            )

            if odometer < 0:
                raise ValueError

        except ValueError:

            flash(
                "Enter a valid odometer reading.",
                "danger"
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record
            )

        # ----------------------------------------------------
        # Price / total
        # ----------------------------------------------------

        try:

            price_per_litre = (
                _parse_positive_decimal(
                    price_per_litre_value
                )
            )

            total_amount = (
                _parse_positive_decimal(
                    total_amount_value
                )
            )

            litres = (
                total_amount /
                price_per_litre
            )

        except (
            ValueError,
            InvalidOperation,
            ZeroDivisionError
        ):

            flash(
                "Enter a valid fuel price "
                "and total amount.",
                "danger"
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record
            )

        # ----------------------------------------------------
        # Validate against surrounding records
        # ----------------------------------------------------

        other_records = (
            FuelRecord.query
            .filter(
                FuelRecord.vehicle_id == vehicle.id,
                FuelRecord.id != fuel_record.id
            )
            .order_by(
                FuelRecord.refill_date.asc(),
                FuelRecord.odometer.asc(),
                FuelRecord.id.asc()
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
                    record.id or 0
                )
            )

            if (
                odometer <
                previous_record.odometer
            ):

                flash(
                    "Odometer cannot be lower than "
                    "the previous fuel entry.",
                    "danger"
                )

                return render_template(
                    "fuel/edit_fuel.html",
                    vehicle=vehicle,
                    fuel_record=fuel_record
                )

        if upper_records:

            next_record = min(
                upper_records,
                key=lambda record: (
                    record.refill_date,
                    record.odometer,
                    record.id or 0
                )
            )

            if (
                odometer >
                next_record.odometer
            ):

                flash(
                    "Odometer cannot be higher than "
                    "the next fuel entry.",
                    "danger"
                )

                return render_template(
                    "fuel/edit_fuel.html",
                    vehicle=vehicle,
                    fuel_record=fuel_record
                )

        # ----------------------------------------------------
        # Update record
        # ----------------------------------------------------

        fuel_record.refill_date = refill_date

        fuel_record.odometer = odometer

        fuel_record.litres = litres

        fuel_record.total_amount = total_amount

        fuel_record.price_per_litre = (
            price_per_litre
        )

        fuel_record.fuel_station = (
            fuel_station or None
        )

        fuel_record.full_tank = full_tank

        fuel_record.notes = (
            notes or None
        )

        # Flush so SQLAlchemy sees edited odometer
        db.session.flush()

        highest_fuel_odometer = (
            db.session.query(
                db.func.max(
                    FuelRecord.odometer
                )
            )
            .filter(
                FuelRecord.vehicle_id ==
                vehicle.id
            )
            .scalar()
        )

        highest_service_odometer = (
            db.session.query(
                db.func.max(
                    ServiceRecord.odometer
                )
            )
            .filter(
                ServiceRecord.vehicle_id ==
                vehicle.id
            )
            .scalar()
        )

        vehicle.odometer = max(
            highest_fuel_odometer or 0,
            highest_service_odometer or 0,
            vehicle.odometer or 0
        )

        try:

            db.session.commit()

        except Exception:

            db.session.rollback()

            flash(
                "Unable to update fuel record.",
                "danger"
            )

            return render_template(
                "fuel/edit_fuel.html",
                vehicle=vehicle,
                fuel_record=fuel_record
            )

        flash(
            "Fuel record updated successfully.",
            "success"
        )

        return redirect(
            url_for(
                "fuel.fuel_history",
                vehicle_id=vehicle.id
            )
        )

    return render_template(

        "fuel/edit_fuel.html",

        vehicle=vehicle,

        fuel_record=fuel_record
    )


# ============================================================
# DELETE FUEL
# ============================================================

@fuel.route(
    "/delete/<int:fuel_id>",
    methods=["POST"]
)
@login_required
def delete_fuel(fuel_id):

    fuel_record = (
        FuelRecord.query
        .join(Vehicle)
        .filter(
            FuelRecord.id == fuel_id,
            Vehicle.user_id == current_user.id
        )
        .first_or_404()
    )

    vehicle = fuel_record.vehicle

    db.session.delete(
        fuel_record
    )

    # Flush deletion before checking max odometer.
    db.session.flush()

    highest_fuel_odometer = (
        db.session.query(
            db.func.max(
                FuelRecord.odometer
            )
        )
        .filter(
            FuelRecord.vehicle_id ==
            vehicle.id
        )
        .scalar()
    )

    highest_service_odometer = (
        db.session.query(
            db.func.max(
                ServiceRecord.odometer
            )
        )
        .filter(
            ServiceRecord.vehicle_id ==
            vehicle.id
        )
        .scalar()
    )

    # Vehicle's real odometer should normally never move backwards.
    vehicle.odometer = max(
        highest_fuel_odometer or 0,
        highest_service_odometer or 0,
        vehicle.odometer or 0,
    )

    try:

        db.session.commit()

    except Exception:

        db.session.rollback()

        flash(
            "Unable to delete fuel record.",
            "danger"
        )

        return redirect(
            url_for(
                "fuel.fuel_history",
                vehicle_id=vehicle.id
            )
        )

    flash(
        "Fuel record deleted successfully.",
        "success"
    )

    return redirect(
        url_for(
            "fuel.fuel_history",
            vehicle_id=vehicle.id
        )
    )


# ============================================================
# FUEL ANALYTICS
# ============================================================

@fuel.route(
    "/analytics/<int:vehicle_id>"
)
@login_required
def fuel_analytics(vehicle_id):

    vehicle = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id
    ).first_or_404()

    records = (
        FuelRecord.query
        .filter_by(
            vehicle_id=vehicle.id
        )
        .order_by(
            FuelRecord.refill_date.asc(),
            FuelRecord.odometer.asc(),
            FuelRecord.id.asc()
        )
        .all()
    )

    statistics = _build_fuel_statistics(
        records
    )

    # ========================================================
    # MONTHLY DATA
    # ========================================================

    monthly_totals = {}

    for record in records:

        month_key = (
            record.refill_date.strftime(
                "%b %Y"
            )
        )

        if month_key not in monthly_totals:

            monthly_totals[month_key] = {
                "amount": 0.0,
                "litres": 0.0
            }

        monthly_totals[
            month_key
        ]["amount"] += _to_float(
            record.total_amount
        )

        monthly_totals[
            month_key
        ]["litres"] += _to_float(
            record.litres
        )

    chart_labels = list(
        monthly_totals.keys()
    )

    monthly_spending = [

        round(
            monthly_totals[label]["amount"],
            2
        )

        for label in chart_labels
    ]

    monthly_litres = [

        round(
            monthly_totals[label]["litres"],
            2
        )

        for label in chart_labels
    ]

    # ========================================================
    # MILEAGE CHART
    # ========================================================

    mileage_labels = []
    mileage_values = []

    for index in range(
        1,
        len(records)
    ):

        previous = records[
            index - 1
        ]

        current = records[
            index
        ]

        distance = (
            (current.odometer or 0) -
            (previous.odometer or 0)
        )

        litres = _to_float(
            current.litres
        )

        if (
            distance > 0 and
            litres > 0
        ):

            mileage = (
                distance /
                litres
            )

            mileage_labels.append(
                current.refill_date.strftime(
                    "%d %b"
                )
            )

            mileage_values.append(
                round(
                    mileage,
                    2
                )
            )

    # ========================================================
    # REFILL CHART
    # ========================================================

    refill_labels = [

        record.refill_date.strftime(
            "%d %b"
        )

        for record in records
    ]

    refill_litres = [

        round(
            _to_float(
                record.litres
            ),
            2
        )

        for record in records
    ]

    # ========================================================
    # ANALYTICS VALUES
    # ========================================================

    total_distance = statistics[
        "total_distance"
    ]

    cost_per_km = statistics[
        "cost_per_km"
    ]

    best_mileage = statistics[
        "best_mileage"
    ]

    amounts = [

        _to_float(
            record.total_amount
        )

        for record in records
    ]

    prices = [

        _to_float(
            record.price_per_litre
        )

        for record in records

        if (
            record.price_per_litre is not None and
            _to_float(
                record.price_per_litre
            ) > 0
        )
    ]

    highest_bill = (
        max(amounts)
        if amounts
        else 0.0
    )

    lowest_bill = (
        min(amounts)
        if amounts
        else 0.0
    )

    cheapest_price = (
        min(prices)
        if prices
        else 0.0
    )

    highest_price = (
        max(prices)
        if prices
        else 0.0
    )

    recent_record = (
        records[-1]
        if records
        else None
    )

    # ========================================================
    # RENDER
    # ========================================================

    return render_template(

        "fuel/analytics.html",

        vehicle=vehicle,

        records=records,

        statistics=statistics,

        total_distance=total_distance,

        cost_per_km=cost_per_km,

        best_mileage=best_mileage,

        highest_bill=round(
            highest_bill,
            2
        ),

        lowest_bill=round(
            lowest_bill,
            2
        ),

        cheapest_price=round(
            cheapest_price,
            2
        ),

        highest_price=round(
            highest_price,
            2
        ),

        recent_record=recent_record,

        chart_labels=chart_labels,

        monthly_spending=monthly_spending,

        monthly_litres=monthly_litres,

        mileage_labels=mileage_labels,

        mileage_values=mileage_values,

        refill_labels=refill_labels,

        refill_litres=refill_litres,
    )