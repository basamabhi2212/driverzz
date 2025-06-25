import os
import json
import base64
import random
import datetime
from datetime import timedelta
from functools import wraps
from flask import render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_login import login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from app import app, db
from models import Admin, Customer, Driver, Trip, Notification, DriverPayment, TripLog, UserRole, TripStatus, TripType, PaymentMode, RouteType, TripPrice, DriverDocument, FireDetail
from utils import generate_otp, send_otp, generate_qr_code, overlay_text_on_image, calculate_bill, create_notification, check_license_expiry, check_upcoming_trips

# Custom decorators for role-based access
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"Admin required check - is_authenticated: {current_user.is_authenticated}, type: {type(current_user)}")
        
        if not current_user.is_authenticated:
            flash('You need to be logged in to view this page.', 'warning')
            return redirect(url_for('admin_login'))
            
        # Use the is_admin() method to check if the user is an admin
        if not current_user.is_admin():
            flash('You need to be logged in as an admin to view this page.', 'danger')
            # Redirect based on user type
            if current_user.is_driver():
                return redirect(url_for('driver_dashboard'))
            elif current_user.is_customer():
                return redirect(url_for('customer_dashboard'))
            else:
                return redirect(url_for('admin_login'))
                
        print(f"Admin authenticated - ID: {current_user.employee_id}, Name: {current_user.name}")
        return f(*args, **kwargs)
    return decorated_function

def driver_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"Driver required check - is_authenticated: {current_user.is_authenticated}, type: {type(current_user)}")
        
        if not current_user.is_authenticated:
            flash('You need to be logged in to view this page.', 'warning')
            return redirect(url_for('driver_login'))
        
        # Use the is_driver() method to check if the user is a driver
        if not current_user.is_driver():
            flash('You need to be logged in as a driver to view this page.', 'danger')
            # Redirect based on user type
            if current_user.is_admin():
                return redirect(url_for('admin_dashboard'))
            elif current_user.is_customer():
                return redirect(url_for('customer_dashboard'))
            else:
                return redirect(url_for('driver_login'))
                
        print(f"Driver authenticated - ID: {current_user.driver_id}, Name: {current_user.name}")
        return f(*args, **kwargs)
    return decorated_function

def customer_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        print(f"Customer required check - is_authenticated: {current_user.is_authenticated}, type: {type(current_user)}")
        
        if not current_user.is_authenticated:
            flash('You need to be logged in to view this page.', 'warning')
            return redirect(url_for('customer_login'))
            
        # Use the is_customer() method to check if the user is a customer
        if not current_user.is_customer():
            flash('You need to be logged in as a customer to view this page.', 'danger')
            # Redirect based on user type
            if current_user.is_admin():
                return redirect(url_for('admin_dashboard'))
            elif current_user.is_driver():
                return redirect(url_for('driver_dashboard'))
            else:
                return redirect(url_for('customer_login'))
                
        print(f"Customer authenticated - ID: {current_user.id}, Name: {current_user.name}")
        return f(*args, **kwargs)
    return decorated_function

# Index route
@app.route('/')
def index():
    return render_template('index.html')

# ========== ADMIN ROUTES ==========

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated and current_user.is_admin():
        return redirect(url_for('admin_dashboard'))
        
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
        employee_id = request.form.get('employee_id')
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        address = request.form.get('address')
        office_address = request.form.get('office_address')
        role = request.form.get('role')
        
        # Check if employee_id already exists
        existing_admin = Admin.query.filter_by(employee_id=employee_id).first()
        if existing_admin:
            flash('Employee ID already exists.', 'danger')
            return render_template('admin/register.html')
        
        # Check if email already exists
        existing_email = Admin.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered.', 'danger')
            return render_template('admin/register.html')
        
        # Create new admin
        admin = Admin(
            employee_id=employee_id,
            name=name,
            phone_number=phone_number,
            email=email,
            address=address,
            office_address=office_address,
            role=UserRole(role)
        )
        admin.set_password(password)
        
        try:
            db.session.add(admin)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('admin_login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    roles = [role.value for role in UserRole]
    return render_template('admin/register.html', roles=roles)

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    try:
        # Count stats for dashboard
        pending_trips = Trip.query.filter_by(status=TripStatus.PENDING).count()
        active_trips = Trip.query.filter_by(status=TripStatus.STARTED).count()
        drivers_count = Driver.query.count()
        customers_count = Customer.query.count()
        
        # Get notifications
        notifications = Notification.query.filter_by(
            user_type='Admin', 
            user_id=current_user.id,
            is_read=False
        ).order_by(Notification.created_at.desc()).limit(10).all()
        
        return render_template(
            'admin/dashboard.html', 
            pending_trips=pending_trips,
            active_trips=active_trips,
            drivers_count=drivers_count,
            customers_count=customers_count,
            notifications=notifications
        )
    except Exception as e:
        app.logger.error(f"Dashboard error: {str(e)}")
        return render_template('errors/500.html'), 500

@app.route('/admin/logout')
@admin_required
def admin_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('admin_login'))

@app.route('/admin/trip-management')
@admin_required
def trip_management():
    # Get all trips
    trips = Trip.query.order_by(Trip.trip_start_date.desc()).all()
    
    # Get available drivers for assignment
    available_drivers = Driver.query.filter_by(is_approved=True, is_active=True).all()
    
    return render_template(
        'admin/trip_management.html', 
        trips=trips,
        available_drivers=available_drivers,
        TripStatus=TripStatus
    )
    
@app.route('/admin/book-trip', methods=['GET', 'POST'])
@admin_required
def admin_book_trip():
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        trip_start_date = datetime.datetime.strptime(request.form.get('trip_start_date'), '%Y-%m-%dT%H:%M')
        trip_end_date = datetime.datetime.strptime(request.form.get('trip_end_date'), '%Y-%m-%dT%H:%M')
        trip_type = request.form.get('trip_type')
        route_type = request.form.get('route_type')
        pickup_location = request.form.get('pickup_location')
        drop_location = request.form.get('drop_location')
        driver_id = request.form.get('driver_id')
        
        # Validate the customer exists
        customer = Customer.query.get(customer_id)
        if not customer:
            flash('Invalid customer selected', 'danger')
            return redirect(url_for('admin_book_trip'))
        
        # Validate dates
        if trip_start_date < datetime.datetime.now():
            flash('Trip start date cannot be in the past.', 'danger')
            return redirect(url_for('admin_book_trip'))
        
        if trip_end_date <= trip_start_date:
            flash('Trip end date must be after start date.', 'danger')
            return redirect(url_for('admin_book_trip'))
        
        # Find applicable trip price
        trip_price = TripPrice.query.filter_by(
            route_type=RouteType(route_type),
            trip_type=TripType(trip_type)
        ).first()
        
        # Create new trip
        trip = Trip(
            customer_id=customer_id,
            trip_start_date=trip_start_date,
            trip_end_date=trip_end_date,
            trip_type=TripType(trip_type),
            route_type=RouteType(route_type),
            trip_price_id=trip_price.id if trip_price else None,
            pickup_location=pickup_location,
            drop_location=drop_location,
            status=TripStatus.PENDING,
            last_modified_by_id=current_user.id
        )
        
        try:
            db.session.add(trip)
            db.session.commit()
            
            # Create trip log
            log = TripLog(
                trip_id=trip.id,
                admin_id=current_user.id,
                action="Created trip",
                details=f"Admin created trip for customer {customer.name}"
            )
            db.session.add(log)
            
            # If driver was selected, assign them
            if driver_id:
                driver = Driver.query.get(driver_id)
                if driver:
                    trip.driver_id = driver.id
                    trip.assigned_at = datetime.datetime.utcnow()
                    trip.status = TripStatus.ASSIGNED
                    
                    # Create trip log
                    driver_log = TripLog(
                        trip_id=trip.id,
                        admin_id=current_user.id,
                        action=f"Assigned driver {driver.name}",
                        details=f"Driver ID: {driver.id}"
                    )
                    
                    # Create notification for driver
                    create_notification(
                        user_type="Driver",
                        user_id=driver.id,
                        message=f"You have been assigned to trip #{trip.id} for {customer.name} starting on {trip.trip_start_date.strftime('%Y-%m-%d %H:%M')}"
                    )
                    
                    db.session.add(driver_log)
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=customer.id,
                message=f"A new trip has been booked for you starting on {trip.trip_start_date.strftime('%Y-%m-%d %H:%M')}"
            )
            
            db.session.commit()
            
            flash('Trip booked successfully!', 'success')
            return redirect(url_for('admin_trip_detail', trip_id=trip.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking trip: {str(e)}', 'danger')
    
    # Get all customers
    customers = Customer.query.all()
    
    # Get available drivers
    drivers = Driver.query.filter_by(is_approved=True, is_active=True).all()
    
    # Get trip types and route types
    trip_types = [trip_type.value for trip_type in TripType]
    route_types = [route_type.value for route_type in RouteType]
    
    return render_template(
        'admin/book_trip.html',
        customers=customers,
        drivers=drivers,
        trip_types=trip_types,
        route_types=route_types
    )

@app.route('/admin/trip/<int:trip_id>', methods=['GET', 'POST'])
@admin_required
def admin_trip_detail(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Check admin role for certain operations
    is_authorized_role = current_user.role in [UserRole.OPERATIONS, UserRole.MANAGER, UserRole.ADMIN]
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'assign_driver':
            driver_id = request.form.get('driver_id')
            if driver_id:
                driver = Driver.query.get(driver_id)
                if driver:
                    trip.driver_id = driver.id
                    trip.assigned_at = datetime.datetime.utcnow()
                    trip.status = TripStatus.ASSIGNED
                    trip.last_modified_by_id = current_user.id
                    
                    # Create trip log
                    log = TripLog(
                        trip_id=trip.id,
                        admin_id=current_user.id,
                        action=f"Assigned driver {driver.name}",
                        details=f"Driver ID: {driver.id}"
                    )
                    
                    # Create notification for driver
                    create_notification(
                        user_type="Driver",
                        user_id=driver.id,
                        message=f"You have been assigned to trip #{trip.id} starting on {trip.trip_start_date.strftime('%Y-%m-%d %H:%M')}"
                    )
                    
                    # Create notification for customer
                    create_notification(
                        user_type="Customer",
                        user_id=trip.customer_id,
                        message=f"Driver {driver.name} has been assigned to your trip on {trip.trip_start_date.strftime('%Y-%m-%d %H:%M')}"
                    )
                    
                    db.session.add(log)
                    db.session.commit()
                    
                    flash(f'Driver {driver.name} assigned to trip successfully.', 'success')
                else:
                    flash('Invalid driver selected.', 'danger')
            else:
                flash('Please select a driver.', 'danger')
        
        elif action == 'update_trip':
            # Update trip details
            trip.pickup_location = request.form.get('pickup_location')
            trip.drop_location = request.form.get('drop_location')
            trip.trip_start_date = datetime.datetime.strptime(request.form.get('trip_start_date'), '%Y-%m-%dT%H:%M')
            trip.trip_end_date = datetime.datetime.strptime(request.form.get('trip_end_date'), '%Y-%m-%dT%H:%M')
            trip.trip_type = TripType(request.form.get('trip_type'))
            trip.route_type = RouteType(request.form.get('route_type'))
            
            # Find applicable trip price
            trip_price = TripPrice.query.filter_by(
                route_type=trip.route_type,
                trip_type=trip.trip_type
            ).first()
            trip.trip_price_id = trip_price.id if trip_price else None
            
            trip.last_modified_by_id = current_user.id
            
            # Create trip log
            log = TripLog(
                trip_id=trip.id,
                admin_id=current_user.id,
                action="Updated trip details",
                details=f"Updated trip #{trip.id} details"
            )
            
            db.session.add(log)
            db.session.commit()
            
            flash('Trip details updated successfully.', 'success')
        
        elif action == 'start_trip':
            # Updated to allow Admin, Operations, and Manager roles
            if not is_authorized_role:
                flash('You do not have permission to start trips. Only Admin, Operations, or Manager roles can perform this action.', 'danger')
                return redirect(url_for('admin_trip_detail', trip_id=trip.id))
                
            trip.status = TripStatus.STARTED
            trip.started_at = datetime.datetime.utcnow()
            trip.last_modified_by_id = current_user.id
            
            # Create trip log
            log = TripLog(
                trip_id=trip.id,
                admin_id=current_user.id,
                action="Started trip",
                details=f"Admin {current_user.name} ({current_user.role.value}) started trip #{trip.id}"
            )
            
            # Create notification for driver if assigned
            if trip.driver_id:
                create_notification(
                    user_type="Driver",
                    user_id=trip.driver_id,
                    message=f"Trip #{trip.id} has been started by admin {current_user.name}."
                )
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=trip.customer_id,
                message=f"Your trip #{trip.id} has been started by the admin."
            )
            
            db.session.add(log)
            db.session.commit()
            
            flash('Trip started successfully.', 'success')
        
        elif action == 'end_trip':
            # Updated to allow Admin, Operations, and Manager roles
            if not is_authorized_role:
                flash('You do not have permission to end trips. Only Admin, Operations, or Manager roles can perform this action.', 'danger')
                return redirect(url_for('admin_trip_detail', trip_id=trip.id))
                
            trip.status = TripStatus.COMPLETED
            trip.ended_at = datetime.datetime.utcnow()
            trip.last_modified_by_id = current_user.id
            
            # Calculate bill
            trip.calculate_bill()
            
            # Create trip log
            log = TripLog(
                trip_id=trip.id,
                admin_id=current_user.id,
                action="Ended trip",
                details=f"Admin {current_user.name} ({current_user.role.value}) ended trip #{trip.id}"
            )
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=trip.customer_id,
                message=f"Your trip #{trip.id} has been marked as completed by admin. Total fare: ₹{trip.total_amount:.2f}"
            )
            
            # Create notification for driver if assigned
            if trip.driver_id:
                create_notification(
                    user_type="Driver",
                    user_id=trip.driver_id,
                    message=f"Trip #{trip.id} has been marked as completed by admin. Payment processed."
                )
            
            db.session.add(log)
            db.session.commit()
            
            flash('Trip ended successfully.', 'success')
        
        elif action == 'cancel_trip':
            # Updated to allow Admin, Operations, and Manager roles
            if not is_authorized_role:
                flash('You do not have permission to cancel trips. Only Admin, Operations, or Manager roles can perform this action.', 'danger')
                return redirect(url_for('admin_trip_detail', trip_id=trip.id))
                
            cancel_reason = request.form.get('cancel_reason')
            if not cancel_reason or cancel_reason.strip() == '':
                flash('Please provide a reason for cancellation.', 'danger')
                return redirect(url_for('admin_trip_detail', trip_id=trip.id))
                
            trip.status = TripStatus.CANCELLED
            trip.cancelled_at = datetime.datetime.utcnow()
            trip.cancel_reason = cancel_reason
            trip.last_modified_by_id = current_user.id
            
            # Create trip log
            log = TripLog(
                trip_id=trip.id,
                admin_id=current_user.id,
                action="Cancelled trip",
                details=f"Admin {current_user.name} ({current_user.role.value}) cancelled trip #{trip.id}. Reason: {cancel_reason}"
            )
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=trip.customer_id,
                message=f"Your trip #{trip.id} has been cancelled by admin. Reason: {cancel_reason}"
            )
            
            # Create notification for driver if assigned
            if trip.driver_id:
                create_notification(
                    user_type="Driver",
                    user_id=trip.driver_id,
                    message=f"Trip #{trip.id} has been cancelled by admin. Reason: {cancel_reason}"
                )
            
            db.session.add(log)
            db.session.commit()
            
            flash('Trip cancelled successfully.', 'success')
        
        return redirect(url_for('admin_trip_detail', trip_id=trip.id))
    
    # Get available drivers for assignment
    available_drivers = Driver.query.filter_by(is_approved=True, is_active=True).all()
    
    # Get trip logs
    trip_logs = TripLog.query.filter_by(trip_id=trip.id).order_by(TripLog.timestamp.desc()).all()
    
    return render_template(
        'admin/trip_detail.html', 
        trip=trip,
        available_drivers=available_drivers,
        trip_logs=trip_logs,
        TripStatus=TripStatus,
        TripType=TripType,
        RouteType=RouteType,
        is_authorized_role=is_authorized_role,
        route_types=[route_type.value for route_type in RouteType]
    )

@app.route('/admin/driver-management')
@admin_required
def driver_management():
    # Get all drivers
    drivers = Driver.query.all()
    
    # Current time for license expiry checks
    now = datetime.datetime.utcnow()
    
    # Check for license expirations
    expiring_count = check_license_expiry()
    if expiring_count > 0:
        flash(f'{expiring_count} drivers have licenses expiring within 30 days. Check notifications.', 'warning')
    
    return render_template('admin/driver_management.html', drivers=drivers, now=now)

@app.route('/admin/add-driver', methods=['GET', 'POST'])
@admin_required
def add_driver():
    if request.method == 'POST':
        # Generate a unique driver ID
        driver_id = f"DR{datetime.datetime.now().strftime('%y%m%d')}{random.randint(100, 999)}"
        
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        license_number = request.form.get('license_number')
        license_issue_date = datetime.datetime.strptime(request.form.get('license_issue_date'), '%Y-%m-%d')
        license_expiry_date = datetime.datetime.strptime(request.form.get('license_expiry_date'), '%Y-%m-%d')
        current_address = request.form.get('current_address')
        permanent_address = request.form.get('permanent_address')
        is_approved = True if request.form.get('is_approved') == 'on' else False
        is_active = True if request.form.get('is_active') == 'on' else False
        
        # Check if license number already exists
        existing_license = Driver.query.filter_by(license_number=license_number).first()
        if existing_license:
            flash('License number already registered.', 'danger')
            return render_template('admin/add_driver.html')
        
        # Check if phone number already exists
        existing_phone = Driver.query.filter_by(phone_number=phone_number).first()
        if existing_phone:
            flash('Phone number already registered.', 'danger')
            return render_template('admin/add_driver.html')
        
        # Create QR code for driver
        qr_code = generate_qr_code(driver_id, name)
        
        # Create new driver
        driver = Driver(
            driver_id=driver_id,
            name=name,
            phone_number=phone_number,
            email=email,
            license_number=license_number,
            license_issue_date=license_issue_date,
            license_expiry_date=license_expiry_date,
            current_address=current_address,
            permanent_address=permanent_address or current_address,  # Use current address if permanent is not provided
            qr_code=qr_code,
            is_approved=is_approved,
            is_active=is_active
        )
        driver.set_password(password)
        
        try:
            db.session.add(driver)
            db.session.commit()
            
            # Create notification for driver about their account creation
            create_notification(
                user_type="Driver",
                user_id=driver.id,
                message=f"Your driver account has been created by {current_user.name} with ID: {driver_id}."
            )
            
            # Record who created this driver
            admin_log = f"Driver created by {current_user.name} ({current_user.employee_id})"
            
            flash(f'Driver {name} successfully added with ID: {driver_id}', 'success')
            return redirect(url_for('driver_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating driver: {str(e)}', 'danger')
    
    return render_template('admin/add_driver.html')

@app.route('/admin/reset-driver-password/<int:driver_id>', methods=['POST'])
@admin_required
def reset_driver_password(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or not confirm_password:
        flash('Both password fields are required.', 'danger')
        return redirect(url_for('admin_driver_detail', driver_id=driver_id))
    
    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('admin_driver_detail', driver_id=driver_id))
    
    # Validate password complexity
    if (len(new_password) < 8 or not any(c.isupper() for c in new_password) or 
        not any(c.islower() for c in new_password) or 
        not any(c.isdigit() for c in new_password) or 
        not any(c in '@$!%*?&' for c in new_password)):
        flash('Password must be at least 8 characters and include uppercase, lowercase, number, and special character.', 'danger')
        return redirect(url_for('admin_driver_detail', driver_id=driver_id))
    
    try:
        driver.set_password(new_password)
        db.session.commit()
        
        # Create notification for the driver
        create_notification(
            user_type="Driver",
            user_id=driver.id,
            message=f"Your password has been reset by admin {current_user.name}. Please log in with your new password."
        )
        
        flash(f'Password for driver {driver.name} has been reset successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}', 'danger')
    
    return redirect(url_for('admin_driver_detail', driver_id=driver_id))

@app.route('/admin/driver/<int:driver_id>', methods=['GET', 'POST'])
@admin_required
def admin_driver_detail(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'approve_driver':
            driver.is_approved = True
            db.session.commit()
            flash(f'Driver {driver.name} approved successfully.', 'success')
        
        elif action == 'reject_driver':
            driver.is_approved = False
            db.session.commit()
            flash(f'Driver {driver.name} rejected.', 'danger')
        
        elif action == 'toggle_active':
            driver.is_active = not driver.is_active
            db.session.commit()
            status = "activated" if driver.is_active else "deactivated"
            flash(f'Driver {driver.name} {status} successfully.', 'success')
        
        elif action == 'update_driver':
            driver.name = request.form.get('name')
            driver.phone_number = request.form.get('phone_number')
            driver.email = request.form.get('email')
            driver.license_number = request.form.get('license_number')
            driver.license_issue_date = datetime.datetime.strptime(request.form.get('license_issue_date'), '%Y-%m-%d')
            driver.license_expiry_date = datetime.datetime.strptime(request.form.get('license_expiry_date'), '%Y-%m-%d')
            driver.current_address = request.form.get('current_address')
            driver.permanent_address = request.form.get('permanent_address')
            
            db.session.commit()
            flash('Driver details updated successfully.', 'success')
        
        return redirect(url_for('admin_driver_detail', driver_id=driver.id))
    
    # Get driver's trips
    trips = Trip.query.filter_by(driver_id=driver.id).order_by(Trip.trip_start_date.desc()).all()
    
    # Get driver's payments
    payments = DriverPayment.query.filter_by(driver_id=driver.id).order_by(DriverPayment.payment_date.desc()).all()
    
    # Current time for license expiry checks
    now = datetime.datetime.utcnow()
    
    return render_template(
        'admin/driver_detail.html', 
        driver=driver,
        trips=trips,
        payments=payments,
        now=now
    )

@app.route('/admin/track-driver/<int:driver_id>')
@admin_required
def track_driver(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    
    # Get active trip (if any)
    active_trip = Trip.query.filter_by(
        driver_id=driver.id, 
        status=TripStatus.STARTED
    ).first()
    
    return render_template(
        'admin/track_driver.html', 
        driver=driver,
        active_trip=active_trip
    )

@app.route('/admin/user-management')
@admin_required
def user_management():
    # Only super admins can manage users
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Get all admin users
    users = Admin.query.all()
    
    return render_template(
        'admin/user_management.html', 
        users=users,
        UserRole=UserRole
    )

@app.route('/admin/add-user', methods=['GET', 'POST'])
@admin_required
def add_user():
    # Only super admins can add users
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        employee_id = request.form.get('employee_id')
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        address = request.form.get('address')
        office_address = request.form.get('office_address')
        role = request.form.get('role')
        
        # Check if employee_id already exists
        existing_admin = Admin.query.filter_by(employee_id=employee_id).first()
        if existing_admin:
            flash('Employee ID already exists.', 'danger')
            return redirect(url_for('add_user'))
        
        # Check if email already exists
        existing_email = Admin.query.filter_by(email=email).first()
        if existing_email:
            flash('Email already registered.', 'danger')
            return redirect(url_for('add_user'))
        
        # Create new admin
        admin = Admin(
            employee_id=employee_id,
            name=name,
            phone_number=phone_number,
            email=email,
            address=address,
            office_address=office_address,
            role=UserRole(role)
        )
        admin.set_password(password)
        
        try:
            db.session.add(admin)
            db.session.commit()
            flash('User added successfully!', 'success')
            return redirect(url_for('user_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    roles = [role.value for role in UserRole]
    return render_template('admin/add_user.html', roles=roles)
    
@app.route('/admin/reset-password/<int:user_id>', methods=['POST'])
@admin_required
def reset_admin_password(user_id):
    # Only super admins can reset passwords
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to reset passwords.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    user = Admin.query.get_or_404(user_id)
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not new_password or not confirm_password:
        flash('Both password fields are required.', 'danger')
        return redirect(url_for('user_management'))
    
    if new_password != confirm_password:
        flash('Passwords do not match.', 'danger')
        return redirect(url_for('user_management'))
    
    # Validate password complexity
    if (len(new_password) < 8 or not any(c.isupper() for c in new_password) or 
        not any(c.islower() for c in new_password) or 
        not any(c.isdigit() for c in new_password) or 
        not any(c in '@$!%*?&' for c in new_password)):
        flash('Password must be at least 8 characters and include uppercase, lowercase, number, and special character.', 'danger')
        return redirect(url_for('user_management'))
    
    try:
        user.set_password(new_password)
        db.session.commit()
        
        # Create notification for the user
        create_notification(
            user_type="Admin",
            user_id=user.id,
            message=f"Your password has been reset by admin {current_user.name}. Please log in with your new password."
        )
        
        flash(f'Password for {user.name} has been reset successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error resetting password: {str(e)}', 'danger')
    
    return redirect(url_for('user_management'))

@app.route('/admin/finance')
@admin_required
def admin_finance():
    # Get completed trips
    completed_trips = Trip.query.filter_by(status=TripStatus.COMPLETED).order_by(Trip.ended_at.desc()).all()
    
    # Calculate totals
    total_revenue = sum(trip.total_amount or 0 for trip in completed_trips)
    total_driver_amount = sum(trip.driver_amount or 0 for trip in completed_trips)
    total_company_amount = sum(trip.company_amount or 0 for trip in completed_trips)
    total_gst = sum(trip.gst_amount or 0 for trip in completed_trips)
    
    # Get recent payments
    payments = DriverPayment.query.order_by(DriverPayment.payment_date.desc()).limit(10).all()
    
    return render_template(
        'admin/finance.html', 
        completed_trips=completed_trips,
        total_revenue=total_revenue,
        total_driver_amount=total_driver_amount,
        total_company_amount=total_company_amount,
        total_gst=total_gst,
        payments=payments,
        PaymentMode=PaymentMode
    )

@app.route('/admin/trip-prices', methods=['GET', 'POST'])
@admin_required
def trip_prices():
    # Only Admin, Operations, Manager, and Finance roles can access this page
    if current_user.role not in [UserRole.ADMIN, UserRole.OPERATIONS, UserRole.MANAGER, UserRole.FINANCE]:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Get all trip prices
    prices = TripPrice.query.order_by(TripPrice.route_type, TripPrice.trip_type).all()
    
    if request.method == 'POST':
        # Add or update a trip price
        route_type = request.form.get('route_type')
        trip_type = request.form.get('trip_type')
        per_hour_rate = float(request.form.get('per_hour_rate'))
        daytime_rate = float(request.form.get('daytime_rate'))
        nighttime_rate = float(request.form.get('nighttime_rate'))
        
        # Check if the combination already exists
        existing_price = TripPrice.query.filter_by(
            route_type=RouteType(route_type),
            trip_type=TripType(trip_type)
        ).first()
        
        if existing_price:
            # Update existing price
            existing_price.per_hour_rate = per_hour_rate
            existing_price.daytime_rate = daytime_rate
            existing_price.nighttime_rate = nighttime_rate
            existing_price.updated_at = datetime.datetime.utcnow()
            flash('Trip price updated successfully!', 'success')
        else:
            # Create new price
            new_price = TripPrice(
                route_type=RouteType(route_type),
                trip_type=TripType(trip_type),
                per_hour_rate=per_hour_rate,
                daytime_rate=daytime_rate,
                nighttime_rate=nighttime_rate,
                created_by_id=current_user.id
            )
            db.session.add(new_price)
            flash('Trip price added successfully!', 'success')
        
        try:
            db.session.commit()
            return redirect(url_for('trip_prices'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template(
        'admin/trip_prices.html',
        prices=prices,
        route_types=[route_type.value for route_type in RouteType],
        trip_types=[trip_type.value for trip_type in TripType]
    )

@app.route('/admin/trip-prices/<int:price_id>/delete', methods=['POST'])
@admin_required
def delete_trip_price(price_id):
    # Only Admin, Operations, and Finance roles can delete prices
    if current_user.role not in [UserRole.ADMIN, UserRole.OPERATIONS, UserRole.FINANCE]:
        flash('You do not have permission to delete trip prices.', 'danger')
        return redirect(url_for('trip_prices'))
    
    price = TripPrice.query.get_or_404(price_id)
    
    try:
        db.session.delete(price)
        db.session.commit()
        flash('Trip price deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting trip price: {str(e)}', 'danger')
    
    return redirect(url_for('trip_prices'))

@app.route('/admin/driver/<int:driver_id>/documents', methods=['GET', 'POST'])
@admin_required
def driver_documents(driver_id):
    # Only Admin, Driver Recruitment, Operations, and Manager roles can access this page
    if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER_RECRUITMENT, UserRole.OPERATIONS, UserRole.MANAGER]:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    driver = Driver.query.get_or_404(driver_id)
    documents = DriverDocument.query.filter_by(driver_id=driver_id).all()
    
    if request.method == 'POST':
        document_type = request.form.get('document_type')
        file = request.files.get('document_file')
        
        if not file:
            flash('No file selected.', 'danger')
            return redirect(url_for('driver_documents', driver_id=driver_id))
        
        if file.filename == '':
            flash('No file selected.', 'danger')
            return redirect(url_for('driver_documents', driver_id=driver_id))
        
        # Create uploads directory if it doesn't exist
        uploads_dir = os.path.join(app.root_path, 'static', 'uploads', 'driver_documents')
        os.makedirs(uploads_dir, exist_ok=True)
        
        # Save the file
        filename = secure_filename(f"{driver.driver_id}_{document_type}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.jpg")
        file_path = os.path.join(uploads_dir, filename)
        file.save(file_path)
        
        # Save relative path to database
        db_file_path = os.path.join('uploads', 'driver_documents', filename)
        
        document = DriverDocument(
            driver_id=driver_id,
            document_type=document_type,
            file_path=db_file_path,
            uploaded_by_id=current_user.id
        )
        
        try:
            db.session.add(document)
            db.session.commit()
            flash('Document uploaded successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error uploading document: {str(e)}', 'danger')
        
        return redirect(url_for('driver_documents', driver_id=driver_id))
    
    document_types = [
        'License Front',
        'License Back',
        'Aadhaar Front',
        'Aadhaar Back',
        'Bank Passbook/Statement'
    ]
    
    return render_template(
        'admin/driver_documents.html',
        driver=driver,
        documents=documents,
        document_types=document_types
    )

@app.route('/admin/process-payment/<int:trip_id>', methods=['POST'])
@admin_required
def process_payment(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    if trip.status != TripStatus.COMPLETED:
        flash('Cannot process payment for uncompleted trip.', 'danger')
        return redirect(url_for('admin_finance'))
    
    payment_mode = request.form.get('payment_mode')
    
    # Create payment record
    payment = DriverPayment(
        driver_id=trip.driver_id,
        trip_id=trip.id,
        amount=trip.driver_amount,
        payment_mode=PaymentMode(payment_mode)
    )
    
    # Create notification for driver
    create_notification(
        user_type="Driver",
        user_id=trip.driver_id,
        message=f"Payment of ₹{trip.driver_amount:.2f} processed for trip #{trip.id}."
    )
    
    db.session.add(payment)
    db.session.commit()
    
    flash('Payment processed successfully.', 'success')
    return redirect(url_for('admin_finance'))

@app.route('/admin/generate-invoice/<int:trip_id>')
@admin_required
def generate_invoice(trip_id):
    from datetime import timedelta
    
    trip = Trip.query.get_or_404(trip_id)
    
    if trip.status != TripStatus.COMPLETED:
        flash('Cannot generate invoice for uncompleted trip.', 'danger')
        return redirect(url_for('admin_finance'))
    
    # Get current time for the invoice
    now = datetime.datetime.now()
    
    # In a real app, we would generate a PDF invoice
    # For this demo, we'll just render a template
    return render_template(
        'admin/invoice.html',
        trip=trip,
        invoice_number=f"INV-{trip.id}-{now.strftime('%Y%m%d')}",
        now=now,
        timedelta=timedelta
    )

@app.route('/admin/reports')
@admin_required
def admin_reports():
    # Get date range from query parameters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    report_type = request.args.get('report_type', 'daily')
    
    # Parse dates or use defaults
    try:
        if start_date_str:
            start_date = datetime.datetime.strptime(start_date_str, '%Y-%m-%d')
        else:
            start_date = datetime.datetime.now() - timedelta(days=30)
            
        if end_date_str:
            end_date = datetime.datetime.strptime(end_date_str, '%Y-%m-%d')
        else:
            end_date = datetime.datetime.now()
    except ValueError:
        flash('Invalid date format. Please use YYYY-MM-DD.', 'danger')
        start_date = datetime.datetime.now() - timedelta(days=30)
        end_date = datetime.datetime.now()
    
    # Ensure end date includes the entire day
    end_date = end_date.replace(hour=23, minute=59, second=59)
    
    # Get trips within date range
    trips = Trip.query.filter(
        Trip.created_at >= start_date,
        Trip.created_at <= end_date
    ).order_by(Trip.created_at).all()
    
    # Prepare report data
    report_data = {
        'total_trips': len(trips),
        'completed_trips': sum(1 for trip in trips if trip.status == TripStatus.COMPLETED),
        'cancelled_trips': sum(1 for trip in trips if trip.status == TripStatus.CANCELLED),
        'total_revenue': sum(trip.total_amount or 0 for trip in trips if trip.status == TripStatus.COMPLETED),
        'avg_trip_duration': sum((trip.ended_at - trip.started_at).total_seconds() / 3600 if trip.ended_at and trip.started_at else 0 
                               for trip in trips if trip.status == TripStatus.COMPLETED) / 
                            max(1, sum(1 for trip in trips if trip.status == TripStatus.COMPLETED))
    }
    
    return render_template(
        'admin/reports.html',
        trips=trips,
        report_data=report_data,
        report_type=report_type,
        start_date=start_date,
        end_date=end_date,
        TripStatus=TripStatus
    )

@app.route('/admin/customer-management')
@admin_required
def customer_management():
    # Get all customers
    customers = Customer.query.all()
    
    # Pass datetime and timedelta for calculations in template
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    
    return render_template('admin/customer_management.html', 
                           customers=customers,
                           now=now,
                           timedelta=timedelta)

@app.route('/admin/add-customer', methods=['GET', 'POST'])
@admin_required
def add_customer():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile_number = request.form.get('mobile_number')
        home_address = request.form.get('home_address')
        office_address = request.form.get('office_address')
        vehicle_model = request.form.get('vehicle_model')
        
        # Check if mobile number already exists
        existing_customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        if existing_customer:
            flash('Mobile number already registered.', 'danger')
            return render_template('admin/add_customer.html')
        
        # Create new customer
        customer = Customer(
            name=name,
            mobile_number=mobile_number,
            home_address=home_address,
            office_address=office_address,
            vehicle_model=vehicle_model
        )
        
        try:
            db.session.add(customer)
            db.session.commit()
            
            # Create log
            if isinstance(current_user, Admin):
                create_notification(
                    user_type="Admin",
                    user_id=current_user.id,
                    message=f"Admin {current_user.name} created a new customer: {name}"
                )
            
            flash('Customer added successfully!', 'success')
            return redirect(url_for('customer_management'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error creating customer: {str(e)}', 'danger')
    
    return render_template('admin/add_customer.html')

@app.route('/admin/customer/<int:customer_id>')
@admin_required
def admin_customer_detail(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    
    # Get customer's trips
    trips = Trip.query.filter_by(customer_id=customer.id).order_by(Trip.trip_start_date.desc()).all()
    
    return render_template(
        'admin/customer_detail.html', 
        customer=customer,
        trips=trips
    )

@app.route('/admin/notifications')
@admin_required
def admin_notifications():
    # Get all notifications for admin
    notifications = Notification.query.filter_by(
        user_type='Admin'
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    # Add current datetime for template
    now = datetime.datetime.utcnow()
    
    return render_template('admin/notifications.html', notifications=notifications, now=now)

# ========== FIRE DETAILS ROUTES ==========

@app.route('/admin/fire-details')
@admin_required
def fire_details():
    # Get all fire details
    fire_details = FireDetail.query.order_by(FireDetail.date_time.desc()).all()
    return render_template('admin/fire_details.html', fire_details=fire_details)

@app.route('/admin/trip-estimation')
@admin_required
def trip_estimation():
    trip_types = [trip_type.value for trip_type in TripType]
    route_types = [route_type.value for route_type in RouteType]
    return render_template('admin/fire_details.html', trip_types=trip_types, route_types=route_types)

@app.route('/admin/add-fire-detail', methods=['GET', 'POST'])
@admin_required
def add_fire_detail():
    # Only allow access to users with Admin role
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    if request.method == 'POST':
        # Generate a unique fire_id
        fire_id = f"FIRE-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        
        # Get form data
        location = request.form.get('location')
        date_time_str = request.form.get('date_time')
        status = request.form.get('status')
        severity = request.form.get('severity')
        description = request.form.get('description')
        
        try:
            # Parse date_time
            date_time = datetime.datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
            
            # Create new fire detail
            fire_detail = FireDetail(
                fire_id=fire_id,
                location=location,
                date_time=date_time,
                status=status,
                severity=severity,
                description=description,
                reported_by_id=current_user.id
            )
            
            db.session.add(fire_detail)
            db.session.commit()
            
            # Create notification
            create_notification(
                user_type="Admin",
                user_id=current_user.id,
                message=f"New fire incident reported: {fire_id} at {location}"
            )
            
            flash('Fire detail added successfully!', 'success')
            return redirect(url_for('fire_details'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error adding fire detail: {str(e)}', 'danger')
    
    return render_template('admin/add_fire_detail.html')

@app.route('/admin/fire-detail/<int:fire_id>')
@admin_required
def fire_detail(fire_id):
    # Only allow access to users with Admin role
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Get fire detail
    fire_detail = FireDetail.query.get_or_404(fire_id)
    
    return render_template('admin/fire_detail.html', fire_detail=fire_detail)

@app.route('/admin/update-fire-detail/<int:fire_id>', methods=['GET', 'POST'])
@admin_required
def update_fire_detail(fire_id):
    # Only allow access to users with Admin role
    if current_user.role != UserRole.ADMIN:
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin_dashboard'))
    
    # Get fire detail
    fire_detail = FireDetail.query.get_or_404(fire_id)
    
    if request.method == 'POST':
        # Get form data
        location = request.form.get('location')
        date_time_str = request.form.get('date_time')
        status = request.form.get('status')
        severity = request.form.get('severity')
        description = request.form.get('description')
        
        try:
            # Parse date_time
            date_time = datetime.datetime.strptime(date_time_str, '%Y-%m-%dT%H:%M')
            
            # Update fire detail
            fire_detail.location = location
            fire_detail.date_time = date_time
            fire_detail.status = status
            fire_detail.severity = severity
            fire_detail.description = description
            
            db.session.commit()
            
            # Create notification
            create_notification(
                user_type="Admin",
                user_id=current_user.id,
                message=f"Fire incident updated: {fire_detail.fire_id} at {location}"
            )
            
            flash('Fire detail updated successfully!', 'success')
            return redirect(url_for('fire_detail', fire_id=fire_id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating fire detail: {str(e)}', 'danger')
    
    return render_template('admin/update_fire_detail.html', fire_detail=fire_detail)

# ========== CUSTOMER ROUTES ==========

@app.route('/customer/login', methods=['GET', 'POST'])
def customer_login():
    if current_user.is_authenticated and current_user.is_customer():
        return redirect(url_for('customer_dashboard'))
    
    if request.method == 'POST':
        mobile_number = request.form.get('mobile_number')
        
        # Check if customer exists
        customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        
        if not customer:
            flash('Mobile number not registered. Please register first.', 'danger')
            return redirect(url_for('customer_register'))
        
        # Generate OTP
        otp = generate_otp()
        customer.set_otp(otp)
        db.session.commit()
        
        # Send OTP via Twilio
        success, message = send_otp(mobile_number, otp)
        
        if success:
            # Store mobile in session for OTP verification
            session['customer_mobile'] = mobile_number
            flash('OTP sent to your mobile number.', 'success')
            return redirect(url_for('customer_verify_otp'))
        else:
            flash(f'Failed to send OTP: {message}. Please try again.', 'danger')
    
    return render_template('customer/login.html')

@app.route('/customer/verify-otp', methods=['GET', 'POST'])
def customer_verify_otp():
    if not session.get('customer_mobile'):
        flash('Please enter your mobile number first.', 'danger')
        return redirect(url_for('customer_login'))
    
    if request.method == 'POST':
        otp = request.form.get('otp')
        mobile_number = session.get('customer_mobile')
        
        customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        
        if customer and customer.verify_otp(otp):
            login_user(customer)
            session.pop('customer_mobile', None)  # Clear session
            flash('Login successful!', 'success')
            return redirect(url_for('customer_dashboard'))
        else:
            flash('Invalid or expired OTP. Please try again.', 'danger')
    
    return render_template('customer/otp_verification.html')

@app.route('/customer/register', methods=['GET', 'POST'])
def customer_register():
    if request.method == 'POST':
        name = request.form.get('name')
        mobile_number = request.form.get('mobile_number')
        home_address = request.form.get('home_address')
        office_address = request.form.get('office_address')
        vehicle_model = request.form.get('vehicle_model')
        
        # Check if mobile number already exists
        existing_customer = Customer.query.filter_by(mobile_number=mobile_number).first()
        if existing_customer:
            flash('Mobile number already registered.', 'danger')
            return render_template('customer/register.html')
        
        # Create new customer
        customer = Customer(
            name=name,
            mobile_number=mobile_number,
            home_address=home_address,
            office_address=office_address,
            vehicle_model=vehicle_model
        )
        
        try:
            db.session.add(customer)
            db.session.commit()
            flash('Registration successful! You can now log in.', 'success')
            return redirect(url_for('customer_login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('customer/register.html')

@app.route('/customer/dashboard')
@customer_required
def customer_dashboard():
    # Get customer's trips
    trips = Trip.query.filter_by(customer_id=current_user.id).order_by(Trip.trip_start_date.desc()).all()
    
    # Get notifications
    notifications = Notification.query.filter_by(
        user_type='Customer', 
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    # Count stats for dashboard
    upcoming_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.trip_start_date > datetime.datetime.utcnow(),
        Trip.status.in_([TripStatus.PENDING, TripStatus.ASSIGNED])
    ).count()
    
    active_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.STARTED
    ).count()
    
    completed_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).count()
    
    return render_template(
        'customer/dashboard.html', 
        trips=trips,
        notifications=notifications,
        upcoming_trips=upcoming_trips,
        active_trips=active_trips,
        completed_trips=completed_trips
    )

@app.route('/customer/logout')
@customer_required
def customer_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('customer_login'))

@app.route('/customer/book-trip', methods=['GET', 'POST'])
@customer_required
def book_trip():
    if request.method == 'POST':
        trip_start_date = datetime.datetime.strptime(request.form.get('trip_start_date'), '%Y-%m-%dT%H:%M')
        trip_end_date = datetime.datetime.strptime(request.form.get('trip_end_date'), '%Y-%m-%dT%H:%M')
        trip_type = request.form.get('trip_type')
        route_type = request.form.get('route_type')
        pickup_location = request.form.get('pickup_location')
        drop_location = request.form.get('drop_location')
        
        # Validate dates
        if trip_start_date < datetime.datetime.now():
            flash('Trip start date cannot be in the past.', 'danger')
            return redirect(url_for('book_trip'))
        
        if trip_end_date <= trip_start_date:
            flash('Trip end date must be after start date.', 'danger')
            return redirect(url_for('book_trip'))
        
        # Find applicable trip price
        trip_price = TripPrice.query.filter_by(
            route_type=RouteType(route_type),
            trip_type=TripType(trip_type)
        ).first()
        
        # Create new trip
        trip = Trip(
            customer_id=current_user.id,
            trip_start_date=trip_start_date,
            trip_end_date=trip_end_date,
            trip_type=TripType(trip_type),
            route_type=RouteType(route_type),
            trip_price_id=trip_price.id if trip_price else None,
            pickup_location=pickup_location,
            drop_location=drop_location,
            status=TripStatus.PENDING
        )
        
        try:
            db.session.add(trip)
            db.session.commit()
            
            # Create notification for admin
            create_notification(
                user_type="Admin",
                user_id=1,  # Assuming ID 1 is a super admin
                message=f"New trip booking #{trip.id} from {current_user.name} for {trip_start_date.strftime('%Y-%m-%d %H:%M')}"
            )
            
            flash('Trip booked successfully!', 'success')
            return redirect(url_for('customer_dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error booking trip: {str(e)}', 'danger')
    
    # Get trip types and route types
    trip_types = [trip_type.value for trip_type in TripType]
    route_types = [route_type.value for route_type in RouteType]
    
    return render_template('customer/book_trip.html', trip_types=trip_types, route_types=route_types)

@app.route('/customer/trip/<int:trip_id>')
@customer_required
def customer_trip_detail(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Ensure the trip belongs to the current user
    if trip.customer_id != current_user.id:
        flash('You do not have permission to view this trip.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    return render_template('customer/trip_detail.html', trip=trip, TripStatus=TripStatus)

@app.route('/customer/trip-history')
@customer_required
def trip_history():
    # Get all customer's trips
    trips = Trip.query.filter_by(customer_id=current_user.id).order_by(Trip.trip_start_date.desc()).all()
    
    return render_template('customer/trip_history.html', trips=trips, TripStatus=TripStatus)

@app.route('/customer/payment-history')
@customer_required
def payment_history():
    # Get completed trips
    completed_trips = Trip.query.filter(
        Trip.customer_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).order_by(Trip.ended_at.desc()).all()
    
    return render_template('customer/payment_history.html', trips=completed_trips)

@app.route('/customer/track-driver/<int:trip_id>')
@customer_required
def customer_track_driver(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Ensure the trip belongs to the current user
    if trip.customer_id != current_user.id:
        flash('You do not have permission to view this trip.', 'danger')
        return redirect(url_for('customer_dashboard'))
    
    # Ensure trip has a driver assigned
    if not trip.driver_id:
        flash('No driver assigned to this trip yet.', 'warning')
        return redirect(url_for('customer_trip_detail', trip_id=trip.id))
    
    driver = Driver.query.get_or_404(trip.driver_id)
    
    return render_template('customer/track_driver.html', trip=trip, driver=driver)

@app.route('/customer/notifications')
@customer_required
def customer_notifications():
    # Get all notifications for current customer
    notifications = Notification.query.filter_by(
        user_type='Customer',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    # Add current datetime for template
    now = datetime.datetime.utcnow()
    
    return render_template('customer/notifications.html', notifications=notifications, now=now)

# ========== DRIVER ROUTES ==========

@app.route('/driver/login', methods=['GET', 'POST'])
def driver_login():
    if current_user.is_authenticated and current_user.is_driver():
        return redirect(url_for('driver_dashboard'))
    
    if request.method == 'POST':
        driver_id = request.form.get('driver_id')
        password = request.form.get('password')
        
        print(f"Login attempt for driver_id: {driver_id}")
        
        driver = Driver.query.filter_by(driver_id=driver_id).first()
        
        if driver:
            print(f"Driver found: {driver.name}")
            password_check = driver.check_password(password)
            print(f"Password check result: {password_check}")
            
            if password_check:
                if not driver.is_approved:
                    flash('Your account is pending approval. Please contact the administrator.', 'warning')
                    return render_template('driver/login.html')
                
                if not driver.is_active:
                    flash('Your account has been deactivated. Please contact the administrator.', 'danger')
                    return render_template('driver/login.html')
                
                login_result = login_user(driver)
                print(f"Login result: {login_result}, user.is_authenticated: {current_user.is_authenticated}")
                print(f"Current user ID: {current_user.id}, type: {type(current_user)}")
                flash('Login successful!', 'success')
                return redirect(url_for('driver_dashboard'))
            else:
                flash('Invalid driver ID or password. Password check failed.', 'danger')
        else:
            print(f"No driver found with ID: {driver_id}")
            flash('Invalid driver ID or password. Driver not found.', 'danger')
    
    return render_template('driver/login.html')

@app.route('/driver/register', methods=['GET', 'POST'])
def driver_register():
    if request.method == 'POST':
        # Generate a unique driver ID
        driver_id = f"DR{datetime.datetime.now().strftime('%y%m%d')}{random.randint(100, 999)}"
        
        name = request.form.get('name')
        phone_number = request.form.get('phone_number')
        email = request.form.get('email')
        password = request.form.get('password')
        license_number = request.form.get('license_number')
        license_issue_date = datetime.datetime.strptime(request.form.get('license_issue_date'), '%Y-%m-%d')
        license_expiry_date = datetime.datetime.strptime(request.form.get('license_expiry_date'), '%Y-%m-%d')
        current_address = request.form.get('current_address')
        permanent_address = request.form.get('permanent_address')
        
        # Check if license number already exists
        existing_license = Driver.query.filter_by(license_number=license_number).first()
        if existing_license:
            flash('License number already registered.', 'danger')
            return render_template('driver/register.html')
        
        # Check if phone number already exists
        existing_phone = Driver.query.filter_by(phone_number=phone_number).first()
        if existing_phone:
            flash('Phone number already registered.', 'danger')
            return render_template('driver/register.html')
        
        # Create QR code for driver
        qr_code = generate_qr_code(driver_id, name)
        
        # Create new driver
        driver = Driver(
            driver_id=driver_id,
            name=name,
            phone_number=phone_number,
            email=email,
            license_number=license_number,
            license_issue_date=license_issue_date,
            license_expiry_date=license_expiry_date,
            current_address=current_address,
            permanent_address=permanent_address or current_address,  # Use current address if permanent is not provided
            qr_code=qr_code
        )
        driver.set_password(password)
        
        try:
            db.session.add(driver)
            db.session.commit()
            
            # Create notification for admin
            create_notification(
                user_type="Admin",
                user_id=1,  # Assuming ID 1 is a super admin
                message=f"New driver registration: {name} (ID: {driver_id}) awaiting approval"
            )
            
            flash('Registration successful! Please wait for admin approval.', 'success')
            return redirect(url_for('driver_login'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error: {str(e)}', 'danger')
    
    return render_template('driver/register.html')

@app.route('/driver/dashboard')
@driver_required
def driver_dashboard():
    # Get driver's assigned trips
    assigned_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status.in_([TripStatus.ASSIGNED, TripStatus.STARTED])
    ).order_by(Trip.trip_start_date).all()
    
    # Get completed trips
    completed_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).order_by(Trip.trip_start_date.desc()).limit(5).all()
    
    # Get notifications
    notifications = Notification.query.filter_by(
        user_type='Driver', 
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(10).all()
    
    # Run upcoming trip checks
    check_upcoming_trips()
    
    # Add current datetime for template expiry check
    now = datetime.datetime.utcnow()
    
    return render_template(
        'driver/dashboard.html', 
        assigned_trips=assigned_trips,
        completed_trips=completed_trips,
        notifications=notifications,
        TripStatus=TripStatus,
        now=now
    )

@app.route('/driver/logout')
@driver_required
def driver_logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('driver_login'))

@app.route('/driver/trip/<int:trip_id>', methods=['GET', 'POST'])
@driver_required
def driver_trip_detail(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    # Ensure the trip is assigned to the current driver
    if trip.driver_id != current_user.id:
        flash('You are not assigned to this trip.', 'danger')
        return redirect(url_for('driver_dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'start_trip':
            selfie_data = request.form.get('selfie_data')
            if not selfie_data:
                flash('Please take a selfie before starting the trip.', 'danger')
                return redirect(url_for('driver_trip_detail', trip_id=trip.id))
            
            # Get location data
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            
            # Add timestamp to selfie
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            location_text = f"Starting at {trip.pickup_location}"
            text_overlay = f"{timestamp} - {location_text}"
            selfie_with_text = overlay_text_on_image(selfie_data, text_overlay)
            
            # Update trip status
            trip.status = TripStatus.STARTED
            trip.started_at = datetime.datetime.utcnow()
            trip.start_selfie = selfie_with_text
            
            # Update driver location
            current_user.update_location(float(latitude), float(longitude))
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=trip.customer_id,
                message=f"Your trip has started. Driver {current_user.name} is on the way."
            )
            
            db.session.commit()
            flash('Trip started successfully.', 'success')
        
        elif action == 'end_trip':
            selfie_data = request.form.get('selfie_data')
            if not selfie_data:
                flash('Please take a selfie before ending the trip.', 'danger')
                return redirect(url_for('driver_trip_detail', trip_id=trip.id))
            
            # Get location data
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            
            # Add timestamp to selfie
            timestamp = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
            location_text = f"Ending at {trip.drop_location if trip.drop_location else trip.pickup_location}"
            text_overlay = f"{timestamp} - {location_text}"
            selfie_with_text = overlay_text_on_image(selfie_data, text_overlay)
            
            # Update trip status
            trip.status = TripStatus.COMPLETED
            trip.ended_at = datetime.datetime.utcnow()
            trip.end_selfie = selfie_with_text
            
            # Calculate bill
            bill_details = trip.calculate_bill()
            
            # Update driver location
            current_user.update_location(float(latitude), float(longitude))
            
            # Create notification for customer
            create_notification(
                user_type="Customer",
                user_id=trip.customer_id,
                message=f"Your trip has ended. Total fare: ₹{trip.total_amount:.2f}"
            )
            
            # Create notification for admin
            create_notification(
                user_type="Admin",
                user_id=1,
                message=f"Trip #{trip.id} completed by driver {current_user.name}. Revenue: ₹{trip.total_amount:.2f}"
            )
            
            db.session.commit()
            flash('Trip ended successfully.', 'success')
        
        elif action == 'update_location':
            # Get location data
            latitude = request.form.get('latitude')
            longitude = request.form.get('longitude')
            
            # Update driver location
            current_user.update_location(float(latitude), float(longitude))
            db.session.commit()
            
            return jsonify({'status': 'success'})
        
        return redirect(url_for('driver_trip_detail', trip_id=trip.id))
    
    return render_template('driver/trip_details.html', trip=trip, TripStatus=TripStatus)

@app.route('/driver/payment-info')
@driver_required
def driver_payment_info():
    # Get all payments for the driver
    payments = DriverPayment.query.filter_by(driver_id=current_user.id).order_by(DriverPayment.payment_date.desc()).all()
    
    # Calculate total earnings
    total_earnings = sum(payment.amount for payment in payments)
    
    # Get trips that haven't been paid yet
    completed_trips = Trip.query.filter(
        Trip.driver_id == current_user.id,
        Trip.status == TripStatus.COMPLETED
    ).all()
    
    paid_trip_ids = [payment.trip_id for payment in payments]
    unpaid_trips = [trip for trip in completed_trips if trip.id not in paid_trip_ids]
    
    return render_template(
        'driver/payment_info.html', 
        payments=payments,
        total_earnings=total_earnings,
        unpaid_trips=unpaid_trips,
        PaymentMode=PaymentMode
    )

@app.route('/driver/notifications')
@driver_required
def driver_notifications():
    # Get all notifications for current driver
    notifications = Notification.query.filter_by(
        user_type='Driver',
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    
    # Mark all as read
    for notification in notifications:
        notification.is_read = True
    
    db.session.commit()
    
    # Add current datetime for template
    now = datetime.datetime.utcnow()
    
    return render_template('driver/notifications.html', notifications=notifications, now=now)

@app.route('/driver/qr-code')
@driver_required
def driver_qr_code():
    return render_template('driver/qr_code.html', driver=current_user)

# ========== API ROUTES ==========

@app.route('/api/driver-location/<int:driver_id>')
def get_driver_location(driver_id):
    driver = Driver.query.get_or_404(driver_id)
    
    # Check if location is available
    if not driver.latitude or not driver.longitude:
        return jsonify({
            'error': 'Location not available',
            'success': False
        }), 404
    
    # Check if location is stale (older than 10 minutes)
    if not driver.last_location_update or (datetime.datetime.utcnow() - driver.last_location_update).total_seconds() > 600:
        return jsonify({
            'error': 'Location data is stale',
            'success': False,
            'last_update': driver.last_location_update.isoformat() if driver.last_location_update else None
        }), 404
    
    return jsonify({
        'success': True,
        'latitude': driver.latitude,
        'longitude': driver.longitude,
        'last_update': driver.last_location_update.isoformat(),
        'driver_name': driver.name
    })

@app.route('/api/notifications/count')
def get_notification_count():
    if not current_user.is_authenticated:
        return jsonify({'count': 0})
    
    user_type = None
    if hasattr(current_user, 'employee_id'):
        user_type = 'Admin'
    elif hasattr(current_user, 'mobile_number'):
        user_type = 'Customer'
    elif hasattr(current_user, 'driver_id'):
        user_type = 'Driver'
    
    if not user_type:
        return jsonify({'count': 0})
    
    count = Notification.query.filter_by(
        user_type=user_type,
        user_id=current_user.id,
        is_read=False
    ).count()
    
    return jsonify({'count': count})

@app.route('/api/trip/<int:trip_id>/bill')
def get_trip_bill(trip_id):
    trip = Trip.query.get_or_404(trip_id)
    
    if not trip.started_at or not trip.ended_at:
        return jsonify({
            'error': 'Trip has not started or ended yet',
            'success': False
        }), 400
    
    bill_details = trip.calculate_bill()
    
    return jsonify({
        'success': True,
        'trip_id': trip.id,
        'customer_name': trip.customer.name,
        'driver_name': trip.driver.name if trip.driver else None,
        'bill_details': bill_details
    })

# Configure error handlers
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errors/500.html'), 500
