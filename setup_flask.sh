#!/bin/bash
# Quick start script for Flask application

echo "🧅 Robin Flask Setup Script"
echo "=============================="
echo ""

# Check Python version
python3 --version || { echo "❌ Python 3 not found"; exit 1; }

# Create virtual environment if needed
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
else
    echo "✓ Virtual environment already exists"
    source venv/bin/activate
fi

# Install/upgrade dependencies
echo "📥 Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create .env if not exists
if [ ! -f ".env" ]; then
    echo "🔧 Creating .env file..."
    cp .env.example .env
    
    # Generate a random secret key
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    echo "FLASK_SECRET_KEY=$SECRET_KEY" >> .env
    echo "✓ Generated SECRET_KEY"
fi

# Initialize database
echo "🗄️  Initializing database..."
python3 << EOF
from app import app, db
with app.app_context():
    db.create_all()
    print("✓ Database initialized")
EOF

# Display next steps
echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file if needed"
echo "2. Run: python3 app.py"
echo "3. Open: http://localhost:5000"
echo "4. Register or login"
echo ""
