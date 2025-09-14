"""
Stripe service for handling payments and subscriptions
"""
import stripe
import os
from datetime import datetime, timezone
from flask import current_app
from src.models.user import User
from src.models.subscription import Subscription, Payment, BillingAddress, SubscriptionStatus, BillingInterval
from src.database import db

# Initialize Stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

class StripeService:
    """Service for handling Stripe operations"""
    
    # Stripe Price IDs mapping (from your Stripe dashboard)
    PRICE_IDS = {
        'basic_monthly': 'price_basic_monthly',  # Replace with actual Stripe price IDs
        'basic_quarterly': 'price_basic_quarterly',
        'basic_yearly': 'price_basic_yearly',
        'pro_monthly': 'price_pro_monthly',
        'pro_quarterly': 'price_pro_quarterly', 
        'pro_yearly': 'price_pro_yearly',
        'premium_monthly': 'price_premium_monthly',
        'premium_quarterly': 'price_premium_quarterly',
        'premium_yearly': 'price_premium_yearly'
    }
    
    # Pricing mapping (from your Stripe products)
    PRICING = {
        'basic': {
            'monthly': {'amount': 29.00, 'price_id': 'price_basic_monthly'},
            'quarterly': {'amount': 72.21, 'price_id': 'price_basic_quarterly'},
            'yearly': {'amount': 278.40, 'price_id': 'price_basic_yearly'}
        },
        'pro': {
            'monthly': {'amount': 59.00, 'price_id': 'price_pro_monthly'},
            'quarterly': {'amount': 146.91, 'price_id': 'price_pro_quarterly'},
            'yearly': {'amount': 566.40, 'price_id': 'price_pro_yearly'}
        },
        'premium': {
            'monthly': {'amount': 99.00, 'price_id': 'price_premium_monthly'},
            'quarterly': {'amount': 246.51, 'price_id': 'price_premium_quarterly'},
            'yearly': {'amount': 950.40, 'price_id': 'price_premium_yearly'}
        }
    }
    
    @staticmethod
    def create_customer(user):
        """Create a Stripe customer for the user"""
        try:
            customer = stripe.Customer.create(
                email=user.email,
                name=f"{user.first_name} {user.last_name}".strip(),
                metadata={
                    'user_id': str(user.id),
                    'username': user.username
                }
            )
            return customer
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error creating Stripe customer: {e}")
            raise
    
    @staticmethod
    def create_checkout_session(user, tier, billing_interval, success_url, cancel_url):
        """Create a Stripe checkout session for subscription"""
        try:
            # Get or create Stripe customer
            if user.subscription and user.subscription.stripe_customer_id:
                customer_id = user.subscription.stripe_customer_id
            else:
                customer = StripeService.create_customer(user)
                customer_id = customer.id
            
            # Get price ID for the tier and billing interval
            pricing_info = StripeService.PRICING.get(tier, {}).get(billing_interval)
            if not pricing_info:
                raise ValueError(f"Invalid tier or billing interval: {tier}, {billing_interval}")
            
            price_id = pricing_info['price_id']
            
            # Create checkout session
            session = stripe.checkout.Session.create(
                customer=customer_id,
                payment_method_types=['card'],
                line_items=[{
                    'price': price_id,
                    'quantity': 1,
                }],
                mode='subscription',
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    'user_id': str(user.id),
                    'tier': tier,
                    'billing_interval': billing_interval
                },
                allow_promotion_codes=True,
                billing_address_collection='required',
                customer_update={
                    'address': 'auto',
                    'name': 'auto'
                }
            )
            
            return session
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error creating checkout session: {e}")
            raise
    
    @staticmethod
    def create_billing_portal_session(customer_id, return_url):
        """Create a Stripe billing portal session for subscription management"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return session
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error creating billing portal session: {e}")
            raise
    
    @staticmethod
    def handle_subscription_created(stripe_subscription):
        """Handle subscription.created webhook"""
        try:
            user_id = stripe_subscription.metadata.get('user_id')
            if not user_id:
                current_app.logger.error("No user_id in subscription metadata")
                return
            
            user = User.query.get(user_id)
            if not user:
                current_app.logger.error(f"User not found: {user_id}")
                return
            
            # Extract tier and billing interval from price
            price = stripe.Price.retrieve(stripe_subscription.items.data[0].price.id)
            tier, billing_interval = StripeService._extract_tier_from_price(price)
            
            # Create or update subscription
            subscription = user.subscription
            if not subscription:
                subscription = Subscription(user_id=user.id)
                db.session.add(subscription)
            
            subscription.stripe_subscription_id = stripe_subscription.id
            subscription.stripe_customer_id = stripe_subscription.customer
            subscription.stripe_price_id = price.id
            subscription.tier = tier
            subscription.status = SubscriptionStatus(stripe_subscription.status)
            subscription.billing_interval = billing_interval
            subscription.amount = price.unit_amount / 100  # Convert from cents
            subscription.currency = price.currency.upper()
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            )
            
            # Update user tier
            user.subscription_tier = tier
            user.subscription_expires = subscription.current_period_end
            
            db.session.commit()
            current_app.logger.info(f"Subscription created for user {user.username}")
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription created: {e}")
            db.session.rollback()
    
    @staticmethod
    def handle_subscription_updated(stripe_subscription):
        """Handle subscription.updated webhook"""
        try:
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=stripe_subscription.id
            ).first()
            
            if not subscription:
                current_app.logger.error(f"Subscription not found: {stripe_subscription.id}")
                return
            
            # Update subscription status and dates
            subscription.status = SubscriptionStatus(stripe_subscription.status)
            subscription.current_period_start = datetime.fromtimestamp(
                stripe_subscription.current_period_start, tz=timezone.utc
            )
            subscription.current_period_end = datetime.fromtimestamp(
                stripe_subscription.current_period_end, tz=timezone.utc
            )
            
            if stripe_subscription.canceled_at:
                subscription.canceled_at = datetime.fromtimestamp(
                    stripe_subscription.canceled_at, tz=timezone.utc
                )
            
            if stripe_subscription.ended_at:
                subscription.ended_at = datetime.fromtimestamp(
                    stripe_subscription.ended_at, tz=timezone.utc
                )
            
            # Update user subscription expiry
            subscription.user.subscription_expires = subscription.current_period_end
            
            db.session.commit()
            current_app.logger.info(f"Subscription updated for user {subscription.user.username}")
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription updated: {e}")
            db.session.rollback()
    
    @staticmethod
    def handle_subscription_deleted(stripe_subscription):
        """Handle subscription.deleted webhook"""
        try:
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=stripe_subscription.id
            ).first()
            
            if not subscription:
                current_app.logger.error(f"Subscription not found: {stripe_subscription.id}")
                return
            
            # Update subscription status
            subscription.status = SubscriptionStatus.CANCELED
            subscription.ended_at = datetime.now(timezone.utc)
            
            # Downgrade user to free tier
            subscription.user.subscription_tier = 'free'
            subscription.user.subscription_expires = None
            
            db.session.commit()
            current_app.logger.info(f"Subscription canceled for user {subscription.user.username}")
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription deleted: {e}")
            db.session.rollback()
    
    @staticmethod
    def handle_payment_succeeded(stripe_payment_intent):
        """Handle payment_intent.succeeded webhook"""
        try:
            # Get invoice if this is a subscription payment
            invoice = None
            if stripe_payment_intent.invoice:
                invoice = stripe.Invoice.retrieve(stripe_payment_intent.invoice)
            
            # Find user by customer ID
            customer_id = stripe_payment_intent.customer
            subscription = Subscription.query.filter_by(
                stripe_customer_id=customer_id
            ).first()
            
            if not subscription:
                current_app.logger.error(f"Subscription not found for customer: {customer_id}")
                return
            
            # Create payment record
            payment = Payment(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                stripe_payment_intent_id=stripe_payment_intent.id,
                stripe_invoice_id=invoice.id if invoice else None,
                amount=stripe_payment_intent.amount / 100,  # Convert from cents
                currency=stripe_payment_intent.currency.upper(),
                status='succeeded',
                description=f"Payment for {subscription.tier} subscription",
                payment_method=stripe_payment_intent.payment_method_types[0] if stripe_payment_intent.payment_method_types else None,
                receipt_url=stripe_payment_intent.charges.data[0].receipt_url if stripe_payment_intent.charges.data else None,
                paid_at=datetime.fromtimestamp(stripe_payment_intent.created, tz=timezone.utc)
            )
            
            db.session.add(payment)
            db.session.commit()
            current_app.logger.info(f"Payment recorded for user {subscription.user.username}")
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment succeeded: {e}")
            db.session.rollback()
    
    @staticmethod
    def _extract_tier_from_price(price):
        """Extract tier and billing interval from Stripe price object"""
        # This would need to be customized based on your actual Stripe price IDs
        # For now, we'll use a simple mapping
        price_id = price.id
        
        if 'basic' in price_id:
            tier = 'basic'
        elif 'pro' in price_id:
            tier = 'pro'
        elif 'premium' in price_id:
            tier = 'premium'
        else:
            tier = 'basic'  # Default
        
        if 'yearly' in price_id or price.recurring.interval == 'year':
            billing_interval = BillingInterval.YEARLY
        elif 'quarterly' in price_id or (price.recurring.interval == 'month' and price.recurring.interval_count == 3):
            billing_interval = BillingInterval.QUARTERLY
        else:
            billing_interval = BillingInterval.MONTHLY
        
        return tier, billing_interval
    
    @staticmethod
    def cancel_subscription(user):
        """Cancel subscription at period end"""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise ValueError("User does not have an active subscription")
            
            # Cancel at period end
            subscription = stripe.Subscription.modify(
                user.subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Update local subscription
            user.subscription.update_from_stripe(subscription)
            
            return {
                'message': 'Subscription will be canceled at the end of the current billing period',
                'cancel_at_period_end': subscription.cancel_at_period_end,
                'current_period_end': subscription.current_period_end
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error canceling subscription: {e}")
            raise
    
    @staticmethod
    def reactivate_subscription(user):
        """Reactivate a canceled subscription"""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise ValueError("User does not have a subscription")
            
            # Reactivate subscription
            subscription = stripe.Subscription.modify(
                user.subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            # Update local subscription
            user.subscription.update_from_stripe(subscription)
            
            return {
                'message': 'Subscription reactivated successfully',
                'status': subscription.status
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error reactivating subscription: {e}")
            raise
    
    @staticmethod
    def upgrade_subscription(user, new_tier, new_billing_interval):
        """Upgrade subscription immediately"""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise ValueError("User does not have an active subscription")
            
            # Validate new plan
            pricing_info = StripeService.PRICING.get(new_tier, {}).get(new_billing_interval)
            if not pricing_info:
                raise ValueError(f"Invalid tier or billing interval: {new_tier}, {new_billing_interval}")
            
            new_price_id = pricing_info['price_id']
            
            # Get current subscription
            stripe_subscription = stripe.Subscription.retrieve(user.subscription.stripe_subscription_id)
            
            # Update subscription with new price
            updated_subscription = stripe.Subscription.modify(
                user.subscription.stripe_subscription_id,
                items=[{
                    'id': stripe_subscription['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='always_invoice',  # Immediate upgrade with prorated billing
                metadata={
                    'user_id': str(user.id),
                    'tier': new_tier,
                    'billing_interval': new_billing_interval
                }
            )
            
            # Update local subscription
            user.subscription.update_from_stripe(updated_subscription)
            
            # Update user tier immediately
            user.subscription_tier = new_tier
            user.subscription_expires = user.subscription.current_period_end
            db.session.commit()
            
            return {
                'message': f'Subscription upgraded to {new_tier} successfully',
                'new_tier': new_tier,
                'new_billing_interval': new_billing_interval,
                'status': updated_subscription.status
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error upgrading subscription: {e}")
            raise
    
    @staticmethod
    def downgrade_subscription(user, new_tier, new_billing_interval):
        """Schedule subscription downgrade at period end"""
        try:
            if not user.subscription or not user.subscription.stripe_subscription_id:
                raise ValueError("User does not have an active subscription")
            
            # Validate new plan
            pricing_info = StripeService.PRICING.get(new_tier, {}).get(new_billing_interval)
            if not pricing_info:
                raise ValueError(f"Invalid tier or billing interval: {new_tier}, {new_billing_interval}")
            
            new_price_id = pricing_info['price_id']
            
            # Schedule the change for the end of the current period
            stripe.Subscription.modify(
                user.subscription.stripe_subscription_id,
                items=[{
                    'id': stripe.Subscription.retrieve(user.subscription.stripe_subscription_id)['items']['data'][0].id,
                    'price': new_price_id,
                }],
                proration_behavior='none',  # No immediate charge, change at period end
                metadata={
                    'user_id': str(user.id),
                    'tier': new_tier,
                    'billing_interval': new_billing_interval,
                    'scheduled_downgrade': 'true'
                }
            )
            
            return {
                'message': f'Subscription will be downgraded to {new_tier} at the end of the current billing period',
                'new_tier': new_tier,
                'new_billing_interval': new_billing_interval,
                'effective_date': user.subscription.current_period_end.isoformat()
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Error scheduling downgrade: {e}")
            raise
    
    @staticmethod
    def handle_webhook_event(event_type, event_data):
        """Handle Stripe webhook events"""
        try:
            if event_type == 'customer.subscription.created':
                return StripeService.handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                return StripeService.handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return StripeService.handle_subscription_deleted(event_data)
            elif event_type == 'invoice.payment_succeeded':
                return StripeService.handle_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                return StripeService.handle_payment_failed(event_data)
            else:
                current_app.logger.info(f"Unhandled webhook event type: {event_type}")
                return {'status': 'ignored', 'event_type': event_type}
                
        except Exception as e:
            current_app.logger.error(f"Webhook processing failed: {str(e)}")
            raise
    
    @staticmethod
    def handle_payment_failed(stripe_invoice):
        """Handle invoice.payment_failed webhook"""
        try:
            subscription_id = stripe_invoice.get('subscription')
            if not subscription_id:
                return {'status': 'no_subscription'}
            
            subscription = Subscription.query.filter_by(
                stripe_subscription_id=subscription_id
            ).first()
            
            if not subscription:
                current_app.logger.error(f"Subscription not found: {subscription_id}")
                return {'status': 'subscription_not_found'}
            
            # Create failed payment record
            payment = Payment(
                user_id=subscription.user_id,
                subscription_id=subscription.id,
                stripe_invoice_id=stripe_invoice.id,
                amount=stripe_invoice.amount_due / 100,  # Convert from cents
                currency=stripe_invoice.currency.upper(),
                status='failed',
                description=f"Failed payment for {subscription.tier} subscription",
                failure_reason="Payment failed",
                paid_at=None
            )
            
            db.session.add(payment)
            db.session.commit()
            current_app.logger.info(f"Failed payment recorded for user {subscription.user.username}")
            
            return {'status': 'payment_failed_recorded', 'user_id': str(subscription.user_id)}
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment failed: {e}")
            db.session.rollback()
            return {'status': 'error', 'error': str(e)}

    @staticmethod
    def get_pricing_info():
        """Get all pricing information"""
        return StripeService.PRICING

