import os
from datetime import datetime
from uuid import uuid4

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for
)

from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from models import db
from models.vehicle import Vehicle


vehicle_bp = Blueprint(
    "vehicle",
    __name__,
    url_prefix="/vehicles"
)


ALLOWED_EXTENSIONS = {
    "png",
    "jpg",
    "jpeg",
    "webp"
}


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


@vehicle_bp.route("/add", methods=["GET", "POST"])
@login_required
def add_vehicle():
    if request.method == "POST":
        vehicle_name = request.form.get(
            "vehicle_name",
            ""
        ).strip()

        company = request.form.get(
            "company",
            ""
        ).strip()

        model = request.form.get(
            "model",
            ""
        ).strip()

        registration_number = request.form.get(
            "registration_number",
            ""
        ).strip().upper()

        vehicle_type = request.form.get(
            "vehicle_type",
            ""
        ).strip()

        fuel_type = request.form.get(
            "fuel_type",
            ""
        ).strip()

        purchase_date_value = request.form.get(
            "purchase_date",
            ""
        ).strip()

        odometer_value = request.form.get(
            "odometer",
            "0"
        ).strip()

        if (
            not vehicle_name
            or not company
            or not model
            or not registration_number
            or not vehicle_type
            or not fuel_type
        ):
            flash(
                "Please complete all required fields.",
                "danger"
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        existing_vehicle = Vehicle.query.filter_by(
            registration_number=registration_number
        ).first()

        if existing_vehicle:
            flash(
                "This registration number is already added.",
                "warning"
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        try:
            odometer = int(odometer_value)

            if odometer < 0:
                raise ValueError

        except ValueError:
            flash(
                "Enter a valid odometer reading.",
                "danger"
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        purchase_date = None

        if purchase_date_value:
            try:
                purchase_date = datetime.strptime(
                    purchase_date_value,
                    "%Y-%m-%d"
                ).date()

            except ValueError:
                flash(
                    "Enter a valid purchase date.",
                    "danger"
                )

                return render_template(
                    "vehicle/add_vehicle.html"
                )

        image_filename = None
        uploaded_image = request.files.get(
            "vehicle_image"
        )

        if uploaded_image and uploaded_image.filename:
            if not allowed_file(uploaded_image.filename):
                flash(
                    "Only PNG, JPG, JPEG and WEBP images are allowed.",
                    "danger"
                )

                return render_template(
                    "vehicle/add_vehicle.html"
                )

            original_name = secure_filename(
                uploaded_image.filename
            )

            extension = original_name.rsplit(
                ".",
                1
            )[1].lower()

            image_filename = (
                f"{uuid4().hex}.{extension}"
            )

            upload_folder = current_app.config[
                "UPLOAD_FOLDER"
            ]

            os.makedirs(
                upload_folder,
                exist_ok=True
            )

            uploaded_image.save(
                os.path.join(
                    upload_folder,
                    image_filename
                )
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
            vehicle_image=image_filename
        )

        db.session.add(vehicle)
        db.session.commit()

        flash(
            "Vehicle added successfully.",
            "success"
        )

        return redirect(
            url_for("dashboard.dashboard")
        )

    return render_template(
        "vehicle/add_vehicle.html"
    )