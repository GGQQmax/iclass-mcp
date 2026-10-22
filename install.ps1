#
# iclass-mcp Installation Script for Windows
# Requires PowerShell 5.1 or later
#

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[*] $Message" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[✓] $Message" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[!] $Message" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Message)
    Write-Host "[✗] $Message" -ForegroundColor Red
    exit 1
}

$ROOT_DIR = $PSScriptRoot
Set-Location -Path $ROOT_DIR

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "       iclass-mcp Installer (Windows)   " -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Info "Working directory: $ROOT_DIR"

# 1. Check Git submodules
Write-Info "Checking Git submodules..."
if ((Test-Path "$ROOT_DIR\.git") -and (Get-Command git -ErrorAction SilentlyContinue)) {
    try {
        & git submodule update --init --recursive 2>$null
        Write-Success "Git submodules initialized / updated."
    } catch {
        if (Test-Path "$ROOT_DIR\api\iclass_api.py") {
            Write-Warn "Could not update Git submodules via git. Using existing api/ files."
        } else {
            Write-Err "Failed to initialize Git submodules. Please check network/git permissions."
        }
    }
} elseif (Test-Path "$ROOT_DIR\api\iclass_api.py") {
    Write-Success "API submodule files present."
} else {
    Write-Err "The 'api' directory is missing or incomplete. Please run: git submodule update --init --recursive"
}

# 2. Check Python version (>= 3.10)
Write-Info "Searching for Python 3.10+..."
$PythonExe = $null
$PythonArgs = @()

if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $ver = & py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge [version]"3.10") {
            $PythonExe = "py"
            $PythonArgs = @("-3")
        }
    } catch {}
}

if (-not $PythonExe -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
        $ver = & python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge [version]"3.10") {
            $PythonExe = "python"
            $PythonArgs = @()
        }
    } catch {}
}

if (-not $PythonExe -and (Get-Command python3 -ErrorAction SilentlyContinue)) {
    try {
        $ver = & python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>$null
        if ($ver -and [version]$ver -ge [version]"3.10") {
            $PythonExe = "python3"
            $PythonArgs = @()
        }
    } catch {}
}

if (-not $PythonExe) {
    Write-Err "Python 3.10 or higher could not be found. Please install Python from https://www.python.org/ or the Microsoft Store."
}

$pyVerStr = & $PythonExe @PythonArgs --version 2>&1
Write-Success "Found suitable Python: $PythonExe ($pyVerStr)"

# 3. Create Virtual Environment
$VENV_DIR = Join-Path $ROOT_DIR ".venv"
$VENV_PYTHON = Join-Path $VENV_DIR "Scripts\python.exe"
$VENV_PIP = Join-Path $VENV_DIR "Scripts\pip.exe"

if (-not (Test-Path $VENV_PYTHON)) {
    Write-Info "Creating virtual environment in $VENV_DIR..."
    & $PythonExe @PythonArgs -m venv $VENV_DIR
    Write-Success "Virtual environment created."
} else {
    Write-Info "Virtual environment already exists."
}

# 4. Install Dependencies
Write-Info "Installing / updating dependencies..."
try {
    & $VENV_PIP install --upgrade pip --quiet 2>$null
} catch {}

$pipFailed = $false
try {
    & $VENV_PIP install -r (Join-Path $ROOT_DIR "requirements.txt") 2>$null
    if ($LASTEXITCODE -ne 0) { $pipFailed = $true }
} catch {
    $pipFailed = $true
}

if ($pipFailed) {
    try {
        & $VENV_PIP install --no-index -r (Join-Path $ROOT_DIR "requirements.txt") 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Err "Failed to install dependencies from requirements.txt. Please check your internet connection."
        }
        Write-Info "Dependencies satisfied from local cache."
    } catch {
        Write-Err "Failed to install dependencies from requirements.txt. Please check your internet connection."
    }
}
Write-Success "Dependencies installed successfully."

# 5. Configure .env Credentials
$ENV_FILE = Join-Path $ROOT_DIR ".env"
$ENV_TEMPLATE = Join-Path $ROOT_DIR ".env.template"

if (-not (Test-Path $ENV_FILE)) {
    if (Test-Path $ENV_TEMPLATE) {
        Copy-Item -Path $ENV_TEMPLATE -Destination $ENV_FILE
        Write-Info "Created .env from .env.template"
    } else {
        New-Item -ItemType File -Path $ENV_FILE -Force | Out-Null
    }

    $setupCreds = Read-Host "Would you like to configure your TKU iClass credentials now? (y/N)"
    if ($setupCreds -match "^[Yy]$") {
        $studentId = Read-Host "Enter TKU Student ID"
        $secPassword = Read-Host "Enter TKU SSO Password" -AsSecureString
        $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secPassword)
        $password = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
        [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

        $envContent = @"
USERNAMEID="$studentId"
PASSWORD="$password"
"@
        Set-Content -Path $ENV_FILE -Value $envContent -Encoding utf8
        Write-Success "Saved credentials to .env."
    } else {
        Write-Warn "Please remember to set USERNAMEID and PASSWORD in '$ENV_FILE' before running the server."
    }
} else {
    Write-Success ".env configuration file already exists."
}

# 6. Update .codex/config.toml with absolute paths
$CODEX_CONFIG = Join-Path $ROOT_DIR ".codex\config.toml"
if (Test-Path $CODEX_CONFIG) {
    $venvPyPosix = $VENV_PYTHON.Replace('\', '/')
    $rootPosix = $ROOT_DIR.Replace('\', '/')
    $codexContent = @"
[mcp_servers.iclass]
command = "$venvPyPosix"
args = ["iclass_mcp_server.py"]
cwd = "$rootPosix"
default_tools_approval_mode = "prompt"
"@
    Set-Content -Path $CODEX_CONFIG -Value $codexContent -Encoding utf8
    Write-Success "Updated .codex/config.toml with current paths."
}

# 7. Helper to configure Claude Desktop
$CLAUDE_CONFIG = Join-Path $env:APPDATA "Claude\claude_desktop_config.json"

function Add-McpToClaude {
    param([string]$ConfigFile)
    
    $configDir = Split-Path -Parent $ConfigFile
    if (-not (Test-Path $configDir)) {
        New-Item -ItemType Directory -Path $configDir -Force | Out-Null
    }

    $jsonObj = [ordered]@{}
    if (Test-Path $ConfigFile) {
        try {
            $raw = Get-Content -Path $ConfigFile -Raw -Encoding utf8
            $jsonObj = $raw | ConvertFrom-Json
        } catch {
            $jsonObj = [ordered]@{}
        }
    }

    if (-not $jsonObj.mcpServers) {
        $jsonObj | Add-Member -MemberType NoteProperty -Name "mcpServers" -Value ([ordered]@{}) -Force
    }

    $serverEntry = [ordered]@{
        command = $VENV_PYTHON.Replace('\', '/')
        args = @((Join-Path $ROOT_DIR "iclass_mcp_server.py").Replace('\', '/'))
        cwd = $ROOT_DIR.Replace('\', '/')
    }

    if ($jsonObj.mcpServers -is [PSCustomObject]) {
        $jsonObj.mcpServers | Add-Member -MemberType NoteProperty -Name "iclass" -Value $serverEntry -Force
    } else {
        $jsonObj.mcpServers["iclass"] = $serverEntry
    }

    $jsonOut = $jsonObj | ConvertTo-Json -Depth 10
    Set-Content -Path $ConfigFile -Value $jsonOut -Encoding utf8
    Write-Success "Successfully registered iclass in Claude Desktop ($ConfigFile)"
}

$configureClaude = Read-Host "Add iclass to Claude Desktop config? (y/N)"
if ($configureClaude -match "^[Yy]$") {
    try {
        Add-McpToClaude -ConfigFile $CLAUDE_CONFIG
    } catch {
        Write-Warn "Could not automatically update Claude Desktop config: $_"
    }
}

# 8. Output summary banner
$escapedPy = $VENV_PYTHON.Replace('\', '\\')
$escapedServer = (Join-Path $ROOT_DIR "iclass_mcp_server.py").Replace('\', '\\')
$escapedRoot = $ROOT_DIR.Replace('\', '\\')

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Installation Complete!                 " -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "MCP Client Configuration JSON:" -ForegroundColor White
Write-Host @"
{
  "mcpServers": {
    "iclass": {
      "command": "$escapedPy",
      "args": ["$escapedServer"],
      "cwd": "$escapedRoot"
    }
  }
}
"@ -ForegroundColor Yellow
Write-Host ""
Write-Host "To test the MCP server manually, run:"
Write-Host "  & `"$VENV_PYTHON`" `"$escapedServer`""
Write-Host ""
