"""
Payment routes for GrimmTrading Stripe integration
Handles subscription creation, management, and webhooks
"""

import os
import stripe
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from src.models.user import User
from src.models.subscription import Subscription, Payment
from src.services.stripe_service import StripeService
from src.database import db

payments_bp = Blueprint('payments', __name__)

@payments_bp.route('/pricing', methods=['GET'])
def get_pricing():
    """Get pricing information for all plans"""
    try:
        pricing = StripeService.get_pricing_info()
        return jsonify({
            'success': True,
            'pricing': pricing
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error getting pricing: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get pricing information'
        }), 500

@payments_bp.route('/create-checkout-session', methods=['POST'])
@jwt_required()
def create_checkout_session():
    """Create a Stripe checkout session for subscription"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        data = request.get_json()
        tier = data.get('tier')
        billing_interval = data.get('billing_interval')
        
        # Validate required fields
        if not tier or not billing_interval:
            return jsonify({
                'success': False,
                'error': 'tier and billing_interval are required'
            }), 400
        
        # Validate tier and billing interval
        pricing = StripeService.get_pricing_info()
        if tier not in pricing or billing_interval not in pricing[tier]:
            return jsonify({
                'success': False,
                'error': 'Invalid tier or billing interval'
            }), 400
        
        # Check if user already has an active subscription
        if user.subscription and user.subscription.is_active():
            return jsonify({
                'success': False,
                'error': 'User already has an active subscription'
            }), 400
        
        # Create checkout session
        success_url = data.get('success_url', f"{request.host_url}subscription/success")
        cancel_url = data.get('cancel_url', f"{request.host_url}pricing")
        
        session = StripeService.create_checkout_session(
            user=user,
            tier=tier,
            billing_interval=billing_interval,
            success_url=success_url,
            cancel_url=cancel_url
        )
        
        return jsonify({
            'success': True,
            'checkout_url': session.url,
            'session_id': session.id
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error creating checkout session: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@payments_bp.route('/subscription', methods=['GET'])
@jwt_required()
def get_subscription():
    """Get current user's subscription information"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        if not user.subscription:
            return jsonify({
                'success': True,
                'subscription': None,
                'user_tier': user.subscription_tier
            }), 200
        
        return jsonify({
            'success': True,
            'subscription': user.subscription.to_dict(),
            'user_tier': user.subscription_tier
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting subscription: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get subscription information'
        }), 500

@payments_bp.route('/subscription/cancel', methods=['POST'])
@jwt_required()
def cancel_subscription():
    """Cancel subscription at period end"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        result = StripeService.cancel_subscription(user)
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'cancel_at_period_end': result['cancel_at_period_end'],
            'current_period_end': result['current_period_end']
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error canceling subscription: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to cancel subscription'
        }), 500

@payments_bp.route('/subscription/reactivate', methods=['POST'])
@jwt_required()
def reactivate_subscription():
    """Reactivate a canceled subscription"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        result = StripeService.reactivate_subscription(user)
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'status': result['status']
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error reactivating subscription: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to reactivate subscription'
        }), 500

@payments_bp.route('/subscription/upgrade', methods=['POST'])
@jwt_required()
def upgrade_subscription():
    """Upgrade subscription immediately"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        data = request.get_json()
        new_tier = data.get('tier')
        new_billing_interval = data.get('billing_interval')
        
        if not new_tier or not new_billing_interval:
            return jsonify({
                'success': False,
                'error': 'tier and billing_interval are required'
            }), 400
        
        result = StripeService.upgrade_subscription(user, new_tier, new_billing_interval)
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'new_tier': result['new_tier'],
            'new_billing_interval': result['new_billing_interval'],
            'status': result['status']
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error upgrading subscription: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to upgrade subscription'
        }), 500

@payments_bp.route('/subscription/downgrade', methods=['POST'])
@jwt_required()
def downgrade_subscription():
    """Schedule subscription downgrade at period end"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        data = request.get_json()
        new_tier = data.get('tier')
        new_billing_interval = data.get('billing_interval')
        
        if not new_tier or not new_billing_interval:
            return jsonify({
                'success': False,
                'error': 'tier and billing_interval are required'
            }), 400
        
        result = StripeService.downgrade_subscription(user, new_tier, new_billing_interval)
        
        return jsonify({
            'success': True,
            'message': result['message'],
            'new_tier': result['new_tier'],
            'new_billing_interval': result['new_billing_interval'],
            'effective_date': result['effective_date']
        }), 200
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error scheduling downgrade: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to schedule downgrade'
        }), 500

@payments_bp.route('/billing-portal', methods=['POST'])
@jwt_required()
def create_billing_portal_session():
    """Create a Stripe billing portal session"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        if not user.subscription or not user.subscription.stripe_customer_id:
            return jsonify({
                'success': False,
                'error': 'User does not have an active subscription'
            }), 400
        
        data = request.get_json()
        return_url = data.get('return_url', f"{request.host_url}subscription")
        
        session = StripeService.create_billing_portal_session(
            customer_id=user.subscription.stripe_customer_id,
            return_url=return_url
        )
        
        return jsonify({
            'success': True,
            'portal_url': session.url
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error creating billing portal session: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to create billing portal session'
        }), 500

@payments_bp.route('/payments', methods=['GET'])
@jwt_required()
def get_payment_history():
    """Get user's payment history"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'User not found'
            }), 404
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 10, type=int), 100)
        
        # Query payments
        payments_query = Payment.query.filter_by(user_id=user.id).order_by(Payment.created_at.desc())
        payments_paginated = payments_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        return jsonify({
            'success': True,
            'payments': [payment.to_dict() for payment in payments_paginated.items],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': payments_paginated.total,
                'pages': payments_paginated.pages,
                'has_next': payments_paginated.has_next,
                'has_prev': payments_paginated.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting payment history: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get payment history'
        }), 500

@payments_bp.route('/webhook', methods=['POST'])
def stripe_webhook():
    """Handle Stripe webhook events"""
    try:
        payload = request.get_data()
        signature = request.headers.get('Stripe-Signature')
        
        if not signature:
            current_app.logger.error("Missing Stripe signature")
            return jsonify({'error': 'Missing signature'}), 400
        
        webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')
        if not webhook_secret:
            current_app.logger.error("Missing webhook secret")
            return jsonify({'error': 'Webhook not configured'}), 500
        
        try:
            # Verify webhook signature
            event = stripe.Webhook.construct_event(
                payload, signature, webhook_secret
            )
        except stripe.error.SignatureVerificationError:
            current_app.logger.error("Invalid webhook signature")
            return jsonify({'error': 'Invalid signature'}), 400
        
        # Handle the event
        event_type = event['type']
        event_data = event['data']['object']
        
        current_app.logger.info(f"Processing webhook: {event_type}")
        
        result = StripeService.handle_webhook_event(event_type, event_data)
        
        return jsonify({
            'success': True,
            'result': result
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Webhook error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Webhook processing failed'
        }), 500

# Admin routes for payment management
@payments_bp.route('/admin/subscriptions', methods=['GET'])
@jwt_required()
def admin_get_subscriptions():
    """Admin: Get all subscriptions with pagination"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_admin:
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Query subscriptions with user data
        subscriptions_query = db.session.query(Subscription).join(User).order_by(Subscription.created_at.desc())
        subscriptions_paginated = subscriptions_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        subscriptions_data = []
        for subscription in subscriptions_paginated.items:
            sub_dict = subscription.to_dict()
            sub_dict['user'] = {
                'id': str(subscription.user.id),
                'username': subscription.user.username,
                'email': subscription.user.email,
                'first_name': subscription.user.first_name,
                'last_name': subscription.user.last_name
            }
            subscriptions_data.append(sub_dict)
        
        return jsonify({
            'success': True,
            'subscriptions': subscriptions_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': subscriptions_paginated.total,
                'pages': subscriptions_paginated.pages,
                'has_next': subscriptions_paginated.has_next,
                'has_prev': subscriptions_paginated.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting admin subscriptions: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get subscriptions'
        }), 500

@payments_bp.route('/admin/payments', methods=['GET'])
@jwt_required()
def admin_get_payments():
    """Admin: Get all payments with pagination"""
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user or not user.is_admin:
            return jsonify({
                'success': False,
                'error': 'Admin access required'
            }), 403
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = min(request.args.get('per_page', 20, type=int), 100)
        
        # Query payments with user data
        payments_query = db.session.query(Payment).join(User).order_by(Payment.created_at.desc())
        payments_paginated = payments_query.paginate(
            page=page, 
            per_page=per_page, 
            error_out=False
        )
        
        payments_data = []
        for payment in payments_paginated.items:
            payment_dict = payment.to_dict()
            payment_dict['user'] = {
                'id': str(payment.user.id),
                'username': payment.user.username,
                'email': payment.user.email,
                'first_name': payment.user.first_name,
                'last_name': payment.user.last_name
            }
            payments_data.append(payment_dict)
        
        return jsonify({
            'success': True,
            'payments': payments_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': payments_paginated.total,
                'pages': payments_paginated.pages,
                'has_next': payments_paginated.has_next,
                'has_prev': payments_paginated.has_prev
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting admin payments: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Failed to get payments'
        }), 500

