#!/bin/bash
set -e

# TVRecTopic Installation Script for Ubuntu

echo "Starting Installation..."

# 1. System Dependencies
echo "[1/5] Installing System Dependencies..."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg build-essential curl ca-certificates gnupg git pkg-config

# Install Node.js (LTS) via NodeSource
echo "Installing Node.js LTS from NodeSource..."
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# 2. Backend Setup
echo "[2/5] Setting up Backend..."
PROJECT_ROOT=$(pwd)
cd backend

# Create entry point for package mode
touch __init__.py

# Create Virtual Env
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

source venv/bin/activate

# Install Python Requirements
pip install --upgrade pip
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo "requirements.txt not found!"
    exit 1
fi

# Create default settings.json if missing
if [ ! -f "settings.json" ]; then
    echo "Creating default local settings.json..."
    mkdir -p "$HOME/Videos/tvrectopic"
    cat <<EOF > settings.json
{
    "recording_folder": "$HOME/Videos/tvrectopic",
    "filename_format": "{Title}_{Date}_{Time}_{Channel}.ts",
    "tuner_count_shared": 0,
    "ssh_host": null,
    "gemini_api_key": ""
}
EOF
else
    # Ensure it's configured for local if desired (manual step usually, but we can hint)
    echo "Found existing settings.json. Please ensure 'ssh_host' is null/removed for local recording."
fi

# Run DB Migrations
# Run DB Migrations (Disabled by user request)
# echo "Running DB Migrations..."
# if [ -f "migrate_db_v2.py" ]; then
#     python3 migrate_db_v2.py || echo "Warning: Migration v2 failed or already applied."
# else
#    echo "migrate_db_v2.py not found in backend/. Skipping."
# fi

cd "$PROJECT_ROOT"

# 2.5 Compile Caption2Ass
echo "[2.5/5] Compiling Caption2Ass..."
if [ -d "cap_src" ]; then
    cd cap_src
    make clean
    make
    if [ -f "Caption2Ass" ]; then
        echo "Caption2Ass compiled successfully."
        # Create cap directory if not exists
        mkdir -p ../cap
        mv Caption2Ass ../cap/
    else
        echo "WARNING: Caption2Ass compilation failed."
    fi
    cd "$PROJECT_ROOT"
else
    echo "WARNING: cap_src directory not found. Skipping Caption2Ass compilation."
fi

# 3. Frontend Setup
echo "[3/5] Setting up Frontend..."
cd frontend

# Install Node Modules
npm install

# Build for Production
npm run build

cd "$PROJECT_ROOT"

# 4. Systemd Service Setup
echo "[4/5] Configuring Systemd Service..."
SERVICE_NAME="tvrectopic"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
REAL_USER=${SUDO_USER:-$(whoami)}
USER_NAME=$REAL_USER
WORKING_DIR="$PROJECT_ROOT/backend"
PYTHON_EXEC="$WORKING_DIR/venv/bin/python"

# Create Service File
sudo bash -c "cat <<EOF > $SERVICE_FILE
[Unit]
Description=TVRecTopic Backend Service
After=network.target

[Service]
User=$USER_NAME
WorkingDirectory=$PROJECT_ROOT
ExecStart=$PYTHON_EXEC -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF"

# 5. Finish
echo "[5/5] Finalizing..."
sudo systemctl daemon-reload

# Check for Rec tools
REC_TOOLS=""
if command -v recdvb &> /dev/null; then REC_TOOLS="recdvb "; fi
if command -v recpt1 &> /dev/null; then REC_TOOLS="${REC_TOOLS}recpt1 "; fi

# Fix Permissions
if [ -n "$SUDO_USER" ]; then
    echo "Fixing file permissions for user: $SUDO_USER"
    sudo chown -R "$SUDO_USER":"$SUDO_USER" "$PROJECT_ROOT"
fi

echo "---------------------------------------------------"
echo "Installation Complete!"
echo ""
if [ -n "$REC_TOOLS" ]; then
    echo "Detected tuner tools: $REC_TOOLS"
else
    echo "WARNING: No tuner tools (recdvb/recpt1) detected in PATH."
    echo "Please install tuner drivers and tools separately."
fi
echo ""
echo "To start the service, run:"
echo "  sudo systemctl enable --now $SERVICE_NAME"
echo ""
echo "Access the web interface at: http://localhost:8000"
echo "Check logs with: sudo journalctl -u $SERVICE_NAME -f"
echo "---------------------------------------------------"
