import os
from datetime import datetime
from decimal import Decimal, InvalidOperation

from flask import (
    Blueprint,
    render_template,
    request,
    flash,
    redirect,
    url_for,
    current_app,
    jsonify,
)
from flask_login import login_required, current_user

from models import Vehicle
from extensions import db
from helpers import allowed_image, save_uploaded_file


vehicle = Blueprint(
    "vehicle",
    __name__,
    url_prefix="/vehicles",
)


# ============================================================
# COMMON HELPERS
# ============================================================

def _parse_optional_date(value, field_label):
    value = (value or "").strip()

    if not value:
        return None

    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).date()

    except ValueError as exc:
        raise ValueError(
            f"Enter a valid {field_label}."
        ) from exc


def _parse_optional_int(
    value,
    field_label,
    minimum=None,
):
    value = (value or "").strip()

    if not value:
        return None

    try:
        result = int(value)

    except ValueError as exc:
        raise ValueError(
            f"Enter a valid {field_label}."
        ) from exc

    if minimum is not None and result < minimum:
        raise ValueError(
            f"{field_label} cannot be below {minimum}."
        )

    return result


def _parse_optional_decimal(
    value,
    field_label,
    minimum=None,
):
    value = (value or "").strip()

    if not value:
        return None

    try:
        result = Decimal(value)

    except (InvalidOperation, ValueError) as exc:
        raise ValueError(
            f"Enter a valid {field_label}."
        ) from exc

    if minimum is not None and result < minimum:
        raise ValueError(
            f"{field_label} cannot be below {minimum}."
        )

    return result


# ============================================================
# RC / INSURANCE / PUC DOCUMENT EXTRACTION API
# ============================================================

@vehicle.route(
    "/api/extract-documents",
    methods=["POST"],
)
@login_required
def extract_vehicle_document_details():
    """
    Upload up to three RC / insurance / PUC files and return
    vehicle-related fields that AutoCare AI can use to auto-fill
    the Add Vehicle form.

    This is document extraction only. It is not government,
    insurer or VAHAN verification.
    """

    uploaded_files = request.files.getlist(
        "documents"
    )

    if not uploaded_files:
        return jsonify(
            {
                "success": False,
                "message": (
                    "Choose at least one RC, insurance or PUC "
                    "file before extracting details."
                ),
            }
        ), 400

    try:
        from document_extractor import (
            DocumentExtractionError,
            extract_vehicle_documents,
        )

        result = extract_vehicle_documents(
            uploaded_files
        )

        return jsonify(
            {
                "success": True,
                "verified": False,
                "source": "document_extraction",
                "source_label": "Document scan",
                "message": (
                    "Available details were extracted. "
                    "Review them before saving."
                ),
                "details": result["details"],
                "documents": result["documents"],
                "warnings": result["warnings"],
                "recognized_fields": result[
                    "recognized_fields"
                ],
            }
        )

    except ImportError:
        current_app.logger.exception(
            "Document extraction dependency error"
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "Document extraction dependencies are missing. "
                    "Install pdfplumber, Pillow and pytesseract."
                ),
            }
        ), 500

    except Exception as error:
        try:
            from document_extractor import (
                DocumentExtractionError,
            )
        except Exception:
            DocumentExtractionError = None

        if (
            DocumentExtractionError
            and isinstance(
                error,
                DocumentExtractionError,
            )
        ):
            return jsonify(
                {
                    "success": False,
                    "message": str(error),
                }
            ), 422

        current_app.logger.exception(
            "Vehicle document extraction failed"
        )

        return jsonify(
            {
                "success": False,
                "message": (
                    "The document could not be processed. "
                    "Check the server console for details."
                ),
            }
        ), 500


# ============================================================
# ADD VEHICLE
# ============================================================

@vehicle.route(
    "/add",
    methods=["GET", "POST"],
)
@login_required
def add_vehicle():
    if request.method == "POST":
        vehicle_name = request.form.get(
            "vehicle_name",
            "",
        ).strip()

        company = request.form.get(
            "company",
            "",
        ).strip()

        model = request.form.get(
            "model",
            "",
        ).strip()

        registration_number = request.form.get(
            "registration_number",
            "",
        ).strip().upper()

        vehicle_type = request.form.get(
            "vehicle_type",
            "",
        ).strip()

        fuel_type = request.form.get(
            "fuel_type",
            "",
        ).strip()

        if not all(
            [
                vehicle_name,
                company,
                model,
                registration_number,
                vehicle_type,
                fuel_type,
            ]
        ):
            flash(
                "Complete all required fields.",
                "danger",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        existing_vehicle = Vehicle.query.filter_by(
            registration_number=registration_number
        ).first()

        if existing_vehicle:
            flash(
                "This registration number already exists.",
                "warning",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        try:
            odometer = int(
                request.form.get(
                    "odometer",
                    "0",
                ).strip()
                or "0"
            )

            if odometer < 0:
                raise ValueError

            purchase_date = _parse_optional_date(
                request.form.get(
                    "purchase_date",
                    ""
                ),
                "purchase date",
            )

            manufacturing_year = (
                _parse_optional_int(
                    request.form.get(
                        "manufacturing_year",
                        ""
                    ),
                    "manufacturing year",
                    1950,
                )
            )

            last_service_date = (
                _parse_optional_date(
                    request.form.get(
                        "last_service_date",
                        ""
                    ),
                    "last service date",
                )
            )

            last_service_odometer = (
                _parse_optional_int(
                    request.form.get(
                        "last_service_odometer",
                        ""
                    ),
                    "last service odometer",
                    0,
                )
            )

            avg_daily_km = (
                _parse_optional_int(
                    request.form.get(
                        "avg_daily_km",
                        ""
                    ),
                    "average daily kilometres",
                    0,
                )
            )

            service_interval_km = (
                _parse_optional_int(
                    request.form.get(
                        "service_interval_km",
                        ""
                    ),
                    "service interval",
                    100,
                )
            )

            service_interval_months = (
                _parse_optional_int(
                    request.form.get(
                        "service_interval_months",
                        ""
                    ),
                    "service interval months",
                    1,
                )
            )

            insurance_start_date = (
                _parse_optional_date(
                    request.form.get(
                        "insurance_start_date",
                        ""
                    ),
                    "insurance start date",
                )
            )

            insurance_expiry = (
                _parse_optional_date(
                    request.form.get(
                        "insurance_expiry",
                        ""
                    ),
                    "insurance expiry date",
                )
            )

            insurance_premium = (
                _parse_optional_decimal(
                    request.form.get(
                        "insurance_premium",
                        ""
                    ),
                    "insurance premium",
                    Decimal("0"),
                )
            )

            puc_issue_date = (
                _parse_optional_date(
                    request.form.get(
                        "puc_issue_date",
                        ""
                    ),
                    "PUC issue date",
                )
            )

            puc_expiry = (
                _parse_optional_date(
                    request.form.get(
                        "puc_expiry",
                        ""
                    ),
                    "PUC expiry date",
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "danger",
            )

            return render_template(
                "vehicle/add_vehicle.html"
            )

        image_filename = None

        vehicle_img = request.files.get(
            "vehicle_image"
        )

        if vehicle_img and vehicle_img.filename:
            if not allowed_image(
                vehicle_img.filename
            ):
                flash(
                    "Only PNG, JPG, JPEG and WEBP "
                    "images are allowed.",
                    "danger",
                )

                return render_template(
                    "vehicle/add_vehicle.html"
                )

            image_filename = save_uploaded_file(
                vehicle_img,
                current_app.config[
                    "UPLOAD_FOLDER"
                ],
                allowed_image,
            )

        new_vehicle = Vehicle(
            user_id=current_user.id,
            vehicle_name=vehicle_name,
            company=company,
            model=model,
            variant=(
                request.form.get(
                    "variant",
                    ""
                ).strip()
                or None
            ),
            vehicle_type=vehicle_type,
            fuel_type=fuel_type,
            transmission=(
                request.form.get(
                    "transmission",
                    ""
                ).strip()
                or None
            ),
            manufacturing_year=(
                manufacturing_year
            ),
            registration_number=(
                registration_number
            ),
            purchase_date=purchase_date,
            odometer=odometer,
            last_service_date=(
                last_service_date
            ),
            last_service_odometer=(
                last_service_odometer
            ),
            avg_daily_km=(
                avg_daily_km
                if avg_daily_km is not None
                else 30
            ),
            service_interval_km=(
                service_interval_km
                if service_interval_km is not None
                else 5000
            ),
            service_interval_months=(
                service_interval_months
                if service_interval_months is not None
                else 6
            ),
            insurance_provider=(
                request.form.get(
                    "insurance_provider",
                    ""
                ).strip()
                or None
            ),
            insurance_policy_number=(
                request.form.get(
                    "insurance_policy_number",
                    ""
                ).strip()
                or None
            ),
            insurance_start_date=(
                insurance_start_date
            ),
            insurance_expiry=(
                insurance_expiry
            ),
            insurance_premium=(
                insurance_premium
            ),
            puc_certificate_number=(
                request.form.get(
                    "puc_certificate_number",
                    ""
                ).strip()
                or None
            ),
            puc_issue_date=(
                puc_issue_date
            ),
            puc_expiry=puc_expiry,
            vehicle_image=image_filename,
            nickname=(
                request.form.get(
                    "nickname",
                    ""
                ).strip()
                or None
            ),
        )

        db.session.add(
            new_vehicle
        )
        db.session.commit()

        flash(
            "Vehicle added successfully.",
            "success",
        )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "vehicle/add_vehicle.html"
    )


# ============================================================
# EDIT VEHICLE
# ============================================================

@vehicle.route(
    "/edit/<int:vehicle_id>",
    methods=["GET", "POST"],
)
@login_required
def edit_vehicle(vehicle_id):
    veh = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    if request.method == "POST":
        vehicle_name = request.form.get(
            "vehicle_name",
            "",
        ).strip()

        company = request.form.get(
            "company",
            "",
        ).strip()

        model = request.form.get(
            "model",
            "",
        ).strip()

        registration_number = request.form.get(
            "registration_number",
            "",
        ).strip().upper()

        vehicle_type = request.form.get(
            "vehicle_type",
            "",
        ).strip()

        fuel_type = request.form.get(
            "fuel_type",
            "",
        ).strip()

        if not all(
            [
                vehicle_name,
                company,
                model,
                registration_number,
                vehicle_type,
                fuel_type,
            ]
        ):
            flash(
                "Complete all required fields.",
                "danger",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=veh,
            )

        duplicate_vehicle = Vehicle.query.filter(
            Vehicle.registration_number
            == registration_number,
            Vehicle.id != veh.id,
        ).first()

        if duplicate_vehicle:
            flash(
                "Another vehicle already uses this "
                "registration number.",
                "warning",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=veh,
            )

        try:
            odometer = int(
                request.form.get(
                    "odometer",
                    "0",
                ).strip()
                or "0"
            )

            if odometer < 0:
                raise ValueError

            purchase_date = _parse_optional_date(
                request.form.get(
                    "purchase_date",
                    ""
                ),
                "purchase date",
            )

            manufacturing_year = (
                _parse_optional_int(
                    request.form.get(
                        "manufacturing_year",
                        ""
                    ),
                    "manufacturing year",
                    1950,
                )
            )

            last_service_date = (
                _parse_optional_date(
                    request.form.get(
                        "last_service_date",
                        ""
                    ),
                    "last service date",
                )
            )

            last_service_odometer = (
                _parse_optional_int(
                    request.form.get(
                        "last_service_odometer",
                        ""
                    ),
                    "last service odometer",
                    0,
                )
            )

            avg_daily_km = (
                _parse_optional_int(
                    request.form.get(
                        "avg_daily_km",
                        ""
                    ),
                    "average daily kilometres",
                    0,
                )
            )

            service_interval_km = (
                _parse_optional_int(
                    request.form.get(
                        "service_interval_km",
                        ""
                    ),
                    "service interval",
                    100,
                )
            )

            service_interval_months = (
                _parse_optional_int(
                    request.form.get(
                        "service_interval_months",
                        ""
                    ),
                    "service interval months",
                    1,
                )
            )

            insurance_start_date = (
                _parse_optional_date(
                    request.form.get(
                        "insurance_start_date",
                        ""
                    ),
                    "insurance start date",
                )
            )

            insurance_expiry = (
                _parse_optional_date(
                    request.form.get(
                        "insurance_expiry",
                        ""
                    ),
                    "insurance expiry date",
                )
            )

            insurance_premium = (
                _parse_optional_decimal(
                    request.form.get(
                        "insurance_premium",
                        ""
                    ),
                    "insurance premium",
                    Decimal("0"),
                )
            )

            puc_issue_date = (
                _parse_optional_date(
                    request.form.get(
                        "puc_issue_date",
                        ""
                    ),
                    "PUC issue date",
                )
            )

            puc_expiry = (
                _parse_optional_date(
                    request.form.get(
                        "puc_expiry",
                        ""
                    ),
                    "PUC expiry date",
                )
            )

        except ValueError as error:
            flash(
                str(error),
                "danger",
            )

            return render_template(
                "vehicle/edit_vehicle.html",
                vehicle=veh,
            )

        vehicle_img = request.files.get(
            "vehicle_image"
        )

        if vehicle_img and vehicle_img.filename:
            if not allowed_image(
                vehicle_img.filename
            ):
                flash(
                    "Only PNG, JPG, JPEG and WEBP "
                    "images are allowed.",
                    "danger",
                )

                return render_template(
                    "vehicle/edit_vehicle.html",
                    vehicle=veh,
                )

            old_image = veh.vehicle_image

            new_image_filename = save_uploaded_file(
                vehicle_img,
                current_app.config[
                    "UPLOAD_FOLDER"
                ],
                allowed_image,
            )

            veh.vehicle_image = (
                new_image_filename
            )

            if old_image:
                old_image_path = os.path.join(
                    current_app.config[
                        "UPLOAD_FOLDER"
                    ],
                    old_image,
                )

                try:
                    if os.path.exists(
                        old_image_path
                    ):
                        os.remove(
                            old_image_path
                        )

                except OSError:
                    current_app.logger.warning(
                        "Unable to remove old vehicle "
                        "image: %s",
                        old_image_path,
                    )

        veh.vehicle_name = vehicle_name
        veh.company = company
        veh.model = model
        veh.variant = (
            request.form.get(
                "variant",
                ""
            ).strip()
            or None
        )
        veh.vehicle_type = vehicle_type
        veh.fuel_type = fuel_type
        veh.transmission = (
            request.form.get(
                "transmission",
                ""
            ).strip()
            or None
        )
        veh.manufacturing_year = (
            manufacturing_year
        )
        veh.registration_number = (
            registration_number
        )
        veh.purchase_date = purchase_date
        veh.odometer = odometer
        veh.last_service_date = (
            last_service_date
        )
        veh.last_service_odometer = (
            last_service_odometer
        )
        veh.avg_daily_km = (
            avg_daily_km
            if avg_daily_km is not None
            else 30
        )
        veh.service_interval_km = (
            service_interval_km
            if service_interval_km is not None
            else 5000
        )
        veh.service_interval_months = (
            service_interval_months
            if service_interval_months is not None
            else 6
        )
        veh.insurance_provider = (
            request.form.get(
                "insurance_provider",
                ""
            ).strip()
            or None
        )
        veh.insurance_policy_number = (
            request.form.get(
                "insurance_policy_number",
                ""
            ).strip()
            or None
        )
        veh.insurance_start_date = (
            insurance_start_date
        )
        veh.insurance_expiry = (
            insurance_expiry
        )
        veh.insurance_premium = (
            insurance_premium
        )
        veh.puc_certificate_number = (
            request.form.get(
                "puc_certificate_number",
                ""
            ).strip()
            or None
        )
        veh.puc_issue_date = (
            puc_issue_date
        )
        veh.puc_expiry = puc_expiry
        veh.nickname = (
            request.form.get(
                "nickname",
                ""
            ).strip()
            or None
        )

        db.session.commit()

        flash(
            "Vehicle updated successfully.",
            "success",
        )

        return redirect(
            url_for(
                "dashboard.dashboard"
            )
        )

    return render_template(
        "vehicle/edit_vehicle.html",
        vehicle=veh,
    )


# ============================================================
# DELETE VEHICLE
# ============================================================

@vehicle.route(
    "/delete/<int:vehicle_id>",
    methods=["POST"],
)
@login_required
def delete_vehicle(vehicle_id):
    veh = Vehicle.query.filter_by(
        id=vehicle_id,
        user_id=current_user.id,
    ).first_or_404()

    image_filename = veh.vehicle_image

    db.session.delete(
        veh
    )
    db.session.commit()

    if image_filename:
        image_path = os.path.join(
            current_app.config[
                "UPLOAD_FOLDER"
            ],
            image_filename,
        )

        try:
            if os.path.exists(
                image_path
            ):
                os.remove(
                    image_path
                )

        except OSError:
            current_app.logger.warning(
                "Unable to remove deleted "
                "vehicle image: %s",
                image_path,
            )

    flash(
        "Vehicle and its related records were "
        "deleted successfully.",
        "success",
    )

    return redirect(
        url_for(
            "dashboard.dashboard"
        )
    )


@vehicle.route("/add-vehicle")
@login_required
def add_vehicle_redirect():
    return redirect(
        url_for(
            "vehicle.add_vehicle"
        )
    )