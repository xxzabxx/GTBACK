# GrimmTrading Backend

Professional day trading platform backend built with Flask, JWT authentication, and SQLAlchemy.

## Features

- 🔐 JWT Authentication (register, login, profile management)
- 👤 User management with subscription tiers
- 📊 Database models for trading platform
- 🔒 Password hashing with bcrypt
- 🌐 CORS configured for frontend integration
- ⚡ SQLite for development, PostgreSQL for production

## Quick Start

### Local Development

1. **Clone and setup:**
   ```bash
   cd gtback
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

3. **Run the server:**
   ```bash
   python src/main.py
   ```

   Server will start at `http://localhost:5001`

### Railway Deployment

1. **Create Railway project:**
   - Go to [railway.app](https://railway.app)
   - Create new project from GitHub repo
   - Select this backend directory

2. **Add PostgreSQL database:**
   - Add PostgreSQL service to your Railway project
   - Railway will auto-set DATABASE_URL

3. **Configure environment variables:**
   ```
   FLASK_ENV=production
   SECRET_KEY=your-secret-key-here
   JWT_SECRET_KEY=your-jwt-secret-key-here
   DATABASE_URL=postgresql://... (auto-set by Railway)
   ```

4. **Deploy:**
   - Railway will automatically deploy using `railway.toml`
   - Health check endpoint: `/api/health`

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login user
- `GET /api/auth/profile` - Get user profile (requires JWT)
- `PUT /api/auth/profile` - Update user profile (requires JWT)
- `POST /api/auth/change-password` - Change password (requires JWT)
- `POST /api/auth/refresh` - Refresh JWT token

### Health
- `GET /api/health` - Health check endpoint

## Database Schema

### Users Table
- `id` - Primary key
- `username` - Unique username
- `email` - Unique email
- `password_hash` - Bcrypt hashed password
- `first_name`, `last_name` - User details
- `subscription_tier` - free, premium, professional
- `is_active`, `is_verified` - Account status
- `created_at`, `updated_at`, `last_login` - Timestamps

### Watchlists Table
- `id` - Primary key
- `user_id` - Foreign key to users
- `name` - Watchlist name
- `symbols` - JSON string of stock symbols
- `is_default` - Default watchlist flag
- `created_at`, `updated_at` - Timestamps

## Environment Variables

```bash
# Flask Configuration
FLASK_ENV=development
SECRET_KEY=your-secret-key
JWT_SECRET_KEY=your-jwt-secret-key

# Database (SQLite for dev, PostgreSQL for prod)
DATABASE_URL=sqlite:///src/database/grimm_trading.db

# CORS Origins
CORS_ORIGINS=http://localhost:3000,http://localhost:5173

# Future API Keys
FINNHUB_API_KEY=your-finnhub-key
```

## Project Structure

```
gtback/
├── src/
│   ├── main.py              # Flask application entry point
│   ├── config.py            # Configuration management
│   ├── models/
│   │   └── user.py          # User and Watchlist models
│   ├── routes/
│   │   └── auth.py          # Authentication routes
│   └── database/            # SQLite database files
├── venv/                    # Virtual environment
├── requirements.txt         # Python dependencies
├── railway.toml            # Railway deployment config
├── .env                    # Environment variables
└── README.md               # This file
```

## Development

### Adding New Routes
1. Create new blueprint in `src/routes/`
2. Register blueprint in `src/main.py`
3. Add any new models to `src/models/`

### Database Migrations
For production with PostgreSQL, consider adding Flask-Migrate:
```bash
pip install Flask-Migrate
```

## Security

- Passwords are hashed with bcrypt
- JWT tokens for authentication
- CORS configured for specific origins
- Input validation on all endpoints
- SQL injection protection with SQLAlchemy ORM

## Support

For issues or questions, please check the deployment logs in Railway or run locally with debug mode enabled.

