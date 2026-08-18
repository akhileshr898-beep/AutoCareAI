from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Vehicle, ServiceRecord, FuelRecord, Reminder
from extensions import db
from helpers import predict_next_service, get_insurance_status, get_puc_status, calculate_fuel_statistics, generate_reminders
from datetime import datetime
import calendar

dashboard = Blueprint('dashboard', __name__)

@dashboard.route('/dashboard')
@login_required
def dashboard():
    generate_reminders(current_user)
    
    vehicles = Vehicle.query.filter_by(user_id=current_user.id).all()
    
    vehicle_data = {}
    stats = {
        'total_vehicles': len(vehicles),
        'upcoming_services': 0,
        'overdue_services': 0,
        'insurance_renewals': 0,
        'puc_renewals': 0,
        'total_maintenance_cost': 0,
        'monthly_maintenance': 0,
        'total_fuel_cost': 0,
        'avg_mileage': 0
    }
    
    total_fuel_litres = 0
    all_fuel_records = []
    recent_activities = []
    
    for v in vehicles:
        # Prediction
        pred = predict_next_service(v)
        if pred['status'] == 'due_soon':
            stats['upcoming_services'] += 1
        elif pred['status'] == 'overdue':
            stats['overdue_services'] += 1
            
        # Insurance & PUC
        ins = get_insurance_status(v)
        if ins in ['expiring_soon', 'expired']:
            stats['insurance_renewals'] += 1
            
        puc = get_puc_status(v)
        if puc in ['expiring_soon', 'expired']:
            stats['puc_renewals'] += 1
            
        # Costs
        svc_records = ServiceRecord.query.filter_by(vehicle_id=v.id).all()
        total_svc = sum(r.total_cost for r in svc_records if r.total_cost)
        stats['total_maintenance_cost'] += total_svc
        
        for r in svc_records:
            recent_activities.append({
                'date': r.service_date,
                'type': 'Service',
                'vehicle': v.vehicle_name,
                'cost': r.total_cost,
                'desc': r.service_type
            })
            
        fl_records = FuelRecord.query.filter_by(vehicle_id=v.id).all()
        all_fuel_records.extend(fl_records)
        fuel_stats = calculate_fuel_statistics(fl_records)
        
        fl_cost = 0
        v_mileage = 0
        if fuel_stats:
            fl_cost = fuel_stats['total_cost']
            v_mileage = fuel_stats['avg_mileage']
            stats['total_fuel_cost'] += fl_cost
            total_fuel_litres += fuel_stats['total_litres']
            
        for r in fl_records:
            recent_activities.append({
                'date': r.refill_date,
                'type': 'Fuel',
                'vehicle': v.vehicle_name,
                'cost': r.total_amount,
                'desc': f"{r.litres}L at {r.fuel_station or 'Unknown'}"
            })
            
        vehicle_data[v.id] = {
            'prediction': pred,
            'total_service_cost': total_svc,
            'total_fuel_cost': fl_cost,
            'avg_mileage': v_mileage,
            'insurance_status': ins,
            'puc_status': puc
        }
        
    if all_fuel_records and total_fuel_litres > 0:
        stats['avg_mileage'] = sum(fuel_stats['avg_mileage'] for fuel_stats in [calculate_fuel_statistics(FuelRecord.query.filter_by(vehicle_id=v.id).all())] if fuel_stats) / len(vehicles) if vehicles else 0
        
    # Sort activities
    recent_activities.sort(key=lambda x: x['date'], reverse=True)
    recent_activities = recent_activities[:10]
    
    # Mocking chart data for simplicity, usually you'd aggregate queries by month
    chart_data = {
        'maintenance_by_month': [],
        'fuel_by_month': [],
        'mileage_trend': [],
        'expense_categories': [
            {'category': 'Maintenance', 'amount': float(stats['total_maintenance_cost'])},
            {'category': 'Fuel', 'amount': float(stats['total_fuel_cost'])}
        ]
    }
    
    reminders = Reminder.query.filter_by(user_id=current_user.id, is_dismissed=False).order_by(Reminder.due_date).all()
    
    return render_template('dashboard/dashboard.html',
                           user=current_user,
                           vehicles=vehicles,
                           vehicle_data=vehicle_data,
                           stats=stats,
                           reminders=reminders,
                           chart_data=chart_data,
                           recent_activities=recent_activities)
