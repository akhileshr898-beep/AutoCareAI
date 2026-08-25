import os
from uuid import uuid4
from datetime import date
from dateutil.relativedelta import relativedelta
from werkzeug.utils import secure_filename
from models import Reminder, db
import re
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    mail_username = os.environ.get("MAIL_USERNAME")
    mail_password = os.environ.get("MAIL_PASSWORD")
    mail_from = os.environ.get("MAIL_FROM", mail_username)
    
    if not mail_username or not mail_password:
        current_app.logger.warning(f"Email credentials not configured. DEV MODE - OTP is: {otp}")
        print(f"\n{'='*50}\nDEV MODE: Email not sent.\nOTP for {to_email} is: {otp}\n{'='*50}\n")
        return True
        
    subject = "AutoCare AI - Password Reset Code"
    body = (
        "Hello,\n\n"
        "We received a request to reset your AutoCare AI password.\n\n"
        "Your verification code is:\n\n"
        f"{otp}\n\n"
        "This code expires in 10 minutes.\n\n"
        "If you did not request a password reset, you can ignore this email.\n\n"
        "AutoCare AI\n"
        "Smart maintenance. Safer journeys."
    )

    msg = MIMEMultipart()
    msg['From'] = mail_from
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(mail_username, mail_password)
        server.sendmail(mail_from, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        current_app.logger.error(f"Failed to send email: {e}")
        return False

