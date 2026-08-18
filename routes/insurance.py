from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required, current_user
from models import Vehicle, VehicleDocument
from extensions import db
from datetime import datetime
from decimal import Decimal, InvalidOperation

insurance = Blueprint('insurance', __name__, url_prefix='/insurance-legacy')

@insurance.route('/<int:vehicle_id>', methods=['GET', 'POST'])
@login_required
def insurance_puc(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    
    if request.method == 'POST':
        try:
            # Insurance Fields
            vehicle.insurance_provider = request.form.get('insurance_provider', '').strip() or None
            vehicle.insurance_policy_number = request.form.get('insurance_policy_number', '').strip() or None
            
            start_date_str = request.form.get('insurance_start_date', '').strip()
            if start_date_str:
                vehicle.insurance_start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
            else:
                vehicle.insurance_start_date = None
                
            expiry_str = request.form.get('insurance_expiry', '').strip()
            if expiry_str:
                vehicle.insurance_expiry = datetime.strptime(expiry_str, "%Y-%m-%d").date()
            else:
                vehicle.insurance_expiry = None
                
            premium_str = request.form.get('insurance_premium', '').strip()
            if premium_str:
                premium = Decimal(premium_str)
                if premium < 0:
                    raise ValueError("Premium cannot be negative")
                vehicle.insurance_premium = premium
            else:
                vehicle.insurance_premium = None

            # PUC Fields
            vehicle.puc_certificate_number = request.form.get('puc_certificate_number', '').strip() or None
            
            puc_issue_str = request.form.get('puc_issue_date', '').strip()
            if puc_issue_str:
                vehicle.puc_issue_date = datetime.strptime(puc_issue_str, "%Y-%m-%d").date()
            else:
                vehicle.puc_issue_date = None
                
            puc_expiry_str = request.form.get('puc_expiry', '').strip()
            if puc_expiry_str:
                vehicle.puc_expiry = datetime.strptime(puc_expiry_str, "%Y-%m-%d").date()
            else:
                vehicle.puc_expiry = None

            db.session.commit()
            flash('Insurance and PUC details updated successfully.', 'success')
            return redirect(url_for('insurance.insurance_puc', vehicle_id=vehicle.id))
            
        except (ValueError, InvalidOperation) as e:
            db.session.rollback()
            flash('Invalid data provided. Please check dates and numbers.', 'danger')
            
    documents = VehicleDocument.query.filter_by(vehicle_id=vehicle.id).filter(VehicleDocument.document_type.in_(['insurance', 'puc'])).all()
    
    return render_template('garage/insurance_puc.html', vehicle=vehicle, documents=documents)
