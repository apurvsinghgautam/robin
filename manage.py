#!/usr/bin/env python3
"""
CLI tool for managing Robin Flask application and database.
"""

import sys
import argparse
from app import app, db
from models import User, SavedSearch, SearchStatistics


def init_db():
    """Initialize database."""
    with app.app_context():
        db.create_all()
        print("✓ Database initialized")


def create_user():
    """Create a new user."""
    with app.app_context():
        username = input("Username: ").strip()
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        
        if not all([username, email, password]):
            print("❌ All fields are required")
            return
        
        if len(password) < 6:
            print("❌ Password must be at least 6 characters")
            return
        
        if User.query.filter_by(username=username).first():
            print("❌ Username already exists")
            return
        
        user = User(username=username, email=email)
        user.set_password(password)
        
        try:
            db.session.add(user)
            stats = SearchStatistics(user_id=user.id)
            db.session.add(stats)
            db.session.commit()
            print(f"✓ User '{username}' created successfully")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {str(e)}")


def list_users():
    """List all users."""
    with app.app_context():
        users = User.query.all()
        if not users:
            print("No users found")
            return
        
        print(f"\n{'ID':<5} {'Username':<20} {'Email':<30} {'Created':<20} {'Active':<8}")
        print("-" * 85)
        for user in users:
            print(f"{user.id:<5} {user.username:<20} {user.email:<30} "
                  f"{user.created_at.strftime('%Y-%m-%d %H:%M'):<20} "
                  f"{'Yes' if user.is_active else 'No':<8}")


def delete_user():
    """Delete a user."""
    with app.app_context():
        username = input("Username to delete: ").strip()
        user = User.query.filter_by(username=username).first()
        
        if not user:
            print(f"❌ User '{username}' not found")
            return
        
        confirm = input(f"Delete user '{username}' and all their data? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled")
            return
        
        try:
            # Delete related data
            SavedSearch.query.filter_by(user_id=user.id).delete()
            SearchStatistics.query.filter_by(user_id=user.id).delete()
            db.session.delete(user)
            db.session.commit()
            print(f"✓ User '{username}' deleted")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {str(e)}")


def user_stats():
    """Show statistics for all users."""
    with app.app_context():
        print("\n{'Username':<20} {'Searches':<12} {'Results':<12} {'Avg/Search':<12}")
        print("-" * 58)
        
        users = User.query.all()
        for user in users:
            stats = SearchStatistics.query.filter_by(user_id=user.id).first()
            if stats:
                avg = round(stats.average_results_per_search, 1)
                print(f"{user.username:<20} {stats.total_searches:<12} "
                      f"{stats.total_results_found:<12} {avg:<12}")


def reset_db():
    """Reset database (DANGEROUS!)."""
    confirm = input("⚠️  This will DELETE ALL DATA. Type 'YES' to confirm: ").strip()
    if confirm != 'YES':
        print("Cancelled")
        return
    
    with app.app_context():
        try:
            db.drop_all()
            db.create_all()
            print("✓ Database reset")
        except Exception as e:
            print(f"❌ Error: {str(e)}")


def export_data():
    """Export user data."""
    with app.app_context():
        import json
        from datetime import datetime
        
        users = User.query.all()
        data = []
        
        for user in users:
            user_data = {
                'username': user.username,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'searches': []
            }
            
            searches = SavedSearch.query.filter_by(user_id=user.id).all()
            for search in searches:
                user_data['searches'].append({
                    'query': search.query,
                    'result_count': search.result_count,
                    'created_at': search.created_at.isoformat(),
                    'tags': search.tags
                })
            
            data.append(user_data)
        
        filename = f"robin_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✓ Data exported to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description='Robin Flask Application Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python3 manage.py init-db              Initialize database
  python3 manage.py create-user          Create new user (interactive)
  python3 manage.py list-users           List all users
  python3 manage.py delete-user          Delete user (interactive)
  python3 manage.py stats                Show user statistics
  python3 manage.py export-data          Export all data to JSON
  python3 manage.py reset-db             Reset database (DANGEROUS!)
        '''
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    subparsers.add_parser('init-db', help='Initialize database')
    subparsers.add_parser('create-user', help='Create new user')
    subparsers.add_parser('list-users', help='List all users')
    subparsers.add_parser('delete-user', help='Delete user')
    subparsers.add_parser('stats', help='Show user statistics')
    subparsers.add_parser('export-data', help='Export data to JSON')
    subparsers.add_parser('reset-db', help='Reset database')
    
    args = parser.parse_args()
    
    commands = {
        'init-db': init_db,
        'create-user': create_user,
        'list-users': list_users,
        'delete-user': delete_user,
        'stats': user_stats,
        'export-data': export_data,
        'reset-db': reset_db,
    }
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
    
    if args.command in commands:
        commands[args.command]()
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
