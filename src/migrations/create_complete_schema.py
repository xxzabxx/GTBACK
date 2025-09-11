"""
Complete database schema migration for GrimmTrading Platform
Creates all tables needed for Phase 1: User tiers, admin dashboard, permissions
"""

import os
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

def run_complete_migration():
    """Create complete database schema in Railway PostgreSQL"""
    
    # Get database URL from environment
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found")
        return False
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        print("🔄 Creating complete database schema...")
        
        # Create custom types first
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE subscription_tier AS ENUM ('free', 'premium', 'pro');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE alert_type AS ENUM ('price', 'volume', 'technical', 'news');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        cursor.execute("""
            DO $$ BEGIN
                CREATE TYPE condition_type AS ENUM ('above', 'below', 'crosses_above', 'crosses_below', 'equals');
            EXCEPTION
                WHEN duplicate_object THEN null;
            END $$;
        """)
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) UNIQUE NOT NULL CHECK (username ~ '^[A-Za-z0-9_]{3,50}$'),
                email VARCHAR(255) UNIQUE NOT NULL CHECK (email ~ '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
                password_hash VARCHAR(255) NOT NULL,
                first_name VARCHAR(100),
                last_name VARCHAR(100),
                subscription_tier subscription_tier DEFAULT 'free',
                subscription_expires TIMESTAMPTZ,
                is_active BOOLEAN DEFAULT true,
                is_admin BOOLEAN DEFAULT false,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                last_login TIMESTAMPTZ,
                email_verified BOOLEAN DEFAULT false,
                email_verification_token VARCHAR(255),
                password_reset_token VARCHAR(255),
                password_reset_expires TIMESTAMPTZ,
                timezone VARCHAR(50) DEFAULT 'America/New_York',
                preferred_language VARCHAR(10) DEFAULT 'en',
                avatar_url TEXT,
                bio TEXT,
                default_watchlist_id UUID,
                notification_preferences JSONB DEFAULT '{"sms": false, "push": true, "email": true}',
                trading_preferences JSONB DEFAULT '{"risk_level": "medium", "position_size": "small"}'
            );
        """)
        
        # Create watchlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlists (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                is_default BOOLEAN DEFAULT false,
                is_public BOOLEAN DEFAULT false,
                color VARCHAR(7) DEFAULT '#3B82F6',
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Create watchlist_symbols table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchlist_symbols (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                watchlist_id UUID NOT NULL REFERENCES watchlists(id) ON DELETE CASCADE,
                symbol VARCHAR(10) NOT NULL,
                notes TEXT,
                sort_order INTEGER DEFAULT 0,
                added_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Create alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                symbol VARCHAR(10) NOT NULL,
                alert_type alert_type NOT NULL,
                condition_type condition_type NOT NULL,
                target_value NUMERIC NOT NULL,
                current_value NUMERIC,
                message TEXT,
                is_active BOOLEAN DEFAULT true,
                is_triggered BOOLEAN DEFAULT false,
                triggered_at TIMESTAMPTZ,
                expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                notification_methods JSONB DEFAULT '["email"]',
                trigger_count INTEGER DEFAULT 0,
                max_triggers INTEGER DEFAULT 1
            );
        """)
        
        # Create user_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token_hash VARCHAR(255) NOT NULL,
                device_info JSONB,
                ip_address INET,
                user_agent TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                expires_at TIMESTAMPTZ NOT NULL,
                is_active BOOLEAN DEFAULT true,
                last_used_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Create subscription_history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS subscription_history (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                tier subscription_tier NOT NULL,
                started_at TIMESTAMPTZ DEFAULT NOW(),
                ended_at TIMESTAMPTZ,
                payment_method VARCHAR(50),
                transaction_id VARCHAR(100),
                amount NUMERIC(10,2),
                currency VARCHAR(3) DEFAULT 'USD',
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Create user_activity table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_activity (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                action VARCHAR(100) NOT NULL,
                resource_type VARCHAR(50),
                resource_id UUID,
                metadata JSONB,
                ip_address INET,
                user_agent TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        
        # Create system_settings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_settings (
                key VARCHAR(100) PRIMARY KEY,
                value JSONB NOT NULL,
                description TEXT,
                updated_at TIMESTAMPTZ DEFAULT NOW(),
                updated_by UUID REFERENCES users(id)
            );
        """)
        
        # Create indexes for performance
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
            CREATE INDEX IF NOT EXISTS idx_users_subscription_tier ON users(subscription_tier);
            CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active);
            CREATE INDEX IF NOT EXISTS idx_watchlists_user_id ON watchlists(user_id);
            CREATE INDEX IF NOT EXISTS idx_watchlist_symbols_watchlist_id ON watchlist_symbols(watchlist_id);
            CREATE INDEX IF NOT EXISTS idx_watchlist_symbols_symbol ON watchlist_symbols(symbol);
            CREATE INDEX IF NOT EXISTS idx_alerts_user_id ON alerts(user_id);
            CREATE INDEX IF NOT EXISTS idx_alerts_symbol ON alerts(symbol);
            CREATE INDEX IF NOT EXISTS idx_alerts_is_active ON alerts(is_active);
            CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash);
            CREATE INDEX IF NOT EXISTS idx_subscription_history_user_id ON subscription_history(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_activity_user_id ON user_activity(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_activity_action ON user_activity(action);
        """)
        
        # Create trigger for updated_at timestamps
        cursor.execute("""
            CREATE OR REPLACE FUNCTION update_updated_at_column()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.updated_at = NOW();
                RETURN NEW;
            END;
            $$ language 'plpgsql';
        """)
        
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_users_updated_at ON users;
            CREATE TRIGGER update_users_updated_at 
                BEFORE UPDATE ON users 
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_watchlists_updated_at ON watchlists;
            CREATE TRIGGER update_watchlists_updated_at 
                BEFORE UPDATE ON watchlists 
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        cursor.execute("""
            DROP TRIGGER IF EXISTS update_alerts_updated_at ON alerts;
            CREATE TRIGGER update_alerts_updated_at 
                BEFORE UPDATE ON alerts 
                FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
        """)
        
        # Insert default system settings
        cursor.execute("""
            INSERT INTO system_settings (key, value, description) 
            VALUES 
                ('platform_name', '"GrimmTrading"', 'Platform display name'),
                ('max_watchlists_free', '3', 'Maximum watchlists for free tier'),
                ('max_watchlists_premium', '10', 'Maximum watchlists for premium tier'),
                ('max_watchlists_pro', '50', 'Maximum watchlists for pro tier'),
                ('max_alerts_free', '5', 'Maximum alerts for free tier'),
                ('max_alerts_premium', '50', 'Maximum alerts for premium tier'),
                ('max_alerts_pro', '500', 'Maximum alerts for pro tier'),
                ('market_data_delay_free', '15', 'Market data delay in minutes for free tier'),
                ('market_data_delay_premium', '0', 'Market data delay in minutes for premium tier'),
                ('market_data_delay_pro', '0', 'Market data delay in minutes for pro tier')
            ON CONFLICT (key) DO NOTHING;
        """)
        
        cursor.close()
        conn.close()
        
        print("✅ Complete database schema created successfully!")
        print("📊 Created tables: users, watchlists, watchlist_symbols, alerts, user_sessions, subscription_history, user_activity, system_settings")
        print("🔧 Created indexes and triggers for performance")
        print("⚙️  Inserted default system settings")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        return False

if __name__ == "__main__":
    run_complete_migration()

