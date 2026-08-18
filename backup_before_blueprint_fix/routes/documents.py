import os
from io import BytesIO
from flask import Blueprint, request, flash, redirect, url_for, current_app, send_file
from flask_login import login_required, current_user
from models import Vehicle, VehicleDocument
from extensions import db
from helpers import allowed_document, save_uploaded_file

documents = Blueprint('documents', __name__, url_prefix='/documents')

@documents.route('/upload/<int:vehicle_id>', methods=['POST'])
@login_required
def upload_document(vehicle_id):
    vehicle = Vehicle.query.filter_by(id=vehicle_id, user_id=current_user.id).first_or_404()
    
    doc_type = request.form.get('document_type', 'other')
    doc_name = request.form.get('document_name', '').strip()
    
    if not doc_name:
        doc_name = doc_type.capitalize()
        
    doc_file = request.files.get('document_file')
    
    if not doc_file or not doc_file.filename:
        flash('No file selected.', 'danger')
        return redirect(request.referrer or url_for('dashboard.dashboard'))
        
    if not allowed_document(doc_file.filename):
        flash('Invalid file type. Only PDF, PNG, JPG, JPEG are allowed.', 'danger')
        return redirect(request.referrer or url_for('dashboard.dashboard'))
        
    # Check size
    doc_file.seek(0, os.SEEK_END)
    file_size = doc_file.tell()
    doc_file.seek(0)
    
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 5 * 1024 * 1024)
    if file_size > max_size:
        flash('File is too large.', 'danger')
        return redirect(request.referrer or url_for('dashboard.dashboard'))
        
    mime_type = doc_file.mimetype
    
    # Store approach: check if postgresql in URI for binary storage, else local
    db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI', '')
    
    try:
        new_doc = VehicleDocument(
            vehicle_id=vehicle.id,
            document_type=doc_type,
            document_name=doc_name,
            mime_type=mime_type,
            file_size=file_size
        )
        
        if 'postgresql' in db_uri.lower():
            new_doc.file_data = doc_file.read()
        else:
            filename = save_uploaded_file(
                doc_file, 
                current_app.config['UPLOAD_FOLDER'], 
                allowed_document
            )
            if not filename:
                raise ValueError("Failed to save file")
            new_doc.file_path = filename
            
        db.session.add(new_doc)
        db.session.commit()
        flash('Document uploaded successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Upload error: {str(e)}")
        flash('Error uploading document.', 'danger')
        
    return redirect(request.referrer or url_for('dashboard.dashboard'))

@documents.route('/view/<int:document_id>')
@login_required
def view_document(document_id):
    doc = VehicleDocument.query.join(Vehicle).filter(
        VehicleDocument.id == document_id,
        Vehicle.user_id == current_user.id
    ).first_or_404()
    
    if doc.file_data:
        return send_file(
            BytesIO(doc.file_data),
            mimetype=doc.mime_type,
            as_attachment=False,
            download_name=doc.document_name
        )
    elif doc.file_path:
        return send_file(
            os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path),
            mimetype=doc.mime_type,
            as_attachment=False,
            download_name=doc.document_name
        )
    
    flash('Document file not found.', 'danger')
    return redirect(request.referrer or url_for('dashboard.dashboard'))

@documents.route('/delete/<int:document_id>', methods=['POST'])
@login_required
def delete_document(document_id):
    doc = VehicleDocument.query.join(Vehicle).filter(
        VehicleDocument.id == document_id,
        Vehicle.user_id == current_user.id
    ).first_or_404()
    
    try:
        if doc.file_path:
            file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], doc.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
                
        db.session.delete(doc)
        db.session.commit()
        flash('Document deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Delete error: {str(e)}")
        flash('Error deleting document.', 'danger')
        
    return redirect(request.referrer or url_for('dashboard.dashboard'))
