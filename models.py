"""Database models for search results and user management."""

from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model for authentication."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    saved_results = db.relationship('SavedSearch', backref='user', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and set password."""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Verify password."""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'


class SavedSearch(db.Model):
    """Model for saving search results."""
    __tablename__ = 'saved_searches'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    query = db.Column(db.String(500), nullable=False)
    refined_query = db.Column(db.String(500))
    results = db.Column(db.JSON, nullable=False)  # Store results as JSON
    engine_used = db.Column(db.String(50))  # Which search engine(s) were used
    result_count = db.Column(db.Integer, default=0)
    tags = db.Column(db.String(500))  # Comma-separated tags
    notes = db.Column(db.Text)  # User notes about this search
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def to_dict(self):
        """Convert to dictionary."""
        return {
            'id': self.id,
            'query': self.query,
            'refined_query': self.refined_query,
            'results': self.results,
            'engine_used': self.engine_used,
            'result_count': self.result_count,
            'tags': self.tags.split(',') if self.tags else [],
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
    
    def __repr__(self):
        return f'<SavedSearch {self.query}>'


class SearchStatistics(db.Model):
    """Model for tracking search statistics and analytics."""
    __tablename__ = 'search_statistics'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    total_searches = db.Column(db.Integer, default=0)
    successful_searches = db.Column(db.Integer, default=0)
    failed_searches = db.Column(db.Integer, default=0)
    total_results_found = db.Column(db.Integer, default=0)
    average_results_per_search = db.Column(db.Float, default=0.0)
    most_used_engine = db.Column(db.String(50))
    last_search = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SearchStatistics user_id={self.user_id}>'


class SearchSession(db.Model):
    """Model for tracking search sessions."""
    __tablename__ = 'search_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    session_name = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    search_data = db.Column(db.JSON)  # Store all session searches as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<SearchSession {self.session_name}>'
