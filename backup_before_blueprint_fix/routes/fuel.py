import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import Vehicle, FuelRecord, ServiceRecord
from extensions import db
from helpers import calculate_fuel_statistics

fuel = Blueprint('fuel', __name__, url_prefix='/fuel')

@fuel.route("/add/<int:vehicle_id>", methods=["GET", "POST"])
@login_required
def add_fuel(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        refill_date_value = request.form.get("refill_date", "").strip()
        odometer_value = request.form.get("odometer", "").strip()
        price_per_litre_value = request.form.get("price_per_litre", "").strip()
        total_amount_value = request.form.get("total_amount", "").strip()
        fuel_station = request.form.get("fuel_station", "").strip()
        notes = request.form.get("notes", "").strip()
        full_tank = request.form.get("full_tank") == "on"

        if not all([refill_date_value, odometer_value, price_per_litre_value, total_amount_value]):
            flash("Date, odometer, price per litre and amount are required.", "danger")
            return render_template("fuel/add_fuel.html", vehicle=vehicle)

        try:
            refill_date = datetime.strptime(refill_date_value, "%Y-%m-%d").date()
        except ValueError:
            flash("Enter a valid refill date.", "danger")
            return render_template("fuel/add_fuel.html", vehicle=vehicle)

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("fuel/add_fuel.html", vehicle=vehicle)

        try:
            price_per_litre = Decimal(price_per_litre_value)
            total_amount = Decimal(total_amount_value)
            if price_per_litre <= 0 or total_amount <= 0:
                raise InvalidOperation
            litres = total_amount / price_per_litre
        except (InvalidOperation, ValueError, ZeroDivisionError):
            flash("Enter a valid fuel price and total amount.", "danger")
            return render_template("fuel/add_fuel.html", vehicle=vehicle)

        latest_record = FuelRecord.query.filter_by(vehicle_id=vehicle.id).order_by(
            FuelRecord.odometer.desc(), FuelRecord.refill_date.desc()
        ).first()

        if latest_record and odometer < latest_record.odometer:
            flash("Odometer cannot be lower than the previous fuel entry.", "danger")
            return render_template("fuel/add_fuel.html", vehicle=vehicle)

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

        db.session.add(fuel_record)

        if odometer > vehicle.odometer:
            vehicle.odometer = odometer

        db.session.commit()
        flash("Fuel record added successfully.", "success")
        return redirect(url_for("fuel.fuel_history", vehicle_id=vehicle.id))

    return render_template("fuel/add_fuel.html", vehicle=vehicle)

@fuel.route("/history/<int:vehicle_id>")
@login_required
def fuel_history(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    records = FuelRecord.query.filter_by(vehicle_id=vehicle.id).order_by(
        FuelRecord.refill_date.desc(), FuelRecord.odometer.desc(), FuelRecord.id.desc()
    ).all()

    statistics = calculate_fuel_statistics(records)
    return render_template("fuel/history.html", vehicle=vehicle, records=records, statistics=statistics)

@fuel.route("/edit/<int:fuel_id>", methods=["GET", "POST"])
@login_required
def edit_fuel(fuel_id):
    fuel_record = FuelRecord.query.join(Vehicle).filter(
        FuelRecord.id == fuel_id, Vehicle.user_id == current_user.id
    ).first_or_404()

    vehicle = fuel_record.vehicle

    if request.method == "POST":
        refill_date_value = request.form.get("refill_date", "").strip()
        odometer_value = request.form.get("odometer", "").strip()
        price_per_litre_value = request.form.get("price_per_litre", "").strip()
        total_amount_value = request.form.get("total_amount", "").strip()
        fuel_station = request.form.get("fuel_station", "").strip()
        notes = request.form.get("notes", "").strip()
        full_tank = request.form.get("full_tank") == "on"

        if not all([refill_date_value, odometer_value, price_per_litre_value, total_amount_value]):
            flash("Date, odometer, price per litre and amount are required.", "danger")
            return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        try:
            refill_date = datetime.strptime(refill_date_value, "%Y-%m-%d").date()
        except ValueError:
            flash("Enter a valid refill date.", "danger")
            return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        try:
            price_per_litre = Decimal(price_per_litre_value)
            total_amount = Decimal(total_amount_value)
            if price_per_litre <= 0 or total_amount <= 0:
                raise InvalidOperation
            litres = total_amount / price_per_litre
        except (InvalidOperation, ValueError, ZeroDivisionError):
            flash("Enter a valid fuel price and total amount.", "danger")
            return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        other_records = FuelRecord.query.filter(
            FuelRecord.vehicle_id == vehicle.id, FuelRecord.id != fuel_record.id
        ).order_by(FuelRecord.odometer.asc(), FuelRecord.refill_date.asc()).all()

        lower_records = [r for r in other_records if r.refill_date <= refill_date]
        upper_records = [r for r in other_records if r.refill_date >= refill_date]

        if lower_records:
            prev_rec = max(lower_records, key=lambda r: (r.refill_date, r.odometer))
            if odometer < prev_rec.odometer:
                flash("Odometer cannot be lower than the previous fuel entry.", "danger")
                return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        if upper_records:
            next_rec = min(upper_records, key=lambda r: (r.refill_date, r.odometer))
            if odometer > next_rec.odometer:
                flash("Odometer cannot be higher than the next fuel entry.", "danger")
                return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

        fuel_record.refill_date = refill_date
        fuel_record.odometer = odometer
        fuel_record.litres = litres
        fuel_record.total_amount = total_amount
        fuel_record.price_per_litre = price_per_litre
        fuel_record.fuel_station = fuel_station or None
        fuel_record.full_tank = full_tank
        fuel_record.notes = notes or None

        highest_odometer = db.session.query(db.func.max(FuelRecord.odometer)).filter(
            FuelRecord.vehicle_id == vehicle.id
        ).scalar()

        vehicle.odometer = max(highest_odometer or 0, odometer)
        db.session.commit()
        flash("Fuel record updated successfully.", "success")
        return redirect(url_for("fuel.fuel_history", vehicle_id=vehicle.id))

    return render_template("fuel/edit_fuel.html", vehicle=vehicle, fuel_record=fuel_record)

@fuel.route("/delete/<int:fuel_id>", methods=["POST"])
@login_required
def delete_fuel(fuel_id):
    fuel_record = FuelRecord.query.join(Vehicle).filter(
        FuelRecord.id == fuel_id, Vehicle.user_id == current_user.id
    ).first_or_404()
    
    vehicle = fuel_record.vehicle
    db.session.delete(fuel_record)
    db.session.flush()

    highest_fuel_odometer = db.session.query(db.func.max(FuelRecord.odometer)).filter(
        FuelRecord.vehicle_id == vehicle.id
    ).scalar()

    highest_service_odometer = db.session.query(db.func.max(ServiceRecord.odometer)).filter(
        ServiceRecord.vehicle_id == vehicle.id
    ).scalar()

    vehicle.odometer = max(
        highest_fuel_odometer or 0,
        highest_service_odometer or 0,
        vehicle.odometer or 0,
    )

    db.session.commit()
    flash("Fuel record deleted successfully.", "success")
    return redirect(url_for("fuel.fuel_history", vehicle_id=vehicle.id))

@fuel.route("/analytics/<int:vehicle_id>")
@login_required
def fuel_analytics(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    records = FuelRecord.query.filter_by(vehicle_id=vehicle.id).order_by(
        FuelRecord.refill_date.asc(), FuelRecord.odometer.asc(), FuelRecord.id.asc()
    ).all()

    statistics = calculate_fuel_statistics(records)
    
    # Very basic mocking for the context needed by the template if required
    # Assuming chart_labels etc exist in template as from app.py
    monthly_totals = {}
    valid_distances = []
    valid_mileages = []
    
    for i, record in enumerate(records):
        month_key = record.refill_date.strftime("%b %Y")
        monthly_totals.setdefault(month_key, {"amount": 0, "litres": 0})
        monthly_totals[month_key]["amount"] += float(record.total_amount or 0)
        monthly_totals[month_key]["litres"] += float(record.litres or 0)
        
        if i > 0:
            prev = records[i-1]
            dist = record.odometer - prev.odometer
            if dist > 0 and record.litres > 0:
                mil = float(dist / record.litres)
                valid_distances.append(dist)
                valid_mileages.append(mil)

    chart_labels = list(monthly_totals.keys())
    monthly_spending = [round(monthly_totals[lbl]["amount"], 2) for lbl in chart_labels]
    monthly_litres = [round(monthly_totals[lbl]["litres"], 2) for lbl in chart_labels]
    
    total_distance = sum(valid_distances) if valid_distances else 0
    cost_per_km = (float(statistics["total_amount"]) / total_distance) if total_distance > 0 else 0
    
    amounts = [float(r.total_amount or 0) for r in records]
    prices = [float(r.price_per_litre or 0) for r in records if r.price_per_litre]
    
    best_mileage = max(valid_mileages) if valid_mileages else 0
    highest_bill = max(amounts) if amounts else 0
    lowest_bill = min(amounts) if amounts else 0
    cheapest_price = min(prices) if prices else 0
    highest_price = max(prices) if prices else 0
    
    recent_record = records[-1] if records else None

    # Dummy implementations for labels and values
    mileage_labels = [r.refill_date.strftime("%d %b") for r in records[1:]] if len(records) > 1 else []
    mileage_values = valid_mileages
    refill_labels = [r.refill_date.strftime("%d %b") for r in records]
    refill_litres = [float(r.litres or 0) for r in records]

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
