#!/bin/bash
# OffGridPro Setup Script

echo "⚡ OffGridPro Setup"

# Create virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate venv
source venv/bin/activate

# Install Flask and SocketIO
echo "Installing dependencies..."
pip install Flask Flask-SocketIO

# Create templates folder if not exists
mkdir -p templates

# Create web_app.py
cat > web_app.py <<'EOF'
[PASTE THE FULL web_app.py CONTENT HERE]
EOF

# Create dashboard.html
cat > templates/dashboard.html <<'EOF'
[PASTE THE FULL dashboard.html CONTENT HERE]
EOF

# Syntax check Python
echo "Verifying Python syntax..."
python3 -m py_compile web_app.py
if [ $? -eq 0 ]; then
    echo "✅ Python syntax OK"
else
    echo "❌ Python syntax error – check web_app.py"
    exit 1
fi

echo "✅ Setup complete!"
echo "Run: python3 web_app.py"
