"""
Email service for sending contact form emails and notifications.
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app
from flask_mail import Mail, Message
from typing import Dict, Any

class EmailService:
    def __init__(self, app=None):
        self.mail = None
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize email service with Flask app"""
        # Configure Flask-Mail
        app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
        app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
        app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
        app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
        app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
        app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
        app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER', os.getenv('MAIL_USERNAME'))
        
        self.mail = Mail(app)
    
    def send_contact_form_email(self, form_data: Dict[str, Any]) -> bool:
        """
        Send contact form submission email
        
        Args:
            form_data: Dictionary containing name, email, subject, message
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Create email message
            msg = Message(
                subject=f"GrimmTrading Contact: {form_data.get('subject', 'No Subject')}",
                recipients=[os.getenv('CONTACT_EMAIL', 'grimmdaytrading@gmail.com')],
                reply_to=form_data.get('email')
            )
            
            # Create email body
            msg.body = f"""
New contact form submission from GrimmTrading website:

Name: {form_data.get('name', 'Not provided')}
Email: {form_data.get('email', 'Not provided')}
Subject: {form_data.get('subject', 'Not provided')}

Message:
{form_data.get('message', 'No message provided')}

---
This email was sent from the GrimmTrading contact form.
Reply directly to this email to respond to the user.
            """
            
            # Create HTML version
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2563eb; border-bottom: 2px solid #2563eb; padding-bottom: 10px;">
                        New Contact Form Submission
                    </h2>
                    
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1e40af;">Contact Details</h3>
                        <p><strong>Name:</strong> {form_data.get('name', 'Not provided')}</p>
                        <p><strong>Email:</strong> <a href="mailto:{form_data.get('email', '')}">{form_data.get('email', 'Not provided')}</a></p>
                        <p><strong>Subject:</strong> {form_data.get('subject', 'Not provided')}</p>
                    </div>
                    
                    <div style="background-color: #ffffff; padding: 20px; border: 1px solid #e5e7eb; border-radius: 8px;">
                        <h3 style="margin-top: 0; color: #1e40af;">Message</h3>
                        <p style="white-space: pre-wrap;">{form_data.get('message', 'No message provided')}</p>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 15px; background-color: #fef3c7; border-radius: 8px; border-left: 4px solid #f59e0b;">
                        <p style="margin: 0; font-size: 14px; color: #92400e;">
                            <strong>Note:</strong> This email was sent from the GrimmTrading contact form. 
                            Reply directly to this email to respond to the user.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Send email
            self.mail.send(msg)
            current_app.logger.info(f"Contact form email sent successfully from {form_data.get('email')}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send contact form email: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """
        Send welcome email to new users
        
        Args:
            user_email: User's email address
            user_name: User's name
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            msg = Message(
                subject="Welcome to GrimmTrading - Your Trading Journey Starts Now!",
                recipients=[user_email]
            )
            
            msg.html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <div style="text-align: center; margin-bottom: 30px;">
                        <h1 style="color: #2563eb; margin-bottom: 10px;">Welcome to GrimmTrading!</h1>
                        <p style="font-size: 18px; color: #6b7280;">Your professional day trading platform</p>
                    </div>
                    
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h2 style="color: #1e40af; margin-top: 0;">Hi {user_name},</h2>
                        <p>Thank you for joining GrimmTrading! You now have access to professional-grade trading tools and real-time market data.</p>
                    </div>
                    
                    <div style="margin: 20px 0;">
                        <h3 style="color: #1e40af;">What's Next?</h3>
                        <ul style="padding-left: 20px;">
                            <li>Explore our momentum scanners to find high-probability trades</li>
                            <li>Use our professional charts with real-time data</li>
                            <li>Join our trading community for insights and strategies</li>
                            <li>Check out our resources section for educational content</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://grimmtrading.com/dashboard" 
                           style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold;">
                            Access Your Dashboard
                        </a>
                    </div>
                    
                    <div style="margin-top: 30px; padding: 15px; background-color: #ecfdf5; border-radius: 8px; border-left: 4px solid #10b981;">
                        <p style="margin: 0; font-size: 14px; color: #065f46;">
                            <strong>Need Help?</strong> Visit our contact page or reply to this email if you have any questions.
                        </p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            self.mail.send(msg)
            current_app.logger.info(f"Welcome email sent successfully to {user_email}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Failed to send welcome email to {user_email}: {str(e)}")
            return False

# Create global email service instance
email_service = EmailService()

