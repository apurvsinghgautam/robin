"""Flask application with authentication and search results database."""

from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import json
import os
from functools import wraps

from models import db, User, SavedSearch, SearchStatistics, SearchSession
from search import get_search_results, SEARCH_ENGINES

# Initialize Flask app
app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///robin_search.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Initialize extensions
db.init_app(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'

# Create tables
with app.app_context():
    db.create_all()


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID."""
    return User.query.get(int(user_id))


# ============================================================================
# AUTHENTICATION ROUTES
# ============================================================================

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validation
        if not all([username, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400
        
        if len(username) < 3:
            return jsonify({'error': 'Username must be at least 3 characters'}), 400
        
        if password != confirm_password:
            return jsonify({'error': 'Passwords do not match'}), 400
        
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Check if user exists
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already exists'}), 409
        
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        # Create user
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            db.session.commit()
            
            # Create statistics record
            stats = SearchStatistics(user_id=user.id)
            db.session.add(stats)
            db.session.commit()
            
            login_user(user)
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            return jsonify({'error': 'Username and password required'}), 400
        
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session.permanent = True
            app.permanent_session_lifetime = timedelta(days=7)
            login_user(user, remember=request.form.get('remember'))
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('dashboard'))
        
        return jsonify({'error': 'Invalid username or password'}), 401
    
    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """User logout."""
    logout_user()
    return redirect(url_for('login'))


# ============================================================================
# MAIN PAGE & DASHBOARD
# ============================================================================

@app.route('/')
def index():
    """Home page - redirect to login/dashboard."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard - main page."""
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    # Get user's saved searches
    saved_searches = SavedSearch.query.filter_by(user_id=current_user.id)\
        .order_by(SavedSearch.created_at.desc())\
        .paginate(page=page, per_page=per_page)
    
    # Get user statistics
    stats = SearchStatistics.query.filter_by(user_id=current_user.id).first()
    
    return render_template(
        'dashboard.html',
        user=current_user,
        saved_searches=saved_searches,
        stats=stats
    )


# ============================================================================
# API ROUTES FOR SEARCH FUNCTIONALITY
# ============================================================================

@app.route('/api/search', methods=['POST'])
@login_required
def api_search():
    """Search API endpoint."""
    data = request.get_json() or request.form
    query = data.get('query', '').strip()
    engines = data.get('engines')  # Optional: specific engines
    
    if not query:
        return jsonify({'error': 'Query is required'}), 400
    
    try:
        # Perform search
        results, search_stats = get_search_results(query, stats=True)
        
        # Update user statistics
        stats = SearchStatistics.query.filter_by(user_id=current_user.id).first()
        if stats:
            stats.total_searches += 1
            stats.successful_searches += 1
            stats.total_results_found += len(results)
            stats.last_search = datetime.utcnow()
            if len(results) > 0:
                stats.average_results_per_search = stats.total_results_found / stats.total_searches
            db.session.commit()
        
        return jsonify({
            'success': True,
            'results': results,
            'stats': search_stats,
            'count': len(results)
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/save-results', methods=['POST'])
@login_required
def api_save_results():
    """Save search results to database."""
    data = request.get_json()
    
    required_fields = ['query', 'results']
    if not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields: query, results'}), 400
    
    try:
        # Convert results to JSON-serializable format if needed
        results = data.get('results', [])
        if isinstance(results, str):
            results = json.loads(results)
        
        saved_search = SavedSearch(
            user_id=current_user.id,
            query=data.get('query'),
            refined_query=data.get('refined_query'),
            results=results,
            engine_used=data.get('engine_used'),
            result_count=len(results),
            tags=data.get('tags'),
            notes=data.get('notes')
        )
        
        db.session.add(saved_search)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Results saved successfully',
            'saved_search_id': saved_search.id
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to save results: {str(e)}'}), 500


@app.route('/api/saved-searches', methods=['GET'])
@login_required
def api_saved_searches():
    """Get user's saved searches."""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    sort_by = request.args.get('sort_by', 'created_at')  # created_at, result_count
    
    query = SavedSearch.query.filter_by(user_id=current_user.id)
    
    # Sorting
    if sort_by == 'result_count':
        query = query.order_by(SavedSearch.result_count.desc())
    else:
        query = query.order_by(SavedSearch.created_at.desc())
    
    paginated = query.paginate(page=page, per_page=per_page)
    
    return jsonify({
        'success': True,
        'searches': [s.to_dict() for s in paginated.items],
        'total': paginated.total,
        'pages': paginated.pages,
        'current_page': page
    })


@app.route('/api/saved-searches/<int:search_id>', methods=['GET', 'PUT', 'DELETE'])
@login_required
def api_saved_search(search_id):
    """Get, update, or delete a specific saved search."""
    saved_search = SavedSearch.query.get_or_404(search_id)
    
    # Authorization check
    if saved_search.user_id != current_user.id:
        return jsonify({'error': 'Unauthorized'}), 403
    
    if request.method == 'GET':
        return jsonify({'success': True, 'search': saved_search.to_dict()})
    
    elif request.method == 'PUT':
        data = request.get_json()
        
        if 'notes' in data:
            saved_search.notes = data['notes']
        if 'tags' in data:
            saved_search.tags = ','.join(data['tags']) if isinstance(data['tags'], list) else data['tags']
        
        try:
            saved_search.updated_at = datetime.utcnow()
            db.session.commit()
            return jsonify({'success': True, 'search': saved_search.to_dict()})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500
    
    elif request.method == 'DELETE':
        try:
            db.session.delete(saved_search)
            db.session.commit()
            return jsonify({'success': True, 'message': 'Search deleted'})
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500


@app.route('/api/engines', methods=['GET'])
@login_required
def api_engines():
    """Get list of available search engines."""
    return jsonify({
        'success': True,
        'engines': SEARCH_ENGINES,
        'total': len(SEARCH_ENGINES),
        'active': sum(1 for e in SEARCH_ENGINES if e.get('active', True))
    })


@app.route('/api/statistics', methods=['GET'])
@login_required
def api_statistics():
    """Get user's search statistics."""
    stats = SearchStatistics.query.filter_by(user_id=current_user.id).first()
    
    if not stats:
        return jsonify({'error': 'Statistics not found'}), 404
    
    return jsonify({
        'success': True,
        'statistics': {
            'total_searches': stats.total_searches,
            'successful_searches': stats.successful_searches,
            'failed_searches': stats.failed_searches,
            'total_results_found': stats.total_results_found,
            'average_results_per_search': round(stats.average_results_per_search, 2),
            'most_used_engine': stats.most_used_engine,
            'last_search': stats.last_search.isoformat() if stats.last_search else None,
        }
    })


@app.route('/api/sessions', methods=['GET', 'POST'])
@login_required
def api_sessions():
    """Get or create search sessions."""
    if request.method == 'GET':
        sessions = SearchSession.query.filter_by(user_id=current_user.id)\
            .order_by(SearchSession.created_at.desc()).all()
        return jsonify({
            'success': True,
            'sessions': [
                {
                    'id': s.id,
                    'name': s.session_name,
                    'description': s.description,
                    'created_at': s.created_at.isoformat(),
                    'updated_at': s.updated_at.isoformat(),
                } for s in sessions
            ]
        })
    
    elif request.method == 'POST':
        data = request.get_json()
        name = data.get('name', '').strip()
        
        if not name:
            return jsonify({'error': 'Session name is required'}), 400
        
        try:
            session_obj = SearchSession(
                user_id=current_user.id,
                session_name=name,
                description=data.get('description'),
                search_data={}
            )
            db.session.add(session_obj)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'session_id': session_obj.id,
                'message': 'Session created'
            }), 201
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': str(e)}), 500


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('FLASK_PORT', 5000)),
        debug=os.getenv('FLASK_DEBUG', 'False') == 'True'
    )
