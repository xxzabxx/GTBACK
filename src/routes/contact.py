"""
Contact form routes for handling email submissions.
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.services.email_service import email_service
import logging

contact_bp = Blueprint('contact', __name__)

@contact_bp.route('/contact', methods=['POST'])
def submit_contact_form():
    """
    Handle contact form submission
    
    Expected JSON payload:
    {
        "name": "User Name",
        "email": "user@example.com", 
        "subject": "Subject line",
        "message": "Message content"
    }
    """
    try:
        # Get form data from request
        data = request.get_json()
        
        # Validate required fields
        required_fields = ['name', 'email', 'subject', 'message']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Validate email format (basic validation)
        email = data.get('email', '').strip()
        if '@' not in email or '.' not in email:
            return jsonify({
                'success': False,
                'error': 'Invalid email format'
            }), 400
        
        # Prepare form data
        form_data = {
            'name': data.get('name', '').strip(),
            'email': email,
            'subject': data.get('subject', '').strip(),
            'message': data.get('message', '').strip()
        }
        
        # Send email
        email_sent = email_service.send_contact_form_email(form_data)
        
        if email_sent:
            logging.info(f"Contact form submitted successfully by {form_data['email']}")
            return jsonify({
                'success': True,
                'message': 'Your message has been sent successfully. We\'ll get back to you soon!'
            }), 200
        else:
            logging.error(f"Failed to send contact form email from {form_data['email']}")
            return jsonify({
                'success': False,
                'error': 'Failed to send email. Please try again later.'
            }), 500
            
    except Exception as e:
        logging.error(f"Contact form submission error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'An unexpected error occurred. Please try again later.'
        }), 500

@contact_bp.route('/contact/test', methods=['GET'])
@jwt_required()
def test_email_service():
    """
    Test endpoint to verify email service is working (admin only)
    """
    try:
        # Get current user
        current_user_id = get_jwt_identity()
        
        # Test email data
        test_data = {
            'name': 'Test User',
            'email': 'test@example.com',
            'subject': 'Email Service Test',
            'message': 'This is a test message to verify the email service is working correctly.'
        }
        
        # Send test email
        email_sent = email_service.send_contact_form_email(test_data)
        
        if email_sent:
            return jsonify({
                'success': True,
                'message': 'Test email sent successfully'
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': 'Failed to send test email'
            }), 500
            
    except Exception as e:
        logging.error(f"Email service test error: {str(e)}")
        return jsonify({
            'success': False,
            'error': f'Email service test failed: {str(e)}'
        }), 500

