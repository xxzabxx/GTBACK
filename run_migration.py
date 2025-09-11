#!/usr/bin/env python3
"""
Migration runner for Railway deployment
This script will be run automatically when the app starts
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_migration():
    """Run database migration to add tier system columns"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("WARNING: DATABASE_URL not found, skipping migration")
        return True
    
    try:
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        # Check if migration is needed
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND column_name = 'is_admin'
        """)
        
        if cursor.fetchone():
            print("✅ Database already migrated")
            cursor.close()
            conn.close()
            return True
        
        print("🔄 Running database migration...")
        
        # Add missing columns
        migrations = [
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT false',
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_tier VARCHAR(20) DEFAULT 'free'",
            'ALTER TABLE users ADD COLUMN IF NOT EXISTS subscription_expires TIMESTAMP WITH TIME ZONE'
        ]
        
        for sql in migrations:
            cursor.execute(sql)
        
        # Update existing users
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = COALESCE(subscription_tier, 'free'),
                is_admin = COALESCE(is_admin, false)
        """)
        
        # Make first user admin if no admins exist
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = true")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                UPDATE users 
                SET is_admin = true, subscription_tier = 'pro' 
                WHERE id = (SELECT id FROM users ORDER BY created_at LIMIT 1)
            """)
        
        print("✅ Migration completed successfully")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    run_migration()

