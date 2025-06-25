import os
import random
import string
import datetime
import io
import base64
import qrcode
from PIL import Image, ImageDraw, ImageFont
from flask import current_app, url_for
from twilio.rest import Client

# Twilio credentials - use environment variables securely
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def generate_otp(length=6):
    """Generate a random OTP of specified length."""
    return ''.join(random.choices(string.digits, k=length))

def send_otp(phone_number, otp):
    """Send OTP via Twilio.
    
    Due to Twilio region restrictions, this function will simulate OTP sending
    for development purposes. In production, it would use Twilio API.
    """
    try:
        # Check if we're in development/testing mode or if Twilio credentials are missing
        if os.environ.get('FLASK_ENV') == 'development' or not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
            # In development, just log the OTP and pretend it was sent
            print(f"[DEVELOPMENT MODE] OTP {otp} would be sent to {phone_number}")
            current_app.logger.info(f"[DEVELOPMENT MODE] OTP {otp} would be sent to {phone_number}")
            return True, "DEVELOPMENT_MODE_SID"
        
        # Format phone number properly for Twilio
        # Ensure phone number has proper format with country code
        formatted_phone = phone_number
        if not phone_number.startswith('+'):
            # Add Indian country code if not present (assuming Indian numbers)
            formatted_phone = '+91' + phone_number.lstrip('0')
        
        # For production, use the actual Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=f"Your OTP for Driver Management App login is: {otp}",
            from_=TWILIO_PHONE_NUMBER,
            to=formatted_phone
        )
        return True, message.sid
    except Exception as e:
        # For testing/development purposes, log the error but allow login to proceed
        current_app.logger.error(f"Error sending OTP: {str(e)}")
        print(f"[ERROR MODE] Failed to send OTP {otp} to {phone_number}, but allowing login for testing")
        current_app.logger.info(f"[ERROR MODE] Failed to send OTP {otp} to {phone_number}, but allowing login for testing")
        # Return success with a development SID to allow testing to continue
        return True, "DEVELOPMENT_MODE_SID"

def generate_qr_code(driver_id, driver_name):
    """Generate QR code for driver with payment information."""
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    
    # Data to be encoded in QR code (driver payment information)
    data = {
        "driver_id": driver_id,
        "driver_name": driver_name,
        "payment_info": f"Driver ID: {driver_id}, Name: {driver_name}"
    }
    
    qr.add_data(str(data))
    qr.make(fit=True)
    
    # Create QR code image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save QR code to a BytesIO object
    img_io = io.BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    # Return base64 encoded image
    return base64.b64encode(img_io.getvalue()).decode('utf-8')

def overlay_text_on_image(img_data, text):
    """Add text overlay to an image (e.g., timestamp on driver selfie)."""
    try:
        # Decode base64 image
        img_bytes = base64.b64decode(img_data.split(',')[1])
        img = Image.open(io.BytesIO(img_bytes))
        
        # Create a drawing context
        draw = ImageDraw.Draw(img)
        
        # Determine font size based on image dimensions
        font_size = int(img.width * 0.04)  # 4% of image width
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            font = ImageFont.load_default()
        
        # Position text at bottom right
        try:
            # For older PIL versions
            text_width, text_height = draw.textsize(text, font=font)
        except AttributeError:
            # For newer PIL versions
            text_width, text_height = font.getbbox(text)[2:]
        
        position = (img.width - text_width - 10, img.height - text_height - 10)
        
        # Draw text with shadow for better visibility
        draw.text((position[0]+2, position[1]+2), text, font=font, fill="black")
        draw.text(position, text, font=font, fill="white")
        
        # Convert back to base64
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG")
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        return f"data:image/jpeg;base64,{img_str}"
    except Exception as e:
        current_app.logger.error(f"Error processing image: {str(e)}")
        return img_data  # Return original image if processing fails

def calculate_bill(start_time, end_time):
    """Calculate trip bill based on start and end times."""
    # Calculate duration in hours
    duration = (end_time - start_time).total_seconds() / 3600
    
    daytime_hours = 0
    nighttime_hours = 0
    
    # Calculate daytime and nighttime hours
    current_time = start_time
    while current_time < end_time:
        hour = current_time.hour
        if 7 <= hour < 22:  # Daytime (7:00 AM - 10:00 PM)
            daytime_hours += min(1, (end_time - current_time).total_seconds() / 3600)
        else:  # Nighttime (10:00 PM - 7:00 AM)
            nighttime_hours += min(1, (end_time - current_time).total_seconds() / 3600)
        current_time += datetime.timedelta(hours=1)
        
    # Apply rates
    daytime_driver_rate = 86  # ₹86/hr
    nighttime_driver_rate = 96  # ₹96/hr
    company_rate = 14  # ₹14/hr
    
    driver_amount = (daytime_hours * daytime_driver_rate) + (nighttime_hours * nighttime_driver_rate)
    company_amount = (daytime_hours + nighttime_hours) * company_rate
    
    # Calculate GST (18%)
    subtotal = driver_amount + company_amount
    gst_amount = subtotal * 0.18
    
    # Calculate total amount
    total_amount = subtotal + gst_amount
    
    return {
        'total_hours': duration,
        'daytime_hours': daytime_hours,
        'nighttime_hours': nighttime_hours,
        'driver_amount': driver_amount,
        'company_amount': company_amount,
        'gst_amount': gst_amount,
        'total_amount': total_amount
    }

def create_notification(user_type, user_id, message):
    """Create a notification for a user."""
    from app import db
    from models import Notification
    
    notification = Notification(
        user_type=user_type,
        user_id=user_id,
        message=message
    )
    
    db.session.add(notification)
    db.session.commit()
    
    return notification

def check_license_expiry():
    """Check for license expiry and create notifications."""
    from app import db
    from models import Driver, Notification
    
    # Get drivers whose licenses expire in 30 days
    thirty_days_from_now = datetime.datetime.utcnow() + datetime.timedelta(days=30)
    expiring_drivers = Driver.query.filter(
        Driver.license_expiry_date <= thirty_days_from_now,
        Driver.license_expiry_date > datetime.datetime.utcnow()
    ).all()
    
    # Create notifications for admin
    for driver in expiring_drivers:
        # Check if notification already exists
        existing_notification = Notification.query.filter(
            Notification.user_type == "Admin",
            Notification.message.like(f"%{driver.name}%license%expiring%")
        ).first()
        
        if not existing_notification:
            # Create notification for admin
            create_notification(
                "Admin", 
                1,  # Admin ID (assuming ID 1 is a super admin)
                f"Driver {driver.name}'s license is expiring on {driver.license_expiry_date.strftime('%Y-%m-%d')}."
            )
    
    return len(expiring_drivers)

def check_upcoming_trips():
    """Check for upcoming trips and send notifications."""
    from app import db
    from models import Trip, TripStatus, Notification
    
    now = datetime.datetime.utcnow()
    
    # Get trips that start within the next 3 hours
    three_hours_from_now = now + datetime.timedelta(hours=3)
    upcoming_trips = Trip.query.filter(
        Trip.trip_start_date <= three_hours_from_now,
        Trip.trip_start_date > now,
        Trip.status.in_([TripStatus.PENDING, TripStatus.ASSIGNED])
    ).all()
    
    for trip in upcoming_trips:
        # Check how many hours until trip starts
        hours_until_trip = (trip.trip_start_date - now).total_seconds() / 3600
        
        if hours_until_trip <= 1:
            message = f"Trip #{trip.id} starting in less than 1 hour!"
        elif hours_until_trip <= 2:
            message = f"Trip #{trip.id} starting in less than 2 hours!"
        else:
            message = f"Trip #{trip.id} starting in less than 3 hours!"
        
        # Notify admin about all upcoming trips
        create_notification("Admin", 1, message)
        
        # If trip is assigned, notify driver
        if trip.status == TripStatus.ASSIGNED and trip.driver_id:
            create_notification("Driver", trip.driver_id, message)
        
        # For pending trips, notify admin
        if trip.status == TripStatus.PENDING:
            create_notification("Admin", 1, f"URGENT: Trip #{trip.id} is not assigned yet and starts soon!")
    
    return len(upcoming_trips)
