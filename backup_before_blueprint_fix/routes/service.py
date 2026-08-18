import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import Vehicle, ServiceRecord
from extensions import db
from helpers import predict_next_service, allowed_document, save_uploaded_file

service = Blueprint('service', __name__, url_prefix='/service')

@service.route("/add/<int:vehicle_id>", methods=["GET", "POST"])
@login_required
def add_service(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        service_date_value = request.form.get("service_date", "").strip()
        odometer_value = request.form.get("odometer", "").strip()
        service_type = request.form.get("service_type", "").strip()
        service_center = request.form.get("service_center", "").strip()
        work_done = request.form.get("work_done", "").strip()
        engine_oil = request.form.get("engine_oil", "").strip()
        total_cost_value = request.form.get("total_cost", "0").strip()
        notes = request.form.get("notes", "").strip()

        if not all([service_date_value, odometer_value, service_type]):
            flash("Service date, odometer and service type are required.", "danger")
            return render_template("service/add_service.html", vehicle=vehicle)

        try:
            service_date = datetime.strptime(service_date_value, "%Y-%m-%d").date()
        except ValueError:
            flash("Enter a valid service date.", "danger")
            return render_template("service/add_service.html", vehicle=vehicle)

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("service/add_service.html", vehicle=vehicle)

        try:
            total_cost = Decimal(total_cost_value or "0")
            if total_cost < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            flash("Enter a valid service cost.", "danger")
            return render_template("service/add_service.html", vehicle=vehicle)

        invoice_filename = None
        invoice_file = request.files.get("invoice_file")
        if invoice_file and invoice_file.filename:
            if not allowed_document(invoice_file.filename):
                flash("Invoice must be PDF, PNG, JPG or JPEG.", "danger")
                return render_template("service/add_service.html", vehicle=vehicle)
            invoice_filename = save_uploaded_file(
                invoice_file,
                current_app.config["INVOICE_UPLOAD_FOLDER"],
                allowed_document,
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

        db.session.add(service_record)

        if odometer > vehicle.odometer:
            vehicle.odometer = odometer
            
        if not vehicle.last_service_date or service_date >= vehicle.last_service_date:
            vehicle.last_service_date = service_date
            vehicle.last_service_odometer = odometer

        db.session.commit()
        flash("Service record saved successfully.", "success")
        return redirect(url_for("service.service_history", vehicle_id=vehicle.id))

    return render_template("service/add_service.html", vehicle=vehicle)

@service.route("/history/<int:vehicle_id>")
@login_required
def service_history(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    records = ServiceRecord.query.filter_by(vehicle_id=vehicle.id).order_by(
        ServiceRecord.service_date.desc(), ServiceRecord.created_at.desc()
    ).all()

    total_spent = sum(float(record.total_cost or 0) for record in records)
    prediction = predict_next_service(vehicle)

    return render_template("service/history.html", vehicle=vehicle, records=records, total_spent=total_spent, prediction=prediction)

@service.route("/edit/<int:service_id>", methods=["GET", "POST"])
@login_required
def edit_service(service_id):
    service_record = ServiceRecord.query.join(Vehicle).filter(
        ServiceRecord.id == service_id,
        Vehicle.user_id == current_user.id
    ).first_or_404()
    
    vehicle = service_record.vehicle

    if request.method == "POST":
        service_date_value = request.form.get("service_date", "").strip()
        odometer_value = request.form.get("odometer", "").strip()
        service_type = request.form.get("service_type", "").strip()
        service_center = request.form.get("service_center", "").strip()
        work_done = request.form.get("work_done", "").strip()
        engine_oil = request.form.get("engine_oil", "").strip()
        total_cost_value = request.form.get("total_cost", "0").strip()
        notes = request.form.get("notes", "").strip()

        if not all([service_date_value, odometer_value, service_type]):
            flash("Service date, odometer and service type are required.", "danger")
            return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)

        try:
            service_date = datetime.strptime(service_date_value, "%Y-%m-%d").date()
        except ValueError:
            flash("Enter a valid service date.", "danger")
            return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)

        try:
            total_cost = Decimal(total_cost_value or "0")
            if total_cost < 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            flash("Enter a valid service cost.", "danger")
            return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)

        invoice_file = request.files.get("invoice_file")
        if invoice_file and invoice_file.filename:
            if not allowed_document(invoice_file.filename):
                flash("Invoice must be PDF, PNG, JPG or JPEG.", "danger")
                return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)
            
            old_invoice = service_record.invoice_file
            invoice_filename = save_uploaded_file(
                invoice_file,
                current_app.config["INVOICE_UPLOAD_FOLDER"],
                allowed_document,
            )
            service_record.invoice_file = invoice_filename
            
            if old_invoice:
                old_path = os.path.join(current_app.config["INVOICE_UPLOAD_FOLDER"], old_invoice)
                if os.path.exists(old_path):
                    os.remove(old_path)

        service_record.service_date = service_date
        service_record.odometer = odometer
        service_record.service_type = service_type
        service_record.service_center = service_center or None
        service_record.work_done = work_done or None
        service_record.engine_oil = engine_oil or None
        service_record.total_cost = total_cost
        service_record.notes = notes or None

        # Recompute vehicle max odometer and latest service date
        db.session.flush()
        
        highest_odo = db.session.query(db.func.max(ServiceRecord.odometer)).filter(ServiceRecord.vehicle_id == vehicle.id).scalar() or 0
        if highest_odo > vehicle.odometer:
            vehicle.odometer = highest_odo
            
        latest_service = ServiceRecord.query.filter_by(vehicle_id=vehicle.id).order_by(ServiceRecord.service_date.desc()).first()
        if latest_service:
            vehicle.last_service_date = latest_service.service_date
            vehicle.last_service_odometer = latest_service.odometer
        else:
            vehicle.last_service_date = None
            vehicle.last_service_odometer = None

        db.session.commit()
        flash("Service record updated successfully.", "success")
        return redirect(url_for("service.service_history", vehicle_id=vehicle.id))

    return render_template("service/edit_service.html", vehicle=vehicle, service_record=service_record)

@service.route("/delete/<int:service_id>", methods=["POST"])
@login_required
def delete_service(service_id):
    service_record = ServiceRecord.query.join(Vehicle).filter(
        ServiceRecord.id == service_id,
        Vehicle.user_id == current_user.id
    ).first_or_404()
    
    vehicle = service_record.vehicle
    invoice_file = service_record.invoice_file
    
    db.session.delete(service_record)
    db.session.flush()

    if invoice_file:
        file_path = os.path.join(current_app.config["INVOICE_UPLOAD_FOLDER"], invoice_file)
        if os.path.exists(file_path):
            os.remove(file_path)
            
    latest_service = ServiceRecord.query.filter_by(vehicle_id=vehicle.id).order_by(ServiceRecord.service_date.desc()).first()
    if latest_service:
        vehicle.last_service_date = latest_service.service_date
        vehicle.last_service_odometer = latest_service.odometer
    else:
        vehicle.last_service_date = None
        vehicle.last_service_odometer = None

    db.session.commit()
    flash("Service record deleted successfully.", "success")
    return redirect(url_for("service.service_history", vehicle_id=vehicle.id))
