
# Ensures the routes module is treated as a package.
# We will import blueprints from their respective modules in app.py or here.

from .auth import auth
from .dashboard import dashboard_bp
from .vehicle import vehicle
from .service import service
from .fuel import fuel
from .garage import garage_bp
from .insurance import insurance
from .documents import documents
from .api import api

__all__ = [
    'auth',
    'dashboard_bp',
    'vehicle',
    'service',
    'fuel',
    'garage_bp',
    'insurance',
    'documents',
    'api'
]
