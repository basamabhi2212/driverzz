from app import app, db
from models import Admin

with app.app_context():
    admin = Admin.query.first()
    print(f'Admin exists: {admin is not None}')
    if admin:
        print(f'Admin ID: {admin.employee_id}')
    print(f'Admin count: {Admin.query.count()}')