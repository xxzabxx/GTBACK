"""
Subscription and billing models for GrimmTrading platform
"""
from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text, ForeignKey, Numeric, Enum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from src.database import db
import enum

class SubscriptionStatus(enum.Enum):
    ACTIVE = "active"
    CANCELED = "canceled" 
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"

class BillingInterval(enum.Enum):
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"  # 3 months
    YEARLY = "yearly"

class Subscription(db.Model):
    """User subscription model"""
    __tablename__ = 'subscriptions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Stripe identifiers
    stripe_subscription_id = Column(String(255), unique=True, nullable=True)
    stripe_customer_id = Column(String(255), nullable=True)
    stripe_price_id = Column(String(255), nullable=True)
    
    # Subscription details
    tier = Column(String(20), nullable=False, default='free')  # free, basic, pro, premium
    status = Column(Enum(SubscriptionStatus), nullable=False, default=SubscriptionStatus.ACTIVE)
    billing_interval = Column(Enum(BillingInterval), nullable=True)
    
    # Pricing
    amount = Column(Numeric(10, 2), nullable=True)  # Amount in USD
    currency = Column(String(3), nullable=False, default='USD')
    
    # Dates
    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    trial_start = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="subscription")
    payments = relationship("Payment", back_populates="subscription", cascade="all, delete-orphan")
    
    @staticmethod
    def create_from_stripe(user_id, stripe_subscription):
        """Create a subscription from Stripe subscription object"""
        from datetime import datetime
        
        # Extract plan info from price metadata
        price = stripe_subscription.items.data[0].price
        plan_id = price.metadata.get('plan_id', 'basic')
        
        # Convert Stripe timestamps to datetime objects
        current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start, tz=timezone.utc) if stripe_subscription.current_period_start else None
        current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end, tz=timezone.utc) if stripe_subscription.current_period_end else None
        trial_start = datetime.fromtimestamp(stripe_subscription.trial_start, tz=timezone.utc) if stripe_subscription.trial_start else None
        trial_end = datetime.fromtimestamp(stripe_subscription.trial_end, tz=timezone.utc) if stripe_subscription.trial_end else None
        canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at, tz=timezone.utc) if stripe_subscription.canceled_at else None
        
        # Map billing interval
        billing_interval_map = {
            'month': BillingInterval.MONTHLY,
            'quarter': BillingInterval.QUARTERLY,
            'year': BillingInterval.YEARLY
        }
        billing_interval = billing_interval_map.get(price.recurring.interval, BillingInterval.MONTHLY)
        
        subscription = Subscription(
            user_id=user_id,
            stripe_subscription_id=stripe_subscription.id,
            stripe_customer_id=stripe_subscription.customer,
            stripe_price_id=price.id,
            tier=plan_id,
            status=SubscriptionStatus(stripe_subscription.status),
            billing_interval=billing_interval,
            amount=price.unit_amount / 100 if price.unit_amount else None,  # Convert cents to dollars
            currency=price.currency.upper(),
            current_period_start=current_period_start,
            current_period_end=current_period_end,
            trial_start=trial_start,
            trial_end=trial_end,
            canceled_at=canceled_at
        )
        
        db.session.add(subscription)
        db.session.commit()
        return subscription
    
    def update_from_stripe(self, stripe_subscription):
        """Update subscription from Stripe subscription object"""
        from datetime import datetime
        
        # Update status and dates
        self.status = SubscriptionStatus(stripe_subscription.status)
        self.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start, tz=timezone.utc) if stripe_subscription.current_period_start else None
        self.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end, tz=timezone.utc) if stripe_subscription.current_period_end else None
        self.trial_start = datetime.fromtimestamp(stripe_subscription.trial_start, tz=timezone.utc) if stripe_subscription.trial_start else None
        self.trial_end = datetime.fromtimestamp(stripe_subscription.trial_end, tz=timezone.utc) if stripe_subscription.trial_end else None
        self.canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at, tz=timezone.utc) if stripe_subscription.canceled_at else None
        
        # Update plan if price changed
        if stripe_subscription.items.data:
            price = stripe_subscription.items.data[0].price
            if price.id != self.stripe_price_id:
                self.stripe_price_id = price.id
                self.tier = price.metadata.get('plan_id', self.tier)
                self.amount = price.unit_amount / 100 if price.unit_amount else None
                self.currency = price.currency.upper()
                
                # Update billing interval
                billing_interval_map = {
                    'month': BillingInterval.MONTHLY,
                    'quarter': BillingInterval.QUARTERLY,
                    'year': BillingInterval.YEARLY
                }
                self.billing_interval = billing_interval_map.get(price.recurring.interval, BillingInterval.MONTHLY)
        
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
    
    def is_active(self):
        """Check if subscription is currently active"""
        return self.status in [SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING]
    
    def is_trial(self):
        """Check if subscription is in trial period"""
        return self.status == SubscriptionStatus.TRIALING
    
    def cancel_at_period_end(self):
        """Check if subscription will be canceled at period end"""
        return self.status == SubscriptionStatus.CANCELED and self.ended_at is None
    
    def days_until_renewal(self):
        """Get days until next renewal"""
        if not self.current_period_end:
            return None
        
        now = datetime.now(timezone.utc)
        if self.current_period_end > now:
            return (self.current_period_end - now).days
        return 0

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'stripe_subscription_id': self.stripe_subscription_id,
            'stripe_customer_id': self.stripe_customer_id,
            'tier': self.tier,
            'status': self.status.value if self.status else None,
            'billing_interval': self.billing_interval.value if self.billing_interval else None,
            'amount': float(self.amount) if self.amount else None,
            'currency': self.currency,
            'current_period_start': self.current_period_start.isoformat() if self.current_period_start else None,
            'current_period_end': self.current_period_end.isoformat() if self.current_period_end else None,
            'trial_start': self.trial_start.isoformat() if self.trial_start else None,
            'trial_end': self.trial_end.isoformat() if self.trial_end else None,
            'canceled_at': self.canceled_at.isoformat() if self.canceled_at else None,
            'ended_at': self.ended_at.isoformat() if self.ended_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'is_active': self.is_active(),
            'is_trial': self.is_trial(),
            'cancel_at_period_end': self.cancel_at_period_end(),
            'days_until_renewal': self.days_until_renewal()
        }

class Payment(db.Model):
    """Payment history model"""
    __tablename__ = 'payments'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    subscription_id = Column(UUID(as_uuid=True), ForeignKey('subscriptions.id'), nullable=True)
    
    # Stripe identifiers
    stripe_payment_intent_id = Column(String(255), unique=True, nullable=True)
    stripe_invoice_id = Column(String(255), nullable=True)
    stripe_charge_id = Column(String(255), nullable=True)
    
    # Payment details
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(3), nullable=False, default='USD')
    status = Column(String(50), nullable=False)  # succeeded, failed, pending, etc.
    description = Column(Text, nullable=True)
    
    # Metadata
    payment_method = Column(String(50), nullable=True)  # card, bank_transfer, etc.
    failure_reason = Column(Text, nullable=True)
    receipt_url = Column(Text, nullable=True)
    
    # Dates
    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="payments")
    subscription = relationship("Subscription", back_populates="payments")
    
    @staticmethod
    def create_from_stripe(user_id, stripe_payment_intent, subscription_id=None):
        """Create a payment from Stripe payment intent object"""
        from datetime import datetime
        
        # Get the charge from the payment intent
        charge = stripe_payment_intent.charges.data[0] if stripe_payment_intent.charges.data else None
        
        payment = Payment(
            user_id=user_id,
            subscription_id=subscription_id,
            stripe_payment_intent_id=stripe_payment_intent.id,
            stripe_invoice_id=stripe_payment_intent.invoice if hasattr(stripe_payment_intent, 'invoice') else None,
            stripe_charge_id=charge.id if charge else None,
            amount=stripe_payment_intent.amount / 100,  # Convert cents to dollars
            currency=stripe_payment_intent.currency.upper(),
            status=stripe_payment_intent.status,
            description=stripe_payment_intent.description,
            payment_method=charge.payment_method_details.type if charge and charge.payment_method_details else None,
            receipt_url=charge.receipt_url if charge else None,
            paid_at=datetime.fromtimestamp(charge.created, tz=timezone.utc) if charge else None
        )
        
        db.session.add(payment)
        db.session.commit()
        return payment
    
    @staticmethod
    def create_from_stripe_invoice(user_id, stripe_invoice, subscription_id=None):
        """Create a payment from Stripe invoice object"""
        from datetime import datetime
        
        payment = Payment(
            user_id=user_id,
            subscription_id=subscription_id,
            stripe_invoice_id=stripe_invoice.id,
            stripe_payment_intent_id=stripe_invoice.payment_intent,
            stripe_charge_id=stripe_invoice.charge,
            amount=stripe_invoice.amount_paid / 100,  # Convert cents to dollars
            currency=stripe_invoice.currency.upper(),
            status='succeeded' if stripe_invoice.paid else 'failed',
            description=f"Invoice {stripe_invoice.number}",
            receipt_url=stripe_invoice.hosted_invoice_url,
            paid_at=datetime.fromtimestamp(stripe_invoice.status_transitions.paid_at, tz=timezone.utc) if stripe_invoice.status_transitions.paid_at else None
        )
        
        db.session.add(payment)
        db.session.commit()
        return payment

    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'subscription_id': str(self.subscription_id) if self.subscription_id else None,
            'stripe_payment_intent_id': self.stripe_payment_intent_id,
            'stripe_invoice_id': self.stripe_invoice_id,
            'amount': float(self.amount),
            'currency': self.currency,
            'status': self.status,
            'description': self.description,
            'payment_method': self.payment_method,
            'failure_reason': self.failure_reason,
            'receipt_url': self.receipt_url,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class BillingAddress(db.Model):
    """User billing address model"""
    __tablename__ = 'billing_addresses'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    
    # Address details
    line1 = Column(String(255), nullable=False)
    line2 = Column(String(255), nullable=True)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=False)
    country = Column(String(2), nullable=False)  # ISO country code
    
    # Metadata
    is_default = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships
    user = relationship("User", back_populates="billing_addresses")
    
    def to_dict(self):
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'line1': self.line1,
            'line2': self.line2,
            'city': self.city,
            'state': self.state,
            'postal_code': self.postal_code,
            'country': self.country,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

