"""
Chat Application Module
Handles Socket.IO integration for real-time chat
This module extends the main Flask app with WebSocket capabilities
"""

from flask_socketio import SocketIO
from src.services.chat_service import chat_service

def init_chat_app(app):
    """Initialize chat functionality with the Flask app"""
    
    # Initialize Socket.IO with the app (Railway-compatible configuration)
    socketio = SocketIO(
        app,
        cors_allowed_origins=app.config.get('CORS_ORIGINS', '*'),
        async_mode='threading',  # Use threading instead of eventlet for Railway
        logger=False,  # Disable verbose logging for production
        engineio_logger=False,
        ping_timeout=60,
        ping_interval=25
    )
    
    # Initialize chat service with Socket.IO
    chat_service.init_app(app, socketio)
    
    # Register chat routes blueprint
    from src.routes.chat import chat_bp
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    
    app.logger.info("✅ Chat functionality initialized successfully")
    
    return socketio

def get_chat_service():
    """Get the global chat service instance"""
    return chat_service

