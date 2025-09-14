#!/usr/bin/env python3
"""
Script to add 'basic' tier to subscription_tier enum
"""
import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def add_basic_tier():
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL', 'postgresql://postgres:EvJpKjxEJTxQoUgVkOhOtIeYNppYnosU@yamabiko.proxy.rlwy.net:20076/railway')
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()
        
        # Check current enum values
        cur.execute("SELECT unnest(enum_range(NULL::subscription_tier));")
        current_values = [row[0] for row in cur.fetchall()]
        print(f"Current enum values: {current_values}")
        
        # Add 'basic' if not exists
        if 'basic' not in current_values:
            print("Adding 'basic' to subscription_tier enum...")
            cur.execute("ALTER TYPE subscription_tier ADD VALUE 'basic';")
            print("✅ Successfully added 'basic' to enum")
        else:
            print("✅ 'basic' already exists in enum")
        
        # Verify the change
        cur.execute("SELECT unnest(enum_range(NULL::subscription_tier));")
        updated_values = [row[0] for row in cur.fetchall()]
        print(f"Updated enum values: {updated_values}")
        
        # Close connection
        cur.close()
        conn.close()
        
        print("✅ Database enum update completed successfully!")
        
    except Exception as e:
        print(f"❌ Error updating enum: {e}")
        return False
    
    return True

if __name__ == "__main__":
    add_basic_tier()

