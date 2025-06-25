from app import app, db
from models import Admin, UserRole

# Admin account information
admin_data = {
    'employee_id': 'ADMIN001',
    'name': 'System Administrator',
    'phone_number': '+919999999999',
    'email': 'admin@driverplatform.com',
    'password': 'Admin@123',
    'address': 'Admin Home Address, City, State, PIN',
    'office_address': 'Head Office, Business District, City, State, PIN',
    'role': UserRole.ADMIN
}

with app.app_context():
    # Check if admin already exists
    existing_admin = Admin.query.filter_by(employee_id=admin_data['employee_id']).first()
    
    if existing_admin:
        print(f"Admin with ID {admin_data['employee_id']} already exists.")
    else:
        # Create new admin
        new_admin = Admin(
            employee_id=admin_data['employee_id'],
            name=admin_data['name'],
            phone_number=admin_data['phone_number'],
            email=admin_data['email'],
            address=admin_data['address'],
            office_address=admin_data['office_address'],
            role=admin_data['role']
        )
        
        # Set password
        new_admin.set_password(admin_data['password'])
        
        # Add to database
        db.session.add(new_admin)
        db.session.commit()
        
        print(f"Admin created successfully with ID: {new_admin.employee_id}")
        print(f"Username: {new_admin.employee_id}")
        print(f"Password: {admin_data['password']}")