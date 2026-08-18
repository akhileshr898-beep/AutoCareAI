from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user
from models import Vehicle, ServiceRecord, FuelRecord
from helpers import predict_next_service, get_insurance_status, get_puc_status, get_vehicle_twin_data

garage = Blueprint('garage', __name__)

@garage.route('/garage/<int:vehicle_id>')
@login_required
def garage_view(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    prediction = predict_next_service(vehicle)
    
    service_records = ServiceRecord.query.filter_by(vehicle_id=vehicle.id).order_by(ServiceRecord.service_date.desc()).all()
    total_cost = sum(float(record.total_cost or 0) for record in service_records)
    service_count = len(service_records)
    
    fuel_records = FuelRecord.query.filter_by(vehicle_id=vehicle.id).order_by(FuelRecord.refill_date.desc()).all()
    
    health_score = 95
    if prediction.get("is_overdue", False):
        health_score -= 25
    if service_count == 0:
        health_score -= 10
        
    insurance_status = get_insurance_status(vehicle)
    puc_status = get_puc_status(vehicle)
    
    if insurance_status == 'expired':
        health_score -= 15
    if puc_status == 'expired':
        health_score -= 15
        
    health_score = max(min(health_score, 100), 0)
    
    return render_template('garage/garage.html',
                           vehicle=vehicle,
                           prediction=prediction,
                           service_records=service_records,
                           total_cost=total_cost,
                           service_count=service_count,
                           health_score=health_score,
                           insurance_status=insurance_status,
                           puc_status=puc_status,
                           fuel_records=fuel_records)

@garage.route('/vehicle-twin/<int:vehicle_id>')
@login_required
def vehicle_twin(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    twin_data = get_vehicle_twin_data(vehicle)
    return render_template('vehicle_twin.html', vehicle=vehicle, twin_data=twin_data)

@garage.route('/api/vehicle-twin-data/<int:vehicle_id>')
@login_required
def api_vehicle_twin_data(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    twin_data = get_vehicle_twin_data(vehicle)
    return jsonify(twin_data)
