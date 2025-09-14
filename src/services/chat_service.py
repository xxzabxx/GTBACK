"""
Trading Room Chat Service
Handles real-time WebSocket communication for premium users
"""

import re
import json
from datetime import datetime, timedelta
from flask import current_app
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect
from flask_jwt_extended import decode_token, verify_jwt_in_request
from src.database import db
from src.models.user import User
import uuid

class ChatService:
    def __init__(self):
        self.socketio = None
        self.active_users = {}  # {session_id: user_info}
        
    def init_app(self, app, socketio):
        """Initialize chat service with Flask app and SocketIO"""
        self.socketio = socketio
        self.app = app
        self.setup_events()
        
    def setup_events(self):
        """Setup WebSocket event handlers"""
        
        @self.socketio.on('connect')
        def handle_connect(auth):
            """Handle user connection to chat"""
            try:
                # Verify JWT token and premium access
                token = auth.get('token') if auth else None
                if not token:
                    current_app.logger.warning("Chat connection rejected: No token provided")
                    disconnect()
                    return False
                
                # Decode JWT token
                try:
                    decoded_token = decode_token(token)
                    user_id = decoded_token['sub']
                except Exception as e:
                    current_app.logger.warning(f"Chat connection rejected: Invalid token - {str(e)}")
                    disconnect()
                    return False
                
                # Get user from database
                user = User.query.get(user_id)
                if not user:
                    current_app.logger.warning(f"Chat connection rejected: User not found - {user_id}")
                    disconnect()
                    return False
                
                # Check if user has premium access
                if user.subscription_tier not in ['pro', 'premium']:
                    current_app.logger.warning(f"Chat connection rejected: User {user.username} has tier {user.subscription_tier}")
                    emit('error', {'message': 'Premium subscription required for trading room chat'})
                    disconnect()
                    return False
                
                # Join trading room
                join_room('trading_room')
                
                # Store user session
                session_id = str(uuid.uuid4())
                self.active_users[session_id] = {
                    'user_id': user.id,
                    'username': user.username,
                    'tier': user.subscription_tier,
                    'connected_at': datetime.utcnow(),
                    'last_activity': datetime.utcnow()
                }
                
                # Save session to database
                self._save_chat_session(user.id, session_id)
                
                # Send recent chat history
                recent_messages = self._get_recent_messages()
                emit('chat_history', recent_messages)
                
                # Notify room of new user
                emit('user_joined', {
                    'username': user.username,
                    'tier': user.subscription_tier,
                    'timestamp': datetime.utcnow().isoformat()
                }, room='trading_room', include_self=False)
                
                # Send current online users count
                online_count = len(self.active_users)
                emit('online_count', {'count': online_count}, room='trading_room')
                
                current_app.logger.info(f"User {user.username} connected to trading room chat")
                return True
                
            except Exception as e:
                current_app.logger.error(f"Error in chat connect: {str(e)}")
                disconnect()
                return False
        
        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle user disconnection from chat"""
            try:
                # Find and remove user session
                session_to_remove = None
                user_info = None
                
                for session_id, user_data in self.active_users.items():
                    # This is a simplified approach - in production you'd want better session tracking
                    session_to_remove = session_id
                    user_info = user_data
                    break
                
                if session_to_remove:
                    del self.active_users[session_to_remove]
                    
                    # Update database session
                    self._update_chat_session(session_to_remove, is_active=False)
                    
                    # Notify room of user leaving
                    if user_info:
                        emit('user_left', {
                            'username': user_info['username'],
                            'timestamp': datetime.utcnow().isoformat()
                        }, room='trading_room')
                        
                        current_app.logger.info(f"User {user_info['username']} disconnected from trading room chat")
                
                # Send updated online count
                online_count = len(self.active_users)
                emit('online_count', {'count': online_count}, room='trading_room')
                
            except Exception as e:
                current_app.logger.error(f"Error in chat disconnect: {str(e)}")
        
        @self.socketio.on('send_message')
        def handle_send_message(data):
            """Handle incoming chat message"""
            try:
                message = data.get('message', '').strip()
                if not message:
                    emit('error', {'message': 'Message cannot be empty'})
                    return
                
                # Validate message length
                if len(message) > 1000:
                    emit('error', {'message': 'Message too long (max 1000 characters)'})
                    return
                
                # Find user session (simplified - in production use proper session tracking)
                user_info = None
                for session_id, user_data in self.active_users.items():
                    user_info = user_data
                    break
                
                if not user_info:
                    emit('error', {'message': 'User session not found'})
                    return
                
                # Check rate limiting
                if not self._check_rate_limit(user_info['user_id']):
                    emit('error', {'message': 'Rate limit exceeded. Please slow down.'})
                    return
                
                # Detect stock symbols
                stock_symbols = self._parse_stock_symbols(message)
                
                # Save message to database
                message_id = self._save_message(
                    user_info['user_id'],
                    user_info['username'],
                    message,
                    stock_symbols
                )
                
                # Prepare message for broadcast
                message_data = {
                    'id': str(message_id),
                    'username': user_info['username'],
                    'tier': user_info['tier'],
                    'message': message,
                    'stock_symbols': stock_symbols,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
                # Broadcast to all users in trading room
                emit('new_message', message_data, room='trading_room')
                
                current_app.logger.info(f"Message sent by {user_info['username']}: {message[:50]}...")
                
            except Exception as e:
                current_app.logger.error(f"Error handling message: {str(e)}")
                emit('error', {'message': 'Failed to send message'})
    
    def _save_chat_session(self, user_id, session_id):
        """Save chat session to database"""
        try:
            from src.database import db
            
            # Clean up old sessions for this user
            db.session.execute(
                "UPDATE chat_sessions SET is_active = FALSE WHERE user_id = %s",
                (user_id,)
            )
            
            # Insert new session
            db.session.execute(
                """INSERT INTO chat_sessions (user_id, session_id, connected_at, last_activity, is_active)
                   VALUES (%s, %s, %s, %s, %s)""",
                (user_id, session_id, datetime.utcnow(), datetime.utcnow(), True)
            )
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Error saving chat session: {str(e)}")
            db.session.rollback()
    
    def _update_chat_session(self, session_id, is_active=True):
        """Update chat session activity"""
        try:
            from src.database import db
            
            db.session.execute(
                "UPDATE chat_sessions SET last_activity = %s, is_active = %s WHERE session_id = %s",
                (datetime.utcnow(), is_active, session_id)
            )
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Error updating chat session: {str(e)}")
            db.session.rollback()
    
    def _get_recent_messages(self, hours=24, limit=50):
        """Get recent chat messages"""
        try:
            from src.database import db
            
            result = db.session.execute(
                """SELECT id, username, message, stock_symbols, created_at, message_type
                   FROM chat_messages 
                   WHERE created_at > %s AND is_deleted = FALSE
                   ORDER BY created_at DESC 
                   LIMIT %s""",
                (datetime.utcnow() - timedelta(hours=hours), limit)
            )
            
            messages = []
            for row in result:
                messages.append({
                    'id': str(row[0]),
                    'username': row[1],
                    'message': row[2],
                    'stock_symbols': row[3] or [],
                    'timestamp': row[4].isoformat(),
                    'message_type': row[5]
                })
            
            # Reverse to get chronological order
            return list(reversed(messages))
            
        except Exception as e:
            current_app.logger.error(f"Error getting recent messages: {str(e)}")
            return []
    
    def _save_message(self, user_id, username, message, stock_symbols):
        """Save chat message to database"""
        try:
            from src.database import db
            
            message_id = str(uuid.uuid4())
            
            db.session.execute(
                """INSERT INTO chat_messages (id, user_id, username, message, stock_symbols, created_at, message_type)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (message_id, user_id, username, message, stock_symbols, datetime.utcnow(), 'text')
            )
            db.session.commit()
            
            return message_id
            
        except Exception as e:
            current_app.logger.error(f"Error saving message: {str(e)}")
            db.session.rollback()
            return None
    
    def _parse_stock_symbols(self, message):
        """Parse stock symbols from message ($AAPL format)"""
        try:
            # Regex to find $SYMBOL patterns (1-5 uppercase letters)
            pattern = r'\\$([A-Z]{1,5})\\b'
            symbols = re.findall(pattern, message.upper())
            
            # Remove duplicates and validate
            unique_symbols = list(set(symbols))
            
            # Basic validation - could be enhanced with actual stock symbol validation
            valid_symbols = []
            for symbol in unique_symbols:
                if len(symbol) >= 1 and len(symbol) <= 5 and symbol.isalpha():
                    valid_symbols.append(symbol)
            
            return valid_symbols
            
        except Exception as e:
            current_app.logger.error(f"Error parsing stock symbols: {str(e)}")
            return []
    
    def _check_rate_limit(self, user_id, max_messages=5, window_minutes=1):
        """Check if user is within rate limits"""
        try:
            from src.database import db
            
            window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
            
            # Get or create rate limit record
            result = db.session.execute(
                "SELECT message_count, window_start FROM chat_rate_limits WHERE user_id = %s",
                (user_id,)
            ).fetchone()
            
            if result:
                message_count, last_window = result
                
                # Check if we're in a new window
                if last_window < window_start:
                    # Reset counter for new window
                    db.session.execute(
                        "UPDATE chat_rate_limits SET message_count = 1, window_start = %s WHERE user_id = %s",
                        (datetime.utcnow(), user_id)
                    )
                    db.session.commit()
                    return True
                else:
                    # Check if under limit
                    if message_count < max_messages:
                        # Increment counter
                        db.session.execute(
                            "UPDATE chat_rate_limits SET message_count = message_count + 1 WHERE user_id = %s",
                            (user_id,)
                        )
                        db.session.commit()
                        return True
                    else:
                        # Rate limit exceeded
                        return False
            else:
                # Create new rate limit record
                db.session.execute(
                    "INSERT INTO chat_rate_limits (user_id, message_count, window_start) VALUES (%s, %s, %s)",
                    (user_id, 1, datetime.utcnow())
                )
                db.session.commit()
                return True
                
        except Exception as e:
            current_app.logger.error(f"Error checking rate limit: {str(e)}")
            db.session.rollback()
            # Allow message on error to avoid blocking users
            return True

# Global chat service instance
chat_service = ChatService()

