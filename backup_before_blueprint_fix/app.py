import os
from datetime import datetime, timezone
from urllib.parse import quote_plus
from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import Flask, render_template, send_from_directory, jsonify

from extensions import db, login_manager, migrate, csrf
from routes import (
    auth, dashboard, vehicle, service, 
    fuel, garage, insurance, documents, api
)
from models import User # needed to initialize models

load_dotenv()

app = Flask(__name__)

# Basic Config
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'autocare-ai-secret-key-default')

# Database Config
db_url = os.environ.get('DATABASE_URL')
if not db_url:
    # fallback to localhost if no env
    mysql_password = quote_plus("akhi@123")
    db_url = f"mysql+pymysql://root:{mysql_password}@localhost:3306/autocare_ai"
elif db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# File Upload Config
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB
app.config['UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads')
app.config['INVOICE_UPLOAD_FOLDER'] = os.path.join(app.root_path, 'static', 'uploads', 'invoices')

# Production Security Headers
if os.environ.get('FLASK_ENV') == 'production':
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Initialize Extensions
db.init_app(app)
login_manager.init_app(app)
migrate.init_app(app, db)
csrf.init_app(app)

# Register Blueprints
app.register_blueprint(auth)
app.register_blueprint(dashboard)
app.register_blueprint(vehicle)
app.register_blueprint(service)
app.register_blueprint(fuel)
app.register_blueprint(garage)
app.register_blueprint(insurance)
app.register_blueprint(documents)
app.register_blueprint(api)

# Error Handlers
@app.errorhandler(400)
def bad_request_error(error):
    return render_template('errors/400.html'), 400

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('errors/403.html'), 403

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(413)
def request_entity_too_large_error(error):
    return render_template('errors/413.html'), 413

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# Base Routes
@app.route('/health')
@csrf.exempt
def health_check():
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/offline')
def offline():
    return render_template('offline.html')

@app.route('/service-worker.js')
def service_worker():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'service-worker.js',
        mimetype='application/javascript'
    )

# Setup context
with app.app_context():
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['INVOICE_UPLOAD_FOLDER'], exist_ok=True)
    db.create_all()

if __name__ == '__main__':
    app.run(debug=True)
