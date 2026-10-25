import os
import socket
import traceback
from datetime import datetime, timezone
from urllib.parse import quote_plus, urlparse, urlunparse

from dotenv import load_dotenv

# ============================================================
# LOAD ENVIRONMENT VARIABLES
# ============================================================

load_dotenv()


from werkzeug.middleware.proxy_fix import ProxyFix

from flask import (
    Flask,
    render_template,
    send_from_directory,
    jsonify,
    redirect,
    url_for,
)

from extensions import (
    db,
    login_manager,
    migrate,
    csrf,
    limiter,
    mail,
)

from routes import (
    auth,
    dashboard_bp,
    vehicle,
    service,
    fuel,
    garage_bp,
    insurance,
    documents,
    api,
)

from models import User


# ============================================================
# CREATE FLASK APPLICATION
# ============================================================

app = Flask(__name__)


# ============================================================
# BASIC CONFIGURATION
# ============================================================

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "autocare-ai-secret-key-default",
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

def configure_db_url(raw_url):
    if not raw_url:
        mysql_user = os.environ.get("MYSQL_USER", "root")
        mysql_password = quote_plus(os.environ.get("MYSQL_PASSWORD", "akhi@123"))
        mysql_host = os.environ.get("MYSQL_HOST", "localhost")
        mysql_port = os.environ.get("MYSQL_PORT", "3306")
        mysql_database = os.environ.get("MYSQL_DATABASE", "autocare_ai")
        return (
            f"mysql+pymysql://"
            f"{mysql_user}:"
            f"{mysql_password}"
            f"@{mysql_host}:"
            f"{mysql_port}/"
            f"{mysql_database}"
        )

    url = raw_url.strip()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg2://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

    # Render internal DNS fix: resolve dpg-xxxx-a to the region-specific public domain
    try:
        parsed = urlparse(url)
        host = parsed.hostname
        if host and host.startswith("dpg-") and ".render.com" not in host:
            try:
                socket.gethostbyname(host)
            except (socket.gaierror, socket.herror):
                for region in ["oregon", "frankfurt", "singapore", "ohio", "virginia"]:
                    candidate = f"{host}.{region}-postgres.render.com"
                    try:
                        socket.gethostbyname(candidate)
                        netloc = parsed.netloc.replace(host, candidate)
                        url = urlunparse(parsed._replace(netloc=netloc))
                        if "sslmode" not in url:
                            url += "?sslmode=require" if "?" not in url else "&sslmode=require"
                        print(f"Render DB host resolved to: {candidate}")
                        break
                    except (socket.gaierror, socket.herror):
                        continue
    except Exception as e:
        print(f"Error parsing database URL: {e}")

    # Validate remote connection or gracefully fall back to local SQLite
    if url.startswith("postgresql"):
        from sqlalchemy import create_engine, text
        try:
            test_engine = create_engine(url, connect_args={"connect_timeout": 5})
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            test_engine.dispose()
            print("Successfully connected to PostgreSQL database.")
        except Exception as conn_err:
            print(f"WARNING: PostgreSQL connection failed ({conn_err}).")
            fallback_path = os.path.join(app.root_path, "autocare.db")
            print(f"Falling back to local SQLite database: {fallback_path}")
            return f"sqlite:///{fallback_path}"

    return url

db_url = configure_db_url(os.environ.get("DATABASE_URL"))



app.config[
    "SQLALCHEMY_DATABASE_URI"
] = db_url


app.config[
    "SQLALCHEMY_TRACK_MODIFICATIONS"
] = False


# ============================================================
# FILE UPLOAD CONFIGURATION
# ============================================================

# Maximum request upload size = 20 MB
app.config[
    "MAX_CONTENT_LENGTH"
] = 20 * 1024 * 1024


# Vehicle images
app.config[
    "UPLOAD_FOLDER"
] = os.path.join(
    app.root_path,
    "static",
    "uploads",
)


# Service invoices
app.config[
    "INVOICE_UPLOAD_FOLDER"
] = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "invoices",
)


# Documents
app.config[
    "DOCUMENT_UPLOAD_FOLDER"
] = os.path.join(
    app.root_path,
    "static",
    "uploads",
    "documents",
)


# ============================================================
# SESSION CONFIGURATION
# ============================================================

app.config[
    "SESSION_COOKIE_HTTPONLY"
] = True


app.config[
    "SESSION_COOKIE_SAMESITE"
] = "Lax"


# ============================================================
# PRODUCTION & REVERSE PROXY CONFIGURATION (RENDER COMPATIBLE)
# ============================================================

is_production = (
    os.environ.get("FLASK_ENV") == "production"
    or os.environ.get("RENDER") is not None
    or os.environ.get("DATABASE_URL") is not None
)

if is_production:
    app.config["SESSION_COOKIE_SECURE"] = True
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=1,
        x_proto=1,
        x_host=1,
        x_prefix=1,
    )

# Disable strict SSL check for CSRF to prevent false mismatches behind Render's proxy
app.config["WTF_CSRF_SSL_STRICT"] = False


# ============================================================
# INITIALIZE EXTENSIONS
# ============================================================

db.init_app(
    app
)

login_manager.init_app(
    app
)

migrate.init_app(
    app,
    db,
)

limiter.init_app(app)

csrf.init_app(
    app
)


# ============================================================
# MAIL CONFIGURATION (Flask-Mail via Gmail SMTP)
# ============================================================

app.config["MAIL_SERVER"]   = "smtp.gmail.com"
app.config["MAIL_PORT"]     = 587
app.config["MAIL_USE_TLS"]  = True
app.config["MAIL_USE_SSL"]  = False
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = (
    "AutoCare AI",
    os.environ.get("MAIL_FROM", os.environ.get("MAIL_USERNAME", "")),
)
app.config["MAIL_TIMEOUT"]  = 30

mail.init_app(app)


# ============================================================
# LOGIN MANAGER CONFIGURATION
# ============================================================

login_manager.login_view = (
    "auth.login"
)

login_manager.login_message = (
    "Please log in first."
)

login_manager.login_message_category = (
    "warning"
)


# ============================================================
# USER LOADER
# ============================================================

@login_manager.user_loader
def load_user(user_id):

    try:

        return db.session.get(
            User,
            int(user_id),
        )

    except (
        TypeError,
        ValueError,
    ):

        return None


# ============================================================
# REGISTER BLUEPRINTS
# ============================================================

app.register_blueprint(
    auth
)

app.register_blueprint(
    dashboard_bp
)

app.register_blueprint(
    vehicle
)

app.register_blueprint(
    service
)

app.register_blueprint(
    fuel
)

app.register_blueprint(
    garage_bp
)

app.register_blueprint(
    insurance
)

app.register_blueprint(
    documents
)

app.register_blueprint(
    api
)


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(400)
def bad_request_error(error):
    app.logger.warning(f"400 Bad Request: {error}")
    try:
        return render_template("errors/400.html", error=error), 400
    except Exception:
        return "<div style='color:white;background:#1e1e1e;padding:40px;text-align:center;'><h2>400 Bad Request</h2><p>Session or security token expired. <a href='/login' style='color:#60a5fa;'>Click here to log in again</a>.</p></div>", 400


@app.errorhandler(403)
def forbidden_error(error):
    try:
        return render_template("errors/403.html"), 403
    except Exception:
        return "<div style='color:white;background:#1e1e1e;padding:40px;text-align:center;'><h2>403 Forbidden</h2></div>", 403


@app.errorhandler(404)
def not_found_error(error):
    try:
        return render_template("errors/404.html"), 404
    except Exception:
        return "<div style='color:white;background:#1e1e1e;padding:40px;text-align:center;'><h2>404 Not Found</h2></div>", 404


@app.errorhandler(413)
def request_entity_too_large_error(error):
    try:
        return render_template("errors/413.html"), 413
    except Exception:
        return "<div style='color:white;background:#1e1e1e;padding:40px;text-align:center;'><h2>413 File Too Large</h2></div>", 413


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    app.logger.error(f"500 Internal Server Error: {error}\n{traceback.format_exc()}")
    try:
        return render_template("errors/500.html"), 500
    except Exception:
        return "<div style='color:white;background:#1e1e1e;padding:40px;text-align:center;'><h2>500 Internal Server Error</h2><p>Something went wrong on our end.</p></div>", 500





# ============================================================
# HOME PAGE
# ============================================================

@app.route(
    "/"
)
def index():

    return render_template(
        "index.html"
    )


# ============================================================
# HOME ALIAS
# ============================================================

@app.route(
    "/home"
)
def home():

    return redirect(
        url_for(
            "index"
        )
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route(
    "/health"
)
@csrf.exempt
@limiter.exempt
def health_check():

    return jsonify(
        {
            "status": "healthy",
            "timestamp":
                datetime.now(
                    timezone.utc
                ).isoformat(),
        }
    )


# ============================================================
# OFFLINE PAGE
# ============================================================

@app.route(
    "/offline"
)
def offline():

    return render_template(
        "offline.html"
    )


# ============================================================
# OLD LOGOUT ALIAS
# ============================================================
#
# Real logout route:
#   auth.logout -> /logout
#
# Compatibility route for older templates:
#   url_for("logout")
#
# ============================================================

@app.route(
    "/logout-redirect"
)
def logout():

    return redirect(
        url_for(
            "auth.logout"
        )
    )


# ============================================================
# SERVICE WORKER
# ============================================================

@app.route(
    "/service-worker.js"
)
def service_worker():

    return send_from_directory(
        os.path.join(
            app.root_path,
            "static",
        ),
        "service-worker.js",
        mimetype=(
            "application/javascript"
        ),
    )


# ============================================================
# CREATE REQUIRED DIRECTORIES
# ============================================================

os.makedirs(
    app.config[
        "UPLOAD_FOLDER"
    ],
    exist_ok=True,
)


os.makedirs(
    app.config[
        "INVOICE_UPLOAD_FOLDER"
    ],
    exist_ok=True,
)


os.makedirs(
    app.config[
        "DOCUMENT_UPLOAD_FOLDER"
    ],
    exist_ok=True,
)


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

with app.app_context():

    try:

        db.create_all()

    except Exception as error:

        print(
            "DATABASE INITIALIZATION ERROR:"
        )

        print(
            error
        )


# ============================================================
# PRINT IMPORTANT ROUTES
# ============================================================

def print_routes():

    print()

    print(
        "=" * 78
    )

    print(
        "AUTOCARE AI REGISTERED ROUTES"
    )

    print(
        "=" * 78
    )

    for rule in sorted(
        app.url_map.iter_rules(),
        key=lambda route: route.rule,
    ):

        methods = ",".join(
            sorted(
                method
                for method
                in rule.methods
                if method
                not in {
                    "HEAD",
                    "OPTIONS",
                }
            )
        )

        print(
            f"{rule.endpoint:35}"
            f"{methods:15}"
            f"{rule.rule}"
        )

    print(
        "=" * 78
    )

    print()


# ============================================================
# RUN APPLICATION
# ============================================================

if __name__ == "__main__":

    port = int(
        os.environ.get(
            "PORT",
            "5055",
        )
    )

    print()

    print(
        "AUTOCARE AI STARTING..."
    )

    print(
        "RUNNING FILE:",
        os.path.abspath(
            __file__
        ),
    )

    print(
        "PROJECT ROOT:",
        app.root_path,
    )

    print(
        "DATABASE:",
        app.config[
            "SQLALCHEMY_DATABASE_URI"
        ].split("@")[-1]
        if "@"
        in app.config[
            "SQLALCHEMY_DATABASE_URI"
        ]
        else "Configured",
    )

    print(
        "SERVER:",
        f"http://127.0.0.1:{port}",
    )

    print_routes()

    app.run(
        host="127.0.0.1",
        port=port,
        debug=True,
        use_reloader=True,
    )
