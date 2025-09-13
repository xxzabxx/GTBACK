"""
Email service for handling contact forms and user communications.
Supports SendGrid API for reliable cloud-based email delivery.
"""
import os
import logging
from typing import Dict, Any, Optional
from flask import current_app

class EmailService:
    def __init__(self):
        self.sendgrid_client = None
        
    def init_app(self, app):
        """Initialize email service with Flask app"""
        # Initialize SendGrid if API key is available
        sendgrid_api_key = os.getenv('SENDGRID_API_KEY')
        if sendgrid_api_key:
            try:
                from sendgrid import SendGridAPIClient
                self.sendgrid_client = SendGridAPIClient(api_key=sendgrid_api_key)
                logging.info("SendGrid client initialized successfully")
            except Exception as e:
                logging.warning(f"Failed to initialize SendGrid: {str(e)}")
        else:
            logging.warning("SENDGRID_API_KEY not found in environment variables")
    
    def send_contact_form_email(self, form_data: Dict[str, Any]) -> bool:
        """
        Send contact form submission email using SendGrid
        
        Args:
            form_data: Dictionary containing name, email, subject, message
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            if not self.sendgrid_client:
                current_app.logger.error("SendGrid client not initialized")
                return self._log_form_submission(form_data)
            
            return self._send_via_sendgrid(form_data)
            
        except Exception as e:
            current_app.logger.error(f"Email service failed: {str(e)}")
            return self._log_form_submission(form_data)
    
    def _send_via_sendgrid(self, form_data: Dict[str, Any]) -> bool:
        """Send email using SendGrid API"""
        try:
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            # Create email
            from_email = Email(os.getenv('MAIL_USERNAME', 'grimmdaytrading@gmail.com'))
            to_email = To(os.getenv('CONTACT_EMAIL', 'grimmdaytrading@gmail.com'))
            subject = f"GrimmTrading Contact: {form_data.get('subject', 'No Subject')}"
            
            # Create HTML content
            html_content = f"""
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
            
            content = Content("text/html", html_content)
            mail = Mail(from_email, to_email, subject, content)
            
            # Set reply-to
            mail.reply_to = Email(form_data.get('email', ''))
            
            # Send email
            response = self.sendgrid_client.send(mail)
            
            if response.status_code in [200, 201, 202]:
                current_app.logger.info(f"Contact form email sent via SendGrid from {form_data.get('email')}")
                return True
            else:
                current_app.logger.error(f"SendGrid failed with status {response.status_code}: {response.body}")
                return self._log_form_submission(form_data)
                
        except Exception as e:
            current_app.logger.error(f"SendGrid email failed: {str(e)}")
            return self._log_form_submission(form_data)
    
    def _log_form_submission(self, form_data: Dict[str, Any]) -> bool:
        """
        Log form submission when email fails (backup method)
        """
        try:
            current_app.logger.error(f"""
CONTACT FORM SUBMISSION (EMAIL FAILED):
=====================================
Name: {form_data.get('name', 'Not provided')}
Email: {form_data.get('email', 'Not provided')}
Subject: {form_data.get('subject', 'Not provided')}
Message: {form_data.get('message', 'No message provided')}
=====================================
            """)
            
            # In a production environment, you might want to save this to a database
            # or send to a monitoring service like Sentry
            
            return False  # Return False since email wasn't actually sent
            
        except Exception as e:
            current_app.logger.error(f"Failed to log form submission: {str(e)}")
            return False
    
    def send_welcome_email(self, user_email: str, user_name: str) -> bool:
        """
        Send welcome email to new users
        
        Args:
            user_email: User's email address
            user_name: User's display name
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            if not self.sendgrid_client:
                current_app.logger.error("SendGrid client not initialized for welcome email")
                return False
            
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            # Create email
            from_email = Email(os.getenv('MAIL_USERNAME', 'grimmdaytrading@gmail.com'))
            to_email = To(user_email)
            subject = "Welcome to GrimmTrading - Your Trading Journey Starts Now!"
            
            # Create HTML content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h1 style="color: #2563eb; text-align: center;">Welcome to GrimmTrading!</h1>
                    
                    <p>Hi {user_name},</p>
                    
                    <p>Welcome to GrimmTrading - the professional momentum trading platform trusted by thousands of day traders worldwide.</p>
                    
                    <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <h3 style="margin-top: 0; color: #1e40af;">What's Next?</h3>
                        <ul>
                            <li>Explore our momentum scanners to find high-probability setups</li>
                            <li>Use our professional TradingView charts for technical analysis</li>
                            <li>Join our trading community for real-time market discussions</li>
                            <li>Check out our resources section for educational content</li>
                        </ul>
                    </div>
                    
                    <div style="text-align: center; margin: 30px 0;">
                        <a href="https://grimmtrading.com/dashboard" 
                           style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block;">
                            Access Your Dashboard
                        </a>
                    </div>
                    
                    <p>If you have any questions, don't hesitate to reach out through our contact form.</p>
                    
                    <p>Happy Trading!<br>
                    The GrimmTrading Team</p>
                </div>
            </body>
            </html>
            """
            
            content = Content("text/html", html_content)
            mail = Mail(from_email, to_email, subject, content)
            
            # Send email
            response = self.sendgrid_client.send(mail)
            
            if response.status_code in [200, 201, 202]:
                current_app.logger.info(f"Welcome email sent to {user_email}")
                return True
            else:
                current_app.logger.error(f"Welcome email failed with status {response.status_code}")
                return False
                
        except Exception as e:
            current_app.logger.error(f"Welcome email failed: {str(e)}")
            return False

# Create singleton instance
email_service = EmailService()

