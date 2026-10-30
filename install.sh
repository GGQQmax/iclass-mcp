#!/usr/bin/env bash
#
# iclass-mcp Installation Script for Linux & macOS
#

set -e

# Terminal colors
if [ -t 1 ]; then
    GREEN='\033[0;32m'
    BLUE='\033[0;34m'
    YELLOW='\033[1;33m'
    RED='\033[0;31m'
    BOLD='\033[1m'
    NC='\033[0m'
else
    GREEN=''
    BLUE=''
    YELLOW=''
    RED=''
    BOLD=''
    NC=''
fi

info() {
    echo -e "${BLUE}[*]${NC} $1"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1"
}

error() {
    echo -e "${RED}[✗]${NC} $1"
    exit 1
}

# Resolve script root directory
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
ROOT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
cd "$ROOT_DIR"

INSTALL_VIDEO="prompt"
INSTALL_WHISPER="prompt"

for arg in "$@"; do
    case "$arg" in
        --with-video|--video)
            INSTALL_VIDEO="yes"
            ;;
        --no-video)
            INSTALL_VIDEO="no"
            ;;
        --whisper)
            INSTALL_VIDEO="yes"
            INSTALL_WHISPER="yes"
            ;;
        --help|-h)
            echo "Usage: ./install.sh [options]"
            echo "Options:"
            echo "  --with-video, --video    Install optional Video-to-Text pipeline dependencies"
            echo "  --no-video               Skip Video-to-Text pipeline dependencies"
            echo "  --whisper                Install video pipeline with faster-whisper STT backend"
            exit 0
            ;;
    esac
done

echo -e "${BOLD}========================================${NC}"
echo -e "${BOLD}       iclass-mcp Installer           ${NC}"
echo -e "${BOLD}========================================${NC}"
info "Working directory: $ROOT_DIR"

# 1. Check Git submodules
info "Checking Git submodules..."
if [ -d "$ROOT_DIR/.git" ] && command -v git >/dev/null 2>&1; then
    if git submodule update --init --recursive 2>/dev/null; then
        success "Git submodules initialized / updated."
    elif [ -f "$ROOT_DIR/api/iclass_api.py" ]; then
        warn "Could not update Git submodules via git (possibly read-only or offline). Using existing api/ files."
    else
        error "Failed to initialize Git submodules. Please check your network and git permissions."
    fi
elif [ -f "$ROOT_DIR/api/iclass_api.py" ]; then
    success "API submodule files present."
else
    error "The 'api' directory is missing or incomplete. Please run: git submodule update --init --recursive"
fi

# 2. Check Python version (>= 3.10)
info "Checking Python version..."
PYTHON_BIN=""

for cmd in python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)
        if [ -n "$PY_VER" ]; then
            MAJOR=$(echo "$PY_VER" | cut -d. -f1)
            MINOR=$(echo "$PY_VER" | cut -d. -f2)
            if [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 10 ]; then
                PYTHON_BIN="$cmd"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    error "Python 3.10 or higher is required. Please install Python 3.10+ and re-run this script."
fi

PY_FULL_VER=$("$PYTHON_BIN" --version 2>&1)
success "Found suitable Python: $PYTHON_BIN ($PY_FULL_VER)"

# 3. Create Virtual Environment
VENV_DIR="$ROOT_DIR/.venv"
VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_PYTHON" ]; then
    info "Creating virtual environment in $VENV_DIR..."
    "$PYTHON_BIN" -m venv "$VENV_DIR"
    success "Virtual environment created."
else
    info "Virtual environment already exists."
fi

# 4. Install Dependencies
info "Installing / updating base dependencies..."
"$VENV_PIP" install --upgrade pip --quiet 2>/dev/null || true
if ! "$VENV_PIP" install -r "$ROOT_DIR/requirements.txt" 2>/dev/null; then
    if "$VENV_PIP" install --no-index -r "$ROOT_DIR/requirements.txt" >/dev/null 2>&1; then
        info "Dependencies satisfied from local cache."
    else
        error "Failed to install dependencies from requirements.txt. Please check your internet connection."
    fi
fi
success "Base dependencies installed successfully."

# Optional Video-to-Text Pipeline
if [ "$INSTALL_VIDEO" = "prompt" ]; then
    if [ -t 0 ]; then
        echo ""
        read -r -p "Install optional Video-to-Text lecture notes pipeline (extract slides, OCR, speech transcription)? [y/N]: " USER_CHOICE_VIDEO
        if [[ "$USER_CHOICE_VIDEO" =~ ^[Yy]$ ]]; then
            INSTALL_VIDEO="yes"
        else
            INSTALL_VIDEO="no"
        fi
    else
        INSTALL_VIDEO="no"
    fi
fi

if [ "$INSTALL_VIDEO" = "yes" ]; then
    info "Installing Video-to-Text dependencies from requirements-video.txt..."
    if "$VENV_PIP" install -r "$ROOT_DIR/requirements-video.txt"; then
        success "Video pipeline dependencies installed successfully."
    else
        warn "Could not install all video dependencies from requirements-video.txt."
    fi

    if [ "$INSTALL_WHISPER" = "prompt" ] && [ -t 0 ]; then
        read -r -p "Install local speech-to-text backend ('faster-whisper')? [y/N]: " USER_CHOICE_WHISPER
        if [[ "$USER_CHOICE_WHISPER" =~ ^[Yy]$ ]]; then
            INSTALL_WHISPER="yes"
        else
            INSTALL_WHISPER="no"
        fi
    fi

    if [ "$INSTALL_WHISPER" = "yes" ]; then
        info "Installing faster-whisper..."
        "$VENV_PIP" install "faster-whisper>=1.0.0" || warn "Failed to install faster-whisper."
    fi

    # Check external system tools
    echo ""
    info "Checking external system tools for video pipeline..."
    if command -v ffmpeg >/dev/null 2>&1; then
        success "Found ffmpeg: $(command -v ffmpeg)"
    else
        warn "ffmpeg is not found. Video/audio extraction requires ffmpeg."
        echo "       Install ffmpeg via your system package manager (e.g. 'sudo dnf install ffmpeg' or 'sudo apt install ffmpeg')."
    fi

    if command -v tesseract >/dev/null 2>&1; then
        success "Found tesseract: $(command -v tesseract)"
        if tesseract --list-langs 2>/dev/null | grep -q "chi_tra"; then
            success "Found Traditional Chinese OCR pack (chi_tra)."
        else
            warn "Traditional Chinese OCR pack (chi_tra) not found in tesseract."
            echo "       For best slide OCR results in Chinese, install: 'sudo dnf install tesseract-langpack-chi_tra' or 'sudo apt install tesseract-ocr-chi-tra'."
        fi
    else
        warn "tesseract is not found. Slide OCR requires tesseract."
        echo "       Install tesseract via: 'sudo dnf install tesseract tesseract-langpack-chi_tra' or 'sudo apt install tesseract-ocr tesseract-ocr-chi-tra'."
    fi
fi

# 5. Configure .env Credentials
ENV_FILE="$ROOT_DIR/.env"
ENV_TEMPLATE="$ROOT_DIR/.env.template"

if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$ENV_TEMPLATE" ]; then
        cp "$ENV_TEMPLATE" "$ENV_FILE"
        info "Created .env from .env.template"
    else
        touch "$ENV_FILE"
    fi

    if [ -t 0 ]; then
        echo ""
        read -r -p "Would you like to configure your TKU iClass credentials now? [y/N]: " SETUP_CREDS
        if [[ "$SETUP_CREDS" =~ ^[Yy]$ ]]; then
            read -r -p "Enter TKU Student ID: " USERNAME_INPUT
            read -r -s -p "Enter TKU SSO Password: " PASSWORD_INPUT
            echo ""

            # Update .env
            cat > "$ENV_FILE" <<EOF
USERNAMEID="$USERNAME_INPUT"
PASSWORD="$PASSWORD_INPUT"
EOF
            success "Saved credentials to .env."
        else
            warn "Please remember to set USERNAMEID and PASSWORD in '$ENV_FILE' before running the server."
        fi
    else
        warn "Non-interactive shell: Please edit '$ENV_FILE' with your student ID and password."
    fi
else
    success ".env configuration file already exists."
fi

# 6. Update .codex/config.toml with absolute paths
CODEX_CONFIG="$ROOT_DIR/.codex/config.toml"
if [ -f "$CODEX_CONFIG" ]; then
    cat > "$CODEX_CONFIG" <<EOF
[mcp_servers.iclass]
command = "$VENV_PYTHON"
args = ["iclass_mcp_server.py"]
cwd = "$ROOT_DIR"
default_tools_approval_mode = "prompt"
EOF
    success "Updated .codex/config.toml with current paths."
fi

# 7. Helper to configure Claude Desktop or Antigravity
OS_TYPE="$(uname -s)"
CLAUDE_CONFIG=""
if [ "$OS_TYPE" = "Darwin" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
elif [ "$OS_TYPE" = "Linux" ]; then
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
fi

ANTIGRAVITY_CONFIG="$HOME/.gemini/config/mcp_config.json"

add_mcp_to_json_config() {
    local config_file="$1"
    local client_name="$2"

    if [ -z "$config_file" ]; then
        return
    fi

    mkdir -p "$(dirname "$config_file")"

    "$VENV_PYTHON" - <<EOF
import json, os

config_path = os.path.expanduser("$config_file")
server_cmd = "$VENV_PYTHON"
server_file = os.path.join("$ROOT_DIR", "iclass_mcp_server.py")
cwd = "$ROOT_DIR"

data = {}
if os.path.exists(config_path):
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = {}

if "mcpServers" not in data:
    data["mcpServers"] = {}

data["mcpServers"]["iclass"] = {
    "command": server_cmd,
    "args": [server_file],
    "cwd": cwd
}

with open(config_path, "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("success")
EOF
    success "Successfully registered iclass in $client_name ($config_file)"
}

if [ -t 0 ]; then
    echo ""
    echo -e "${BOLD}Optional MCP Client Integration:${NC}"
    
    # Check Claude Desktop
    if [ -n "$CLAUDE_CONFIG" ]; then
        read -r -p "Add iclass to Claude Desktop config? [y/N]: " CONFIGURE_CLAUDE
        if [[ "$CONFIGURE_CLAUDE" =~ ^[Yy]$ ]]; then
            add_mcp_to_json_config "$CLAUDE_CONFIG" "Claude Desktop"
        fi
    fi

    # Check Antigravity
    read -r -p "Add iclass to Antigravity config? [y/N]: " CONFIGURE_ANTIGRAVITY
    if [[ "$CONFIGURE_ANTIGRAVITY" =~ ^[Yy]$ ]]; then
        add_mcp_to_json_config "$ANTIGRAVITY_CONFIG" "Antigravity"
    fi
fi

# 8. Print Manual Configuration Snippets
echo ""
echo -e "${BOLD}========================================${NC}"
echo -e "${GREEN}${BOLD} Installation Complete!                ${NC}"
echo -e "${BOLD}========================================${NC}"
echo ""
echo "MCP Client Configuration JSON:"
echo -e "${YELLOW}{
  \"mcpServers\": {
    \"iclass\": {
      \"command\": \"$VENV_PYTHON\",
      \"args\": [\"$ROOT_DIR/iclass_mcp_server.py\"],
      \"cwd\": \"$ROOT_DIR\"
    }
  }
}${NC}"
echo ""
echo "To test the MCP server manually, run:"
echo "  $VENV_PYTHON $ROOT_DIR/iclass_mcp_server.py"
echo ""
