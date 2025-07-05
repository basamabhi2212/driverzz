import os
import datetime
from flask import render_template, request, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from app import app, db
from models import (
    Admin, Customer, Driver, Trip, TripStatus, TripType, RouteType, 
    UserRole, Notification, DriverPayment, PaymentMode, TripLog, 
    TripPrice, DriverDocument, FireDetail
)
from utils import generate_otp, send_otp, generate_qr_code, overlay_text_on_image, create_notification
from werkzeug.utils import secure_filename
import json

# Home route
@app.route('/')
def index():
    return render_template('index.html')

# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        password = request.form.get('password')
        
        admin = Admin.query.filter_by(employee_id=employee_id).first()
        
        if admin and admin.check_password(password):
            login_user(admin)
            flash('Login successful!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid employee ID or password.', 'danger')
    
    return render_template('admin/login.html')

@app.route('/admin/register', methods=['GET', 'POST'])
def admin_register():
    if request.method == 'POST':
        try:
            # Get form data
            employee_id = request.form.get('employee_id')
            name = request.form.get('name')
            phone_number = request.form.get('phone_number')
            email = request.form.get('email')
            address = request.form.get('address')
            office_address = request.form.get('office_address')
            role = request.form.get('role')
            password = request.form.get('password')
            
            # Check if admin already exists
            existing_admin = Admin.query.filter(
                (Admin.employee_id == employee_id) | (Admin.email == email)
            ).first()
            
            if existing_admin:
                flash('Admin with this employee ID or email already exists.', 'danger')
                return render_template('admin/register.html', roles=[role.value for role in UserRole])
            
            # Create new admin
            new_admin = Admin(
                employee_id=employee_id,
                name=name,
                phone_number=phone_number,
                email=email,
                address=address,
                office_address=office_address,
                role=UserRole(role)
            )
            new_admin.set_password(password)
            
            db.session.add(new_admin)
            db.session.commit()
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('admin_login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('admin/register.html', roles=[role.value for role in UserRole])

@app.route('/admin/logout')
@login_required
def admin_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    # Get dashboard statistics
    pending_trips = Trip.query.filter_by(status=TripStatus.PENDING).count()
    active_trips = Trip.query.filter(Trip.status.in_([TripStatus.ASSIGNED, TripStatus.STARTED])).count()
    drivers_count = Driver.query.count()
    customers_count = Customer.query.count()
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_type='Admin'
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('admin/dashboard.html',
                         pending_trips=pending_trips,
                         active_trips=active_trips,
                         drivers_count=drivers_count,
                         customers_count=customers_count,
                         notifications=notifications)

# ============================================================================
# CUSTOMER ROUTES
# ============================================================================

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if request.method == 'POST':
        mobile_number = request.form.get('mobile_number')
        
        # Find or create customer
        customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        
        if not customer:
            flash('Mobile number not registered. Please register first.', 'danger')
            return redirect(url_for('customer_register'))
        
        # Generate and send OTP
        otp = generate_otp()
        customer.set_otp(otp)
        db.session.commit()
        
        # Send OTP (in development mode, this will just log the OTP)
        success, message_sid = send_otp(mobile_number, otp)
        
        if success:
            session['customer_mobile'] = mobile_number
            flash('OTP sent to your mobile number.', 'info')
            return redirect(url_for('customer_verify_otp'))
        else:
            flash('Failed to send OTP. Please try again.', 'danger')
    
    return render_template('customer/login.html')

@app.route('/customer/verify-otp', methods=['GET', 'POST'])
def customer_verify_otp():
    if 'customer_mobile' not in session:
        flash('Please request OTP first.', 'danger')
        return redirect(url_for('customer_login'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        mobile_number = session.get('customer_mobile')
        
        customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        
        if customer and customer.verify_otp(otp):
            login_user(customer)
            session.pop('customer_mobile', None)
            flash('Login successful!', 'success')
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid or expired OTP.', 'danger')
    
    return render_template('customer/otp_verification.html')

@app.route('/customer/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            mobile_number = request.form.get('mobile_number')
            home_address = request.form.get('home_address')
            office_address = request.form.get('office_address')
            vehicle_model = request.form.get('vehicle_model')
            
            # Check if customer already exists
            existing_customer = Customer.query.filter_by(mobile_number=mobile_number).first()
            
            if existing_customer:
                flash('Customer with this mobile number already exists.', 'danger')
                return render_template('customer/register.html')
            
            # Create new customer
            new_customer = Customer(
                name=name,
                mobile_number=mobile_number,
                home_address=home_address,
                office_address=office_address,
                vehicle_model=vehicle_model
            )
            
            db.session.add(new_customer)
            db.session.commit()
            
            flash('Registration successful! You can now login.', 'success')
            return redirect(url_for('customer_login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('customer/register.html')

@app.route('/customer/logout')
@login_required
def customer_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/customer/dashboard')
@login_required
def customer_dashboard():
    if not current_user.is_customer():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    # Get customer statistics
    trips = Trip.query.filter_by(customer_id=current_user.id).all()
    upcoming_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status.in_([TripStatus.PENDING, TripStatus.ASSIGNED]),
        Trip.trip_start_date > datetime.datetime.utcnow()
    ).count()
    
    active_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.STARTED
    ).count()
    
    completed_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).count()
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_type='Customer',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('customer/dashboard.html',
                         trips=trips,
                         upcoming_trips=upcoming_trips,
                         active_trips=active_trips,
                         completed_trips=completed_trips,
                         notifications=notifications)

# ============================================================================
# DRIVER ROUTES
# ============================================================================

@app.route('/driver/login', methods=['GET', 'POST'])
def driver_login():
    if request.method == 'POST':
        driver_id = request.form.get('driver_id')
        password = request.form.get('password')
        
        driver = Driver.query.filter_by(driver_id=driver_id).first()
        
        if driver and driver.check_password(password):
            if not driver.is_approved:
                flash('Your account is pending approval. Please wait for admin approval.', 'warning')
                return render_template('driver/login.html')
            
            login_user(driver)
            flash('Login successful!', 'success')
            return redirect(url_for('driver_dashboard'))
        else:
            flash('Invalid driver ID or password.', 'danger')
    
    return render_template('driver/login.html')

@app.route('/driver/register', methods=['GET', 'POST'])
def driver_register():
    if request.method == 'POST':
        try:
            # Get form data
            name = request.form.get('name')
            phone_number = request.form.get('phone_number')
            email = request.form.get('email')
            password = request.form.get('password')
            license_number = request.form.get('license_number')
            license_issue_date = datetime.datetime.strptime(request.form.get('license_issue_date'), '%Y-%m-%d')
            license_expiry_date = datetime.datetime.strptime(request.form.get('license_expiry_date'), '%Y-%m-%d')
            current_address = request.form.get('current_address')
            permanent_address = request.form.get('permanent_address')
            
            # Check if driver already exists
            existing_driver = Driver.query.filter(
                (Driver.phone_number == phone_number) | 
                (Driver.license_number == license_number) |
                (Driver.email == email if email else False)
            ).first()
            
            if existing_driver:
                flash('Driver with this phone number, license number, or email already exists.', 'danger')
                return render_template('driver/register.html')
            
            # Generate unique driver ID
            import random
            import string
            driver_id = 'DR' + ''.join(random.choices(string.digits, k=9))
            
            # Ensure driver ID is unique
            while Driver.query.filter_by(driver_id=driver_id).first():
                driver_id = 'DR' + ''.join(random.choices(string.digits, k=9))
            
            # Create new driver
            new_driver = Driver(
                driver_id=driver_id,
                name=name,
                phone_number=phone_number,
                email=email,
                license_number=license_number,
                license_issue_date=license_issue_date,
                license_expiry_date=license_expiry_date,
                current_address=current_address,
                permanent_address=permanent_address or current_address,
                is_approved=False,  # Requires admin approval
                is_active=True
            )
            new_driver.set_password(password)
            
            # Generate QR code for driver
            qr_code = generate_qr_code(driver_id, name)
            new_driver.qr_code = qr_code
            
            db.session.add(new_driver)
            db.session.commit()
            
            # Create notification for admin
            create_notification(
                'Admin', 
                1, 
                f'New driver registration: {name} (ID: {driver_id}) requires approval.'
            )
            
            flash(f'Registration successful! Your Driver ID is {driver_id}. Please wait for admin approval.', 'success')
            return redirect(url_for('driver_login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'danger')
    
    return render_template('driver/register.html')

@app.route('/driver/logout')
@login_required
def driver_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/driver/dashboard')
@login_required
def driver_dashboard():
    if not current_user.is_driver():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    # Get assigned trips
    assigned_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status.in_([TripStatus.ASSIGNED, TripStatus.STARTED])
    ).order_by(Trip.trip_start_date.asc()).all()
    
    # Get recent completed trips
    completed_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).order_by(Trip.ended_at.desc()).limit(5).all()
    
    # Get recent notifications
    notifications = Notification.query.filter_by(
        user_type='Driver',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    return render_template('driver/dashboard.html',
                         assigned_trips=assigned_trips,
                         completed_trips=completed_trips,
                         notifications=notifications,
                         now=datetime.datetime.utcnow())

# ============================================================================
# ADDITIONAL ROUTES (Placeholders for other functionality)
# ============================================================================

@app.route('/book-trip')
@login_required
def book_trip():
    if not current_user.is_customer():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    trip_types = [trip_type.value for trip_type in TripType]
    route_types = [route_type.value for route_type in RouteType]
    
    return render_template('customer/book_trip.html', 
                         trip_types=trip_types, 
                         route_types=route_types)

@app.route('/trip-history')
@login_required
def trip_history():
    if not current_user.is_customer():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    trips = Trip.query.filter_by(customer_id=current_user.id).order_by(Trip.created_at.desc()).all()
    
    return render_template('customer/trip_history.html', 
                         trips=trips, 
                         TripStatus=TripStatus)

@app.route('/payment-history')
@login_required
def payment_history():
    if not current_user.is_customer():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).order_by(Trip.ended_at.desc()).all()
    
    return render_template('customer/payment_history.html', trips=trips)

@app.route('/driver/payment-info')
@login_required
def driver_payment_info():
    if not current_user.is_driver():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    # Get driver's payment history
    payments = DriverPayment.query.filter_by(driver_id=current_user.id).order_by(DriverPayment.payment_date.desc()).all()
    
    # Get completed trips
    completed_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).order_by(Trip.ended_at.desc()).all()
    
    return render_template('driver/payment_info.html', 
                         payments=payments, 
                         completed_trips=completed_trips)

@app.route('/driver/qr-code')
@login_required
def driver_qr_code():
    if not current_user.is_driver():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('driver/qr_code.html')

@app.route('/driver/notifications')
@login_required
def driver_notifications():
    if not current_user.is_driver():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(
        user_type='Driver',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('driver/notifications.html', 
                         notifications=notifications,
                         now=datetime.datetime.utcnow())

@app.route('/customer/notifications')
@login_required
def customer_notifications():
    if not current_user.is_customer():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(
        user_type='Customer',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('customer/notifications.html', 
                         notifications=notifications,
                         now=datetime.datetime.utcnow())

@app.route('/admin/notifications')
@login_required
def admin_notifications():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    
    notifications = Notification.query.filter_by(
        user_type='Admin'
    ).order_by(Notification.created_at.desc()).all()
    
    return render_template('admin/notifications.html', 
                         notifications=notifications,
                         now=datetime.datetime.utcnow())

# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/notifications/count')
@login_required
def api_notifications_count():
    if current_user.is_admin():
        count = Notification.query.filter_by(user_type='Admin', is_read=False).count()
    elif current_user.is_customer():
        count = Notification.query.filter_by(user_type='Customer', user_id=current_user.id, is_read=False).count()
    elif current_user.is_driver():
        count = Notification.query.filter_by(user_type='Driver', user_id=current_user.id, is_read=False).count()
    else:
        count = 0
    
    return jsonify({'count': count})

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('errors/500.html'), 500

# ============================================================================
# PLACEHOLDER ROUTES (To prevent 404 errors)
# ============================================================================

# Admin routes placeholders
@app.route('/admin/trip-management')
@login_required
def trip_management():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/trip_management.html')

@app.route('/admin/driver-management')
@login_required
def driver_management():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/driver_management.html')

@app.route('/admin/customer-management')
@login_required
def customer_management():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/customer_management.html')

@app.route('/admin/finance')
@login_required
def admin_finance():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/finance.html')

@app.route('/admin/reports')
@login_required
def admin_reports():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/reports.html')

@app.route('/admin/user-management')
@login_required
def user_management():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/user_management.html')

@app.route('/admin/trip-estimation')
@login_required
def trip_estimation():
    if not current_user.is_admin():
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    return render_template('admin/fire_details.html')  # Using fire_details.html as trip estimation template