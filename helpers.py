import os
from uuid import uuid4
from datetime import date
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
from models import Reminder, db
import re
import secrets
from flask import current_app

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'glb'}
ALLOWED_DOC_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg'}

def allowed_image(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS

def allowed_document(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_DOC_EXTENSIONS

def save_uploaded_file(uploaded_file, upload_folder, validation_function):
    if not uploaded_file or not uploaded_file.filename:
        return None
    if not validation_function(uploaded_file.filename):
        return None
    safe_name = secure_filename(uploaded_file.filename)
    extension = safe_name.rsplit('.', 1)[1].lower()
    filename = f"{uuid4().hex}.{extension}"
    os.makedirs(upload_folder, exist_ok=True)
    uploaded_file.save(os.path.join(upload_folder, filename))
    return filename

def normalize_text(value):
    if not value:
        return ""
    return value.strip().lower()

def calculate_service_date(purchase_date, months):
    if not purchase_date or not months:
        return None
    whole_months = int(months)
    service_date = purchase_date + relativedelta(months=whole_months)
    if months != whole_months:
        service_date += relativedelta(days=15)
    return service_date

def predict_next_service(vehicle):
    # Calculates distance-based next service
    last_odo = vehicle.last_service_odometer or 0
    service_interval_km = vehicle.service_interval_km or 5000
    next_service_km = last_odo + service_interval_km

    # Calculates date-based next service
    service_interval_months = vehicle.service_interval_months or 6
    if vehicle.last_service_date:
        base_date = vehicle.last_service_date
    elif vehicle.purchase_date:
        base_date = vehicle.purchase_date
    else:
        base_date = None

    next_service_date = None
    if base_date:
        next_service_date = calculate_service_date(base_date, service_interval_months)

    current_odo = vehicle.odometer or 0
    today = date.today()

    remaining_km = max(next_service_km - current_odo, 0)
    remaining_days = None
    if next_service_date:
        remaining_days = (next_service_date - today).days

    is_overdue = False
    status = 'good'
    explanation = []

    if remaining_km <= 0:
        is_overdue = True
        explanation.append("Overdue by distance.")
    elif remaining_km <= 1000:
        status = 'due_soon'
        explanation.append("Service due soon based on distance.")
    
    if remaining_days is not None:
        if remaining_days < 0:
            is_overdue = True
            explanation.append("Overdue by time.")
        elif remaining_days <= 30:
            if status != 'due_soon' and not is_overdue:
                status = 'due_soon'
            explanation.append("Service due soon based on time.")

    if is_overdue:
        status = 'overdue'

    if not explanation:
        explanation.append("Service is up to date.")

    return {
        "supported": True,
        "next_service_date": next_service_date,
        "next_service_km": next_service_km,
        "remaining_km": remaining_km,
        "remaining_days": remaining_days,
        "is_overdue": is_overdue,
        "status": status,
        "explanation": " ".join(explanation)
    }

def get_insurance_status(vehicle):
    if not vehicle.insurance_expiry:
        return 'unknown'
    today = date.today()
    remaining = (vehicle.insurance_expiry - today).days
    if remaining < 0:
        return 'expired'
    elif remaining <= 30:
        return 'expiring_soon'
    return 'valid'

def get_puc_status(vehicle):
    if not vehicle.puc_expiry:
        return 'unknown'
    today = date.today()
    remaining = (vehicle.puc_expiry - today).days
    if remaining < 0:
        return 'expired'
    elif remaining <= 30:
        return 'expiring_soon'
    return 'valid'

def generate_reminders(user):
    for vehicle in user.vehicles:
        # Service Reminders
        pred = predict_next_service(vehicle)
        if pred['status'] in ['due_soon', 'overdue']:
            rtype = 'service_overdue' if pred['status'] == 'overdue' else 'service_due'
            title = f"{'Overdue' if rtype == 'service_overdue' else 'Upcoming'} Service for {vehicle.vehicle_name}"
            msg = pred['explanation']
            
            existing = Reminder.query.filter_by(vehicle_id=vehicle.id, reminder_type=rtype, is_dismissed=False).first()
            if not existing:
                r = Reminder(user_id=user.id, vehicle_id=vehicle.id, reminder_type=rtype, title=title, message=msg, due_date=pred['next_service_date'])
                db.session.add(r)
        
        # Insurance
        ins_status = get_insurance_status(vehicle)
        if ins_status in ['expiring_soon', 'expired']:
            rtype = 'insurance_expired' if ins_status == 'expired' else 'insurance_expiring'
            title = f"Insurance {'Expired' if ins_status == 'expired' else 'Expiring'} for {vehicle.vehicle_name}"
            msg = f"Insurance policy is {'expired' if ins_status == 'expired' else 'expiring on'} {vehicle.insurance_expiry}."
            
            existing = Reminder.query.filter_by(vehicle_id=vehicle.id, reminder_type=rtype, is_dismissed=False).first()
            if not existing:
                r = Reminder(user_id=user.id, vehicle_id=vehicle.id, reminder_type=rtype, title=title, message=msg, due_date=vehicle.insurance_expiry)
                db.session.add(r)
        
        # PUC
        puc_status = get_puc_status(vehicle)
        if puc_status in ['expiring_soon', 'expired']:
            rtype = 'puc_expired' if puc_status == 'expired' else 'puc_expiring'
            title = f"PUC {'Expired' if puc_status == 'expired' else 'Expiring'} for {vehicle.vehicle_name}"
            msg = f"PUC certificate is {'expired' if puc_status == 'expired' else 'expiring on'} {vehicle.puc_expiry}."
            
            existing = Reminder.query.filter_by(vehicle_id=vehicle.id, reminder_type=rtype, is_dismissed=False).first()
            if not existing:
                r = Reminder(user_id=user.id, vehicle_id=vehicle.id, reminder_type=rtype, title=title, message=msg, due_date=vehicle.puc_expiry)
                db.session.add(r)
                
    db.session.commit()

def get_vehicle_twin_data(vehicle):
    # This is a simplified digital twin structure based on requirements
    pred = predict_next_service(vehicle)
    ins = get_insurance_status(vehicle)
    puc = get_puc_status(vehicle)
    
    return {
        "engine": {"status": "unknown", "label": "Engine", "details": "No recent diagnostics", "last_update": None, "next_due": None},
        "engine_oil": {"status": pred['status'], "label": "Engine Oil", "details": pred['explanation'], "last_update": str(vehicle.last_service_date) if vehicle.last_service_date else None, "next_due": str(pred['next_service_date']) if pred['next_service_date'] else None},
        "battery": {"status": "unknown", "label": "Battery", "details": "Check during next service", "last_update": None, "next_due": None},
        "tyres": {"status": "unknown", "label": "Tyres", "details": "Check during next service", "last_update": None, "next_due": None},
        "brakes": {"status": "unknown", "label": "Brakes", "details": "Check during next service", "last_update": None, "next_due": None},
        "fuel": {"status": "good", "label": "Fuel System", "details": "Operating normally", "last_update": None, "next_due": None},
        "insurance": {"status": ins, "label": "Insurance", "details": "Valid" if ins == 'valid' else "Expiring/Expired", "last_update": None, "next_due": str(vehicle.insurance_expiry) if vehicle.insurance_expiry else None},
        "puc": {"status": puc, "label": "PUC", "details": "Valid" if puc == 'valid' else "Expiring/Expired", "last_update": None, "next_due": str(vehicle.puc_expiry) if vehicle.puc_expiry else None}
    }

def calculate_fuel_statistics(records):
    if not records:
        return None
        
    records = sorted(records, key=lambda r: r.odometer)
    total_fuel = sum(r.litres for r in records)
    total_cost = sum(r.total_amount for r in records)
    
    avg_mileage = 0
    if len(records) > 1:
        distance_covered = records[-1].odometer - records[0].odometer
        if distance_covered > 0 and total_fuel > 0:
            # Approximate mileage assuming we use total fuel except the first fill-up, 
            # but simple division is ok for now.
            avg_mileage = distance_covered / float(sum(r.litres for r in records[1:]))

    return {
        "total_litres": round(total_fuel, 2),
        "total_cost": round(total_cost, 2),
        "avg_mileage": round(avg_mileage, 2),
        "fill_ups": len(records)
    }

def validate_password(password):
    if len(password) < 10:
        return "Password must be at least 10 characters long."
    if not re.search(r"[A-Z]", password):
        return "Password must contain at least one uppercase letter."
    if not re.search(r"[a-z]", password):
        return "Password must contain at least one lowercase letter."
    if not re.search(r"[0-9]", password):
        return "Password must contain at least one number."
    if not re.search(r"[!@#$%^&*()_+\-=?.]", password):
        return "Password must contain at least one special character."
    return None

def generate_otp():
    return f"{secrets.randbelow(1000000):06d}"

def send_reset_email(to_email, otp):
    """
    Send a password-reset OTP email.
    Uses Flask-Mail (configured in app.py) so it respects MAIL_SUPPRESS_SEND
    in dev mode and uses the same SMTP connection pool as the rest of the app.
    Falls back to logging the OTP if credentials are not set.
    """
    from flask import current_app
    from flask_mail import Message
    from extensions import mail

    mail_username = os.environ.get("MAIL_USERNAME", "").strip()
    mail_password = os.environ.get("MAIL_PASSWORD", "").strip()

    # Dev-mode fallback: print OTP to console if no credentials are configured
    if not mail_username or not mail_password:
        current_app.logger.warning(
            f"[DEV MODE] No email credentials set. OTP for {to_email}: {otp}"
        )
        print(
            f"\n{'='*55}\n"
            f"DEV MODE — Email not sent.\n"
            f"OTP for {to_email}: {otp}\n"
            f"{'='*55}\n"
        )
        return True

    # --- Build a nice HTML email body ---
    html_body = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <style>
    body {{ font-family: Arial, sans-serif; background: #0f172a; margin: 0; padding: 0; }}
    .wrapper {{ max-width: 480px; margin: 40px auto; background: #1e293b;
                border-radius: 12px; overflow: hidden; }}
    .header {{ background: linear-gradient(135deg, #3b82f6, #6366f1);
               padding: 32px 24px; text-align: center; }}
    .header h1 {{ color: #fff; margin: 0; font-size: 24px; letter-spacing: 1px; }}
    .body {{ padding: 32px 24px; color: #e2e8f0; }}
    .otp {{ font-size: 40px; font-weight: bold; letter-spacing: 10px;
            text-align: center; color: #60a5fa; background: #0f172a;
            border-radius: 10px; padding: 20px; margin: 24px 0; }}
    .note {{ font-size: 13px; color: #94a3b8; text-align: center; margin-top: 16px; }}
    .footer {{ background: #0f172a; padding: 16px 24px; text-align: center;
               color: #475569; font-size: 12px; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="header">
      <h1>🚗 AutoCare AI</h1>
    </div>
    <div class="body">
      <p>Hello,</p>
      <p>We received a request to reset your <strong>AutoCare AI</strong> password.
         Use the verification code below — it expires in <strong>10 minutes</strong>.</p>
      <div class="otp">{otp}</div>
      <p class="note">If you did not request a password reset, you can safely ignore this email.</p>
    </div>
    <div class="footer">
      AutoCare AI &bull; Smart maintenance. Safer journeys.
    </div>
  </div>
</body>
</html>
"""

    plain_body = (
        f"AutoCare AI — Password Reset\n\n"
        f"Your verification code is: {otp}\n\n"
        f"This code expires in 10 minutes.\n"
        f"If you did not request a reset, ignore this email.\n\n"
        f"AutoCare AI — Smart maintenance. Safer journeys."
    )

    msg = Message(
        subject="AutoCare AI — Your Password Reset Code",
        recipients=[to_email],
        body=plain_body,
        html=html_body,
    )

    # Retry up to 2 times on transient failures
    for attempt in range(1, 3):
        try:
            mail.send(msg)
            current_app.logger.info(f"Reset email sent to {to_email} (attempt {attempt})")
            return True
        except Exception as exc:
            current_app.logger.error(
                f"Failed to send reset email to {to_email} "
                f"(attempt {attempt}/2): {exc}"
            )
            if attempt == 2:
                return False


