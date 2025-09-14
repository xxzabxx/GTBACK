"""
Database migration script to create payment-related tables for Stripe integration
Run this script to add subscription, payment, and billing_address tables
"""

import os
import sys
from datetime import datetime

# Add the project root to the path so we can import our modules
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)

from src.database import db
from src.models.user import User
from src.models.subscription import Subscription, Payment, BillingAddress

def create_payment_tables():
    """Create all payment-related tables"""
    try:
        print("Creating payment-related database tables...")
        
        # Create all tables defined in the models
        db.create_all()
        
        print("✅ Successfully created payment tables:")
        print("  - subscriptions")
        print("  - payments") 
        print("  - billing_addresses")
        
        # Verify tables were created
        inspector = db.inspect(db.engine)
        existing_tables = inspector.get_table_names()
        
        required_tables = ['subscriptions', 'payments', 'billing_addresses']
        for table in required_tables:
            if table in existing_tables:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' was not created")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating payment tables: {str(e)}")
        return False

def add_indexes():
    """Add database indexes for better performance"""
    try:
        print("\nAdding database indexes...")
        
        # Add indexes for common queries using text() for raw SQL
        from sqlalchemy import text
        
        with db.engine.connect() as conn:
            # Subscription indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id ON subscriptions(user_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_subscription_id ON subscriptions(stripe_subscription_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_stripe_customer_id ON subscriptions(stripe_customer_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions(status);"))
            # Skip tier index for now due to schema conflicts
            # conn.execute(text("CREATE INDEX IF NOT EXISTS idx_subscriptions_tier ON subscriptions(tier);"))
            
            # Payment indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_subscription_id ON payments(subscription_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_stripe_payment_intent_id ON payments(stripe_payment_intent_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_created_at ON payments(created_at);"))
            
            # Billing address indexes
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_billing_addresses_user_id ON billing_addresses(user_id);"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_billing_addresses_is_default ON billing_addresses(is_default);"))
            
            conn.commit()
        
        print("✅ Successfully added database indexes")
        return True
        
    except Exception as e:
        print(f"❌ Error adding indexes: {str(e)}")
        return False

def verify_user_model_compatibility():
    """Verify that the User model is compatible with the new payment models"""
    try:
        print("\nVerifying User model compatibility...")
        
        # Check if User model has the required relationships
        user_relationships = ['subscription', 'payments', 'billing_addresses']
        
        for rel in user_relationships:
            if hasattr(User, rel):
                print(f"✅ User.{rel} relationship exists")
            else:
                print(f"❌ User.{rel} relationship missing")
                return False
        
        print("✅ User model is compatible with payment models")
        return True
        
    except Exception as e:
        print(f"❌ Error verifying User model: {str(e)}")
        return False

def run_migration():
    """Run the complete migration"""
    print("=" * 60)
    print("GRIMMTRADING PAYMENT SYSTEM MIGRATION")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Step 1: Verify User model compatibility
    if not verify_user_model_compatibility():
        print("\n❌ Migration failed: User model compatibility issues")
        return False
    
    # Step 2: Create payment tables
    if not create_payment_tables():
        print("\n❌ Migration failed: Could not create payment tables")
        return False
    
    # Step 3: Add indexes
    if not add_indexes():
        print("\n❌ Migration failed: Could not add indexes")
        return False
    
    print("\n" + "=" * 60)
    print("✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("=" * 60)
    print("The following tables are now available:")
    print("  - subscriptions: Store Stripe subscription data")
    print("  - payments: Track all payment transactions")
    print("  - billing_addresses: Store user billing information")
    print()
    print("Next steps:")
    print("  1. Set up Stripe service layer")
    print("  2. Create payment API routes")
    print("  3. Implement webhook handlers")
    print("  4. Test payment flows")
    print(f"\nCompleted at: {datetime.now()}")
    
    return True

if __name__ == "__main__":
    # Import Flask app to initialize database connection
    try:
        from src.main import app
        
        with app.app_context():
            success = run_migration()
            sys.exit(0 if success else 1)
            
    except ImportError as e:
        print(f"❌ Could not import Flask app: {e}")
        print("Make sure you're running this from the correct directory")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Migration failed with error: {e}")
        sys.exit(1)

