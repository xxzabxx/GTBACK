#!/usr/bin/env python3
"""
Database migration to add tier system columns to existing users table
Run this script to update your Railway PostgreSQL database
"""

import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL')

def run_migration():
    """Run the database migration"""
    database_url = get_database_url()
    
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not found")
        return False
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("Connected to database successfully")
        
        # Check if columns already exist
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'users' AND table_schema = 'public'
        """)
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"Existing columns: {existing_columns}")
        
        # Add missing columns one by one
        migrations = [
            {
                'column': 'is_admin',
                'sql': 'ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT false'
            },
            {
                'column': 'subscription_tier',
                'sql': "ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'"
            },
            {
                'column': 'subscription_expires',
                'sql': 'ALTER TABLE users ADD COLUMN subscription_expires TIMESTAMP WITH TIME ZONE'
            }
        ]
        
        for migration in migrations:
            column_name = migration['column']
            sql = migration['sql']
            
            if column_name not in existing_columns:
                print(f"Adding column: {column_name}")
                cursor.execute(sql)
                print(f"✅ Added column: {column_name}")
            else:
                print(f"⏭️  Column already exists: {column_name}")
        
        # Update existing users to have proper tier info
        print("Updating existing users with default tier info...")
        cursor.execute("""
            UPDATE users 
            SET subscription_tier = 'free', is_admin = false 
            WHERE subscription_tier IS NULL OR is_admin IS NULL
        """)
        
        # Create first admin user if none exists
        cursor.execute("SELECT COUNT(*) FROM users WHERE is_admin = true")
        admin_count = cursor.fetchone()[0]
        
        if admin_count == 0:
            print("No admin users found. Creating admin user...")
            cursor.execute("""
                UPDATE users 
                SET is_admin = true, subscription_tier = 'pro' 
                WHERE id = (SELECT id FROM users ORDER BY created_at LIMIT 1)
            """)
            print("✅ First user promoted to admin")
        
        print("✅ Migration completed successfully!")
        
        # Verify the migration
        cursor.execute("SELECT username, is_admin, subscription_tier FROM users LIMIT 5")
        users = cursor.fetchall()
        print("\nVerification - Sample users:")
        for user in users:
            print(f"  {user[0]}: admin={user[1]}, tier={user[2]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    print("🔄 Starting database migration...")
    success = run_migration()
    
    if success:
        print("🎉 Migration completed successfully!")
        sys.exit(0)
    else:
        print("❌ Migration failed!")
        sys.exit(1)

