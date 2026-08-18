import os
from datetime import datetime
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import Vehicle
from extensions import db
from helpers import allowed_image, save_uploaded_file

vehicle = Blueprint('vehicle', __name__, url_prefix='/vehicles')

@vehicle.route("/add", methods=["GET", "POST"])
@login_required
def add_vehicle():
    if request.method == "POST":
        vehicle_name = request.form.get("vehicle_name", "").strip()
        company = request.form.get("company", "").strip()
        model = request.form.get("model", "").strip()
        registration_number = request.form.get("registration_number", "").strip().upper()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        fuel_type = request.form.get("fuel_type", "").strip()
        purchase_date_value = request.form.get("purchase_date", "").strip()
        odometer_value = request.form.get("odometer", "0").strip()

        if not all([vehicle_name, company, model, registration_number, vehicle_type, fuel_type]):
            flash("Complete all required fields.", "danger")
            return render_template("vehicle/add_vehicle.html")

        existing_vehicle = Vehicle.query.filter_by(registration_number=registration_number).first()
        if existing_vehicle:
            flash("This registration number already exists.", "warning")
            return render_template("vehicle/add_vehicle.html")

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("vehicle/add_vehicle.html")

        purchase_date = None
        if purchase_date_value:
            try:
                purchase_date = datetime.strptime(purchase_date_value, "%Y-%m-%d").date()
            except ValueError:
                flash("Enter a valid purchase date.", "danger")
                return render_template("vehicle/add_vehicle.html")

        image_filename = None
        vehicle_img = request.files.get("vehicle_image")
        if vehicle_img and vehicle_img.filename:
            if not allowed_image(vehicle_img.filename):
                flash("Only PNG, JPG, JPEG and WEBP images are allowed.", "danger")
                return render_template("vehicle/add_vehicle.html")
            image_filename = save_uploaded_file(
                vehicle_img,
                current_app.config["UPLOAD_FOLDER"],
                allowed_image,
            )

        new_vehicle = Vehicle(
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

        db.session.add(new_vehicle)
        db.session.commit()
        flash("Vehicle added successfully.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("vehicle/add_vehicle.html")

@vehicle.route("/edit/<int:vehicle_id>", methods=["GET", "POST"])
@login_required
def edit_vehicle(vehicle_id):
    veh = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()

    if request.method == "POST":
        vehicle_name = request.form.get("vehicle_name", "").strip()
        company = request.form.get("company", "").strip()
        model = request.form.get("model", "").strip()
        registration_number = request.form.get("registration_number", "").strip().upper()
        vehicle_type = request.form.get("vehicle_type", "").strip()
        fuel_type = request.form.get("fuel_type", "").strip()
        purchase_date_value = request.form.get("purchase_date", "").strip()
        odometer_value = request.form.get("odometer", "0").strip()

        if not all([vehicle_name, company, model, registration_number, vehicle_type, fuel_type]):
            flash("Complete all required fields.", "danger")
            return render_template("vehicle/edit_vehicle.html", vehicle=veh)

        duplicate_vehicle = Vehicle.query.filter(
            Vehicle.registration_number == registration_number,
            Vehicle.id != veh.id,
        ).first()

        if duplicate_vehicle:
            flash("Another vehicle already uses this registration number.", "warning")
            return render_template("vehicle/edit_vehicle.html", vehicle=veh)

        try:
            odometer = int(odometer_value)
            if odometer < 0:
                raise ValueError
        except ValueError:
            flash("Enter a valid odometer reading.", "danger")
            return render_template("vehicle/edit_vehicle.html", vehicle=veh)

        purchase_date = None
        if purchase_date_value:
            try:
                purchase_date = datetime.strptime(purchase_date_value, "%Y-%m-%d").date()
            except ValueError:
                flash("Enter a valid purchase date.", "danger")
                return render_template("vehicle/edit_vehicle.html", vehicle=veh)

        vehicle_img = request.files.get("vehicle_image")
        if vehicle_img and vehicle_img.filename:
            if not allowed_image(vehicle_img.filename):
                flash("Only PNG, JPG, JPEG and WEBP images are allowed.", "danger")
                return render_template("vehicle/edit_vehicle.html", vehicle=veh)

            old_image = veh.vehicle_image
            new_image_filename = save_uploaded_file(
                vehicle_img,
                current_app.config["UPLOAD_FOLDER"],
                allowed_image,
            )
            veh.vehicle_image = new_image_filename

            if old_image:
                old_image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], old_image)
                try:
                    if os.path.exists(old_image_path):
                        os.remove(old_image_path)
                except OSError:
                    current_app.logger.warning("Unable to remove old vehicle image: %s", old_image_path)

        veh.vehicle_name = vehicle_name
        veh.company = company
        veh.model = model
        veh.registration_number = registration_number
        veh.vehicle_type = vehicle_type
        veh.fuel_type = fuel_type
        veh.purchase_date = purchase_date
        veh.odometer = odometer

        db.session.commit()
        flash("Vehicle updated successfully.", "success")
        return redirect(url_for("dashboard.dashboard"))

    return render_template("vehicle/edit_vehicle.html", vehicle=veh)

@vehicle.route("/delete/<int:vehicle_id>", methods=["POST"])
@login_required
def delete_vehicle(vehicle_id):
    veh = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    image_filename = veh.vehicle_image
    
    db.session.delete(veh)
    db.session.commit()

    if image_filename:
        image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image_filename)
        try:
            if os.path.exists(image_path):
                os.remove(image_path)
        except OSError:
            current_app.logger.warning("Unable to remove deleted vehicle image: %s", image_path)

    flash("Vehicle and its related records were deleted successfully.", "success")
    return redirect(url_for("dashboard.dashboard"))

@vehicle.route("/add-vehicle")
@login_required
def add_vehicle_redirect():
    return redirect(url_for("vehicle.add_vehicle"))
