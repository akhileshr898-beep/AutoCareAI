import os

# Ensures the routes module is treated as a package.
# We will import blueprints from their respective modules in app.py or here.

from .auth import auth
from .dashboard import dashboard
from .vehicle import vehicle
from .service import service
from .fuel import fuel
from .garage import garage
from .insurance import insurance
from .documents import documents
from .api import api

__all__ = [
    'auth',
    'dashboard',
    'vehicle',
    'service',
    'fuel',
    'garage',
    'insurance',
    'documents',
    'api'
]
