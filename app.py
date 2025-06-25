import os
import logging
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from flask_login import LoginManager

# Set up logging
logging.basicConfig(level=logging.DEBUG)

class Base(DeclarativeBase):
    pass

# Initialize SQLAlchemy with the Base
db = SQLAlchemy(model_class=Base)

# Create the Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET", "dev_secret_key")

# Configure the database
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///driver_management.db")
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "pool_recycle": 300,
    "pool_pre_ping": True,
}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialize the app with the SQLAlchemy extension
db.init_app(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'  # Default route for unauthenticated users
login_manager.login_message = "Please log in to access this page."

# Create all tables in the database
with app.app_context():
    # Import models here to ensure they're registered with SQLAlchemy
    import models  # noqa
    db.create_all()

# Set up the login manager loader
@login_manager.user_loader
def load_user(user_id):
    from models import Admin, Customer, Driver
    
    # Parse the user_id to determine which table to check
    # Format: "admin_{id}" or "customer_{id}" or "driver_{id}"
    if '_' in user_id:
        user_type, actual_id = user_id.split('_', 1)
        try:
            actual_id = int(actual_id)
            
            if user_type == 'admin':
                return Admin.query.get(actual_id)
            elif user_type == 'customer':
                return Customer.query.get(actual_id)
            elif user_type == 'driver':
                return Driver.query.get(actual_id)
        except (ValueError, AttributeError):
            pass
    
    # Legacy fallback (try to find in any table)
    try:
        # Convert to integer for database lookup
        id_int = int(user_id)
        
        # First try to find an admin
        admin = Admin.query.get(id_int)
        if admin:
            return admin
        
        # Then try to find a customer
        customer = Customer.query.get(id_int)
        if customer:
            return customer
        
        # Finally try to find a driver
        driver = Driver.query.get(id_int)
        if driver:
            return driver
    except ValueError:
        pass
    
    return None
