"""
Script to update driver password
"""
from app import app, db
from models import Driver
from werkzeug.security import generate_password_hash

def reset_driver_password(driver_id, new_password):
    """Reset a driver's password"""
    with app.app_context():
        driver = Driver.query.filter_by(driver_id=driver_id).first()
        if not driver:
            print(f"No driver found with ID: {driver_id}")
            return False
        
        print(f"Resetting password for driver: {driver.name} (ID: {driver_id})")
        driver.password_hash = generate_password_hash(new_password)
        db.session.commit()
        print("Password updated successfully")
        return True

if __name__ == "__main__":
    # Update driver password
    driver_id = "DR250403394"
    new_password = "Basam@2212"
    success = reset_driver_password(driver_id, new_password)
    if success:
        print(f"Password for driver {driver_id} has been reset to '{new_password}'")
    else:
        print(f"Failed to reset password for driver {driver_id}")