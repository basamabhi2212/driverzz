import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import enum

class UserRole(enum.Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    FINANCE = "Finance"
    OPERATIONS = "Operations"
    DRIVER_RECRUITMENT = "Driver Recruitment"

class TripType(enum.Enum):
    ONE_WAY = "One-way"
    ROUND_TRIP = "Round Trip"
    
class RouteType(enum.Enum):
    INSTATION = "In Station"
    OUTSTATION = "Out Station"

class TripStatus(enum.Enum):
    PENDING = "Pending"
    ASSIGNED = "Assigned"
    STARTED = "Started"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"

class PaymentMode(enum.Enum):
    CASH = "Cash"
    ONLINE = "Online"

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    
    id = Column(Integer, primary_key=True)
    employee_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(15), nullable=False)
    email = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(256), nullable=False)
    address = Column(String(255), nullable=False)
    office_address = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.ADMIN)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    # Override UserMixin methods to better distinguish between user types
    def get_id(self):
        return f"admin_{self.id}"
        
    def is_admin(self):
        return True
        
    def is_driver(self):
        return False
        
    def is_customer(self):
        return False

class Customer(UserMixin, db.Model):
    __tablename__ = 'customers'
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    mobile_number = Column(String(15), unique=True, nullable=False)
    home_address = Column(String(255), nullable=False)
    office_address = Column(String(255), nullable=True)
    vehicle_model = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    trips = relationship("Trip", back_populates="customer")
    
    # OTP related fields
    otp = Column(String(6), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    
    def set_otp(self, otp):
        self.otp = otp
        self.otp_expiry = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
    
    def verify_otp(self, otp):
        return (self.otp == otp and 
                self.otp_expiry and 
                datetime.datetime.utcnow() < self.otp_expiry)
                
    # Override UserMixin methods to better distinguish between user types
    def get_id(self):
        return f"customer_{self.id}"
        
    def is_admin(self):
        return False
        
    def is_driver(self):
        return False
        
    def is_customer(self):
        return True

class Driver(UserMixin, db.Model):
    __tablename__ = 'drivers'
    
    id = Column(Integer, primary_key=True)
    driver_id = Column(String(20), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    phone_number = Column(String(15), unique=True, nullable=False)
    email = Column(String(100), unique=True, nullable=True)
    password_hash = Column(String(256), nullable=False)
    license_number = Column(String(50), unique=True, nullable=False)
    license_issue_date = Column(DateTime, nullable=False)
    license_expiry_date = Column(DateTime, nullable=False)
    current_address = Column(String(255), nullable=False)
    permanent_address = Column(String(255), nullable=False)
    qr_code = Column(Text, nullable=True)  # Store QR code as base64 encoded string
    is_approved = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Current location
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    last_location_update = Column(DateTime, nullable=True)
    
    # Relationships
    trips = relationship("Trip", back_populates="driver")
    payments = relationship("DriverPayment", back_populates="driver")
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def update_location(self, latitude, longitude):
        self.latitude = latitude
        self.longitude = longitude
        self.last_location_update = datetime.datetime.utcnow()
        
    # Override UserMixin methods to better distinguish between user types
    def get_id(self):
        return f"driver_{self.id}"
        
    def is_admin(self):
        return False
        
    def is_driver(self):
        return True
        
    def is_customer(self):
        return False

class Trip(db.Model):
    __tablename__ = 'trips'
    
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey('customers.id'), nullable=False)
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=True)
    trip_start_date = Column(DateTime, nullable=False)
    trip_end_date = Column(DateTime, nullable=False)
    trip_type = Column(Enum(TripType), nullable=False)
    route_type = Column(Enum(RouteType), nullable=False, default=RouteType.INSTATION)
    trip_price_id = Column(Integer, ForeignKey('trip_prices.id'), nullable=True)
    pickup_location = Column(String(255), nullable=False)
    drop_location = Column(String(255), nullable=True)  # Nullable for round trips
    status = Column(Enum(TripStatus), default=TripStatus.PENDING)
    
    # Trip timestamps
    assigned_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    ended_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    cancel_reason = Column(String(255), nullable=True)
    
    # Trip financials
    total_hours = Column(Float, nullable=True)
    driver_amount = Column(Float, nullable=True)
    company_amount = Column(Float, nullable=True)
    gst_amount = Column(Float, nullable=True)
    total_amount = Column(Float, nullable=True)
    
    # Selfie paths
    start_selfie = Column(String(255), nullable=True)
    end_selfie = Column(String(255), nullable=True)
    
    # Relationships
    customer = relationship("Customer", back_populates="trips")
    driver = relationship("Driver", back_populates="trips")
    
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Last user who modified the trip
    last_modified_by_id = Column(Integer, ForeignKey('admins.id'), nullable=True)
    last_modified_by = relationship("Admin")
    
    # Adding the new relationship for price
    trip_price = relationship("TripPrice")
    
    def calculate_bill(self):
        if not self.started_at or not self.ended_at:
            return None
        
        # Calculate duration in hours
        duration = (self.ended_at - self.started_at).total_seconds() / 3600
        self.total_hours = duration
        
        daytime_hours = 0
        nighttime_hours = 0
        
        # Calculate daytime and nighttime hours
        current_time = self.started_at
        while current_time < self.ended_at:
            hour = current_time.hour
            if 7 <= hour < 22:  # Daytime (7:00 AM - 10:00 PM)
                daytime_hours += min(1, (self.ended_at - current_time).total_seconds() / 3600)
            else:  # Nighttime (10:00 PM - 7:00 AM)
                nighttime_hours += min(1, (self.ended_at - current_time).total_seconds() / 3600)
            current_time += datetime.timedelta(hours=1)
            
        # Apply rates
        # First try to get rates from trip_price if available
        if self.trip_price_id and self.trip_price:
            per_hour_rate = self.trip_price.per_hour_rate
            daytime_driver_rate = self.trip_price.daytime_rate
            nighttime_driver_rate = self.trip_price.nighttime_rate
            company_rate = per_hour_rate - ((daytime_driver_rate + nighttime_driver_rate) / 2)  # Average of day/night rate difference
        else:
            # Fallback to default rates if no pricing is set
            daytime_driver_rate = 86  # ₹86/hr
            nighttime_driver_rate = 96  # ₹96/hr
            company_rate = 14  # ₹14/hr
        
        self.driver_amount = (daytime_hours * daytime_driver_rate) + (nighttime_hours * nighttime_driver_rate)
        self.company_amount = (daytime_hours + nighttime_hours) * company_rate
        
        # Calculate GST (18%)
        subtotal = self.driver_amount + self.company_amount
        self.gst_amount = subtotal * 0.18
        
        # Calculate total amount
        self.total_amount = subtotal + self.gst_amount
        
        return {
            'total_hours': self.total_hours,
            'daytime_hours': daytime_hours,
            'nighttime_hours': nighttime_hours,
            'driver_amount': self.driver_amount,
            'company_amount': self.company_amount,
            'gst_amount': self.gst_amount,
            'total_amount': self.total_amount
        }

class Notification(db.Model):
    __tablename__ = 'notifications'
    
    id = Column(Integer, primary_key=True)
    user_type = Column(String(20), nullable=False)  # Admin, Customer, Driver
    user_id = Column(Integer, nullable=False)
    message = Column(String(255), nullable=False)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class DriverPayment(db.Model):
    __tablename__ = 'driver_payments'
    
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=False)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    amount = Column(Float, nullable=False)
    payment_mode = Column(Enum(PaymentMode), nullable=False)
    payment_date = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    driver = relationship("Driver", back_populates="payments")
    trip = relationship("Trip")

class TripLog(db.Model):
    __tablename__ = 'trip_logs'
    
    id = Column(Integer, primary_key=True)
    trip_id = Column(Integer, ForeignKey('trips.id'), nullable=False)
    admin_id = Column(Integer, ForeignKey('admins.id'), nullable=False)
    action = Column(String(100), nullable=False)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    trip = relationship("Trip")
    admin = relationship("Admin")

class TripPrice(db.Model):
    __tablename__ = 'trip_prices'
    
    id = Column(Integer, primary_key=True)
    route_type = Column(Enum(RouteType), nullable=False)
    trip_type = Column(Enum(TripType), nullable=False)
    duration_min = Column(Integer, nullable=False)  # Minutes
    duration_max = Column(Integer, nullable=False)  # Minutes  
    is_night = Column(Boolean, default=False)
    price_per_km = Column(Float, nullable=False)
    created_by_id = Column(Integer, ForeignKey('admins.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    created_by = relationship("Admin")

class DriverDocument(db.Model):
    __tablename__ = 'driver_documents'
    
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer, ForeignKey('drivers.id'), nullable=False)
    document_type = Column(String(50), nullable=False)  # License Front, License Back, Aadhaar Front, Aadhaar Back, Bank Document
    file_path = Column(String(255), nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey('admins.id'), nullable=False)
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    
    # Relationships
    driver = relationship("Driver")
    uploaded_by = relationship("Admin")


class FireDetail(db.Model):
    __tablename__ = 'fire_details'
    
    id = Column(Integer, primary_key=True)
    fire_id = Column(String(20), unique=True, nullable=False)
    location = Column(String(255), nullable=False)
    date_time = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False)  # Active, Contained, Extinguished
    severity = Column(String(50), nullable=False)  # Low, Medium, High, Critical
    description = Column(Text, nullable=True)
    reported_by_id = Column(Integer, ForeignKey('admins.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # Relationships
    reported_by = relationship("Admin")
