# Flask Setup Guide - Robin Onion Search

## Overview

Robin now includes a **Flask web application** with:
- ✅ User authentication (register/login)
- ✅ SQL database for saving search results
- ✅ User statistics and search history
- ✅ RESTful API for programmatic access
- ✅ Responsive dashboard UI

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install:
- Flask
- Flask-SQLAlchemy (ORM)
- Flask-Login (authentication)
- Flask-WTF (form handling)
- WTForms (form validation)

### 2. Set Environment Variables

Create a `.env` file from the template:

```bash
cp .env.example .env
```

Edit `.env` and set:

```env
# Flask Configuration
FLASK_SECRET_KEY=your-very-secure-random-key-here
DATABASE_URL=sqlite:///robin_search.db
FLASK_PORT=5000
FLASK_DEBUG=False  # Set to True for development
```

**⚠️ Security Notes:**
- Generate a strong SECRET_KEY for production
- Use `sqlite:///` for local SQLite or PostgreSQL for production
- Never commit `.env` to version control

### 3. Initialize Database

```bash
python3 -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database initialized!')"
```

## Running the Application

### Development Mode

```bash
python3 app.py
```

Server will start at `http://localhost:5000`

### Production Mode

Using Gunicorn:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## User Flow

### 1. Register
- Navigate to `/register`
- Create account with username, email, password
- Must be at least 6 characters

### 2. Login
- Navigate to `/login`
- Enter credentials
- Optional: "Remember me for 7 days"

### 3. Search & Save
- Access dashboard at `/dashboard`
- Enter search query
- View results from multiple onion search engines
- Click "Save Results" to store in database
- Add tags and notes

### 4. Manage Saved Searches
- View all saved searches on dashboard
- Edit tags/notes
- Delete searches
- Export results

## API Endpoints

All endpoints require authentication (user logged in).

### Authentication

```
POST /register          - Register new user
POST /login             - Login user
GET  /logout            - Logout user
```

### Search

```
POST /api/search        - Perform search
  Body: {
    "query": "search term",
    "engines": ["Ahmia", "Torch"]  // optional
  }
  Returns: {
    "results": [...],
    "stats": {...},
    "count": number
  }
```

### Save Results

```
POST /api/save-results  - Save search results
  Body: {
    "query": "string",
    "refined_query": "string" (optional),
    "results": [...],
    "engine_used": "string" (optional),
    "tags": "tag1,tag2" (optional),
    "notes": "string" (optional)
  }
```

### Retrieve Saved Searches

```
GET  /api/saved-searches                 - List all saved searches
  Params:
    - page: number (default: 1)
    - per_page: number (default: 10)
    - sort_by: "created_at" | "result_count"

GET  /api/saved-searches/<id>            - Get specific search
PUT  /api/saved-searches/<id>            - Update search (notes/tags)
DELETE /api/saved-searches/<id>          - Delete search
```

### Statistics & Management

```
GET  /api/statistics                     - Get user statistics
GET  /api/engines                        - List all search engines
GET  /api/sessions                       - Get search sessions
POST /api/sessions                       - Create new session
```

## Database Schema

### Users Table
```sql
- id (Primary Key)
- username (Unique)
- email (Unique)
- password_hash
- created_at
- is_active
```

### SavedSearch Table
```sql
- id (Primary Key)
- user_id (Foreign Key)
- query
- refined_query
- results (JSON)
- engine_used
- result_count
- tags
- notes
- created_at
- updated_at
```

### SearchStatistics Table
```sql
- id (Primary Key)
- user_id (Foreign Key)
- total_searches
- successful_searches
- failed_searches
- total_results_found
- average_results_per_search
- most_used_engine
- last_search
```

### SearchSession Table
```sql
- id (Primary Key)
- user_id (Foreign Key)
- session_name
- description
- search_data (JSON)
- created_at
- updated_at
```

## Example Usage

### Python Client

```python
import requests
import json

BASE_URL = "http://localhost:5000"
session = requests.Session()

# Login
response = session.post(f"{BASE_URL}/login", data={
    "username": "john_doe",
    "password": "password123"
})

# Search
response = session.post(f"{BASE_URL}/api/search", json={
    "query": "privacy tools"
})
results = response.json()

# Save results
response = session.post(f"{BASE_URL}/api/save-results", json={
    "query": "privacy tools",
    "results": results["results"],
    "tags": "privacy,tools",
    "notes": "Found some useful results"
})

# Get saved searches
response = session.get(f"{BASE_URL}/api/saved-searches")
saved = response.json()
```

### JavaScript Client

```javascript
async function login(username, password) {
    const form = new FormData();
    form.append('username', username);
    form.append('password', password);
    
    return fetch('/login', { method: 'POST', body: form });
}

async function search(query) {
    const response = await fetch('/api/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query })
    });
    return response.json();
}

async function saveResults(query, results, tags) {
    const response = await fetch('/api/save-results', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            query,
            results,
            tags
        })
    });
    return response.json();
}
```

## Features

### ✅ Implemented
- User registration and login
- Search multiple onion engines simultaneously
- Save search results with metadata
- User statistics tracking
- Search history management
- Results filtering and sorting
- Responsive dashboard UI
- RESTful API

### 🚀 Planned
- Advanced search filters
- Result export (CSV, JSON, PDF)
- Search sharing (read-only links)
- Full-text search in saved results
- Email notifications
- API key management
- Admin panel

## Troubleshooting

### Database Errors

**Issue:** "database is locked"
```bash
# Reset database
rm robin_search.db
python3 -c "from app import app, db; app.app_context().push(); db.create_all()"
```

### Login Issues

**Issue:** User can't login after registration
- Check password is at least 6 characters
- Verify user exists: check database
- Clear browser cookies

### Search Not Working

**Issue:** Tor connection fails
- Ensure Tor proxy is running on `127.0.0.1:9050`
- Check network connectivity
- Review logs in terminal

## Security Best Practices

1. **Change SECRET_KEY** in production
2. **Use HTTPS** in production
3. **Enable CSRF protection** (already enabled)
4. **Use strong passwords** (6+ chars, mixed types)
5. **Regular database backups**
6. **Update dependencies** regularly
7. **Monitor access logs**
8. **Rate limit** login attempts

## Performance Optimization

### For Production

```python
# Use PostgreSQL instead of SQLite
DATABASE_URL=postgresql://user:password@localhost/robin

# Use connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
}

# Enable caching
CACHE_TYPE = "simple"
CACHE_DEFAULT_TIMEOUT = 300
```

### Scaling

- Use PostgreSQL for multi-user deployments
- Implement Redis for caching
- Use Gunicorn with multiple workers
- Separate API and web servers
- Use load balancer (nginx)

## Support & Issues

For bugs or feature requests:
1. Check existing issues
2. Provide minimal reproducible example
3. Include error logs
4. Specify Python version and OS
