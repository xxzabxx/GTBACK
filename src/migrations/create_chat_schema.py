"""
Chat Schema Migration
Creates tables for trading room chat functionality
"""

import psycopg2
import os
from datetime import datetime

def create_chat_schema():
    """Create chat-related database tables and indexes"""
    
    # Database connection
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not found in environment variables")
        return False
    
    try:
        # Connect to database
        conn = psycopg2.connect(database_url)
        cur = conn.cursor()
        
        print("🔧 Creating chat schema...")
        
        # Chat messages table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                username VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                message_type VARCHAR(20) DEFAULT 'text',
                stock_symbols TEXT[],
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted BOOLEAN DEFAULT FALSE,
                deleted_by UUID REFERENCES users(id),
                CONSTRAINT check_message_length CHECK (length(message) <= 1000)
            );
        """)
        
        # Chat user sessions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                session_id VARCHAR(100) UNIQUE NOT NULL,
                connected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT TRUE
            );
        """)
        
        # Chat rate limiting table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS chat_rate_limits (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                user_id UUID REFERENCES users(id) ON DELETE CASCADE,
                message_count INTEGER DEFAULT 0,
                window_start TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id)
            );
        """)
        
        print("📊 Creating chat indexes for performance...")
        
        # Indexes for performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_created_at ON chat_messages(created_at DESC);",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_id ON chat_messages(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_stock_symbols ON chat_messages USING GIN(stock_symbols);",
            "CREATE INDEX IF NOT EXISTS idx_chat_messages_active ON chat_messages(created_at DESC) WHERE is_deleted = FALSE;",
            "CREATE INDEX IF NOT EXISTS idx_chat_sessions_user_id ON chat_sessions(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_chat_sessions_active ON chat_sessions(user_id, is_active) WHERE is_active = TRUE;",
            "CREATE INDEX IF NOT EXISTS idx_chat_rate_limits_user_id ON chat_rate_limits(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_chat_rate_limits_window ON chat_rate_limits(window_start);"
        ]
        
        for index_sql in indexes:
            cur.execute(index_sql)
        
        print("🔧 Creating chat cleanup function...")
        
        # Function to cleanup old messages (24 hours)
        cur.execute("""
            CREATE OR REPLACE FUNCTION cleanup_old_chat_messages()
            RETURNS INTEGER AS $$
            DECLARE
                deleted_count INTEGER;
            BEGIN
                DELETE FROM chat_messages 
                WHERE created_at < NOW() - INTERVAL '24 hours';
                
                GET DIAGNOSTICS deleted_count = ROW_COUNT;
                
                -- Also cleanup inactive sessions
                DELETE FROM chat_sessions 
                WHERE last_activity < NOW() - INTERVAL '1 hour';
                
                -- Reset rate limits older than 1 minute
                DELETE FROM chat_rate_limits 
                WHERE window_start < NOW() - INTERVAL '1 minute';
                
                RETURN deleted_count;
            END;
            $$ LANGUAGE plpgsql;
        """)
        
        print("⚙️ Inserting default chat settings...")
        
        # Insert default system settings for chat
        cur.execute("""
            INSERT INTO system_settings (key, value, description) 
            VALUES 
                ('chat_enabled', 'true', 'Enable/disable trading room chat'),
                ('chat_max_message_length', '1000', 'Maximum characters per chat message'),
                ('chat_rate_limit_messages', '5', 'Maximum messages per minute per user'),
                ('chat_history_hours', '24', 'Hours of chat history to keep'),
                ('chat_premium_only', 'true', 'Restrict chat to premium users only')
            ON CONFLICT (key) DO NOTHING;
        """)
        
        # Commit changes
        conn.commit()
        cur.close()
        conn.close()
        
        print("✅ Chat schema created successfully!")
        print("📊 Tables created: chat_messages, chat_sessions, chat_rate_limits")
        print("🔧 Indexes and functions created for performance")
        print("⚙️ Default chat settings configured")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating chat schema: {str(e)}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()
        return False

if __name__ == "__main__":
    create_chat_schema()

