#!/usr/bin/env bash
# ==============================================================================
# Time Clock - macOS Application Updater
# Updates code and assets in /Applications/Time Clock.app without modifying database or config
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Target resolution
TARGET_APP=""
if [[ -n "${1:-}" && "${1:-}" != --* ]]; then
    TARGET_APP="$1"
elif [[ -d "/Applications/Time Clock.app" ]]; then
    TARGET_APP="/Applications/Time Clock.app"
elif [[ -d "$HOME/Applications/Time Clock.app" ]]; then
    TARGET_APP="$HOME/Applications/Time Clock.app"
else
    echo "Error: No installed 'Time Clock.app' found in /Applications or ~/Applications."
    echo "Please run ./scripts/install_macos.sh first to install the application."
    exit 1
fi

CONTENTS_DIR="$TARGET_APP/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

if [[ ! -d "$MACOS_DIR" || ! -d "$RESOURCES_DIR" ]]; then
    echo "Error: Target $TARGET_APP does not appear to be a valid Time Clock bundle."
    exit 1
fi

echo "=================================================="
echo "Updating Time Clock at: $TARGET_APP"
echo "=================================================="

# 1. Regenerate icon assets if needed
if [[ ! -f "$REPO_ROOT/assets/AppIcon.icns" ]]; then
    echo "Generating latest application icon assets..."
    python3 "$REPO_ROOT/scripts/generate_icon.py"
fi

# 2. Update Launcher executable and Resources
echo "Syncing updated launcher and application code..."

# Detect Python 3 used during update
INSTALL_PYTHON=""
if [[ -n "${PYTHON_EXECUTABLE:-}" && -x "$PYTHON_EXECUTABLE" ]]; then
    INSTALL_PYTHON="$PYTHON_EXECUTABLE"
elif command -v python3 >/dev/null 2>&1; then
    INSTALL_PYTHON="$(command -v python3)"
fi

# Ensure Python requirements are updated in execution environment
if [[ -n "$INSTALL_PYTHON" && -f "$REPO_ROOT/requirements.txt" ]]; then
    echo "Verifying application dependencies with $INSTALL_PYTHON..."
    "$INSTALL_PYTHON" -m pip install --quiet -r "$REPO_ROOT/requirements.txt" || \
    "$INSTALL_PYTHON" -m pip install --user --quiet -r "$REPO_ROOT/requirements.txt" || \
    "$INSTALL_PYTHON" -m pip install --user --break-system-packages --quiet -r "$REPO_ROOT/requirements.txt" || true

    if ! "$INSTALL_PYTHON" -c "import customtkinter" >/dev/null 2>&1; then
        echo "Error: Failed to install required dependencies into $INSTALL_PYTHON." >&2
        echo "Please install dependencies manually using:" >&2
        echo "    $INSTALL_PYTHON -m pip install -r \"$REPO_ROOT/requirements.txt\"" >&2
        exit 1
    fi
fi

cat > "$MACOS_DIR/Time Clock" << EOF
#!/bin/bash
set -e

LAUNCHER_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
APP_DIR="\$(cd "\$LAUNCHER_DIR/../.." && pwd)"
RESOURCES_DIR="\$APP_DIR/Contents/Resources"

# Detect Python 3 runtime (prefer modern Tk 8.6+/9+ runtimes over deprecated system Tk 8.5)
CANDIDATES=(
    "\${PYTHON_EXECUTABLE:-}"
    "$INSTALL_PYTHON"
    "\$(command -v python3 2>/dev/null || true)"
    "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.14/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.12/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.11/bin/python3"
    "/Library/Frameworks/Python.framework/Versions/3.10/bin/python3"
    "/opt/homebrew/bin/python3"
    "/usr/local/bin/python3"
    "\$HOME/.pyenv/shims/python3"
    "\$HOME/miniconda3/bin/python3"
    "\$HOME/anaconda3/bin/python3"
    "\$HOME/.local/bin/python3"
    "/usr/bin/python3"
)

PYTHON_CMD=""
# Pass 1: Prefer candidate that already has both tkinter and customtkinter working
for candidate in "\${CANDIDATES[@]}"; do
    if [ -n "\$candidate" ] && [ -x "\$candidate" ]; then
        if "\$candidate" -c "import tkinter, customtkinter" >/dev/null 2>&1; then
            PYTHON_CMD="\$candidate"
            break
        fi
    fi
done

# Pass 2: Fallback to any candidate with tkinter
if [ -z "\$PYTHON_CMD" ]; then
    for candidate in "\${CANDIDATES[@]}"; do
        if [ -n "\$candidate" ] && [ -x "\$candidate" ]; then
            if "\$candidate" -c "import tkinter" >/dev/null 2>&1; then
                PYTHON_CMD="\$candidate"
                break
            fi
        fi
    done
fi

if [ -z "\$PYTHON_CMD" ]; then
    osascript -e 'display alert "Python 3 Required" message "Time Clock requires Python 3 with Tkinter to run. Please install Python 3 from python.org or Homebrew."'
    exit 1
fi

# Ensure customtkinter dependency is present in selected runtime
if ! "\$PYTHON_CMD" -c "import customtkinter" >/dev/null 2>&1; then
    if [ -f "\$RESOURCES_DIR/requirements.txt" ]; then
        "\$PYTHON_CMD" -m pip install --quiet -r "\$RESOURCES_DIR/requirements.txt" >/dev/null 2>&1 || \
        "\$PYTHON_CMD" -m pip install --user --quiet -r "\$RESOURCES_DIR/requirements.txt" >/dev/null 2>&1 || \
        "\$PYTHON_CMD" -m pip install --user --break-system-packages --quiet -r "\$RESOURCES_DIR/requirements.txt" >/dev/null 2>&1 || true
    fi
fi

if ! "\$PYTHON_CMD" -c "import customtkinter" >/dev/null 2>&1; then
    osascript -e "display alert \"CustomTkinter Dependency Required\" message \"Time Clock requires the 'customtkinter' library. Please install it using:\n\$PYTHON_CMD -m pip install -r '\$RESOURCES_DIR/requirements.txt'\""
    exit 1
fi

export PYTHONPATH="\$RESOURCES_DIR:\${PYTHONPATH:-}"
cd "\$RESOURCES_DIR"
exec "\$PYTHON_CMD" "\$RESOURCES_DIR/main.py" "\$@"
EOF

chmod +x "$MACOS_DIR/Time Clock"

rm -rf "$RESOURCES_DIR/time_clock"
cp -R "$REPO_ROOT/time_clock" "$RESOURCES_DIR/"
cp "$REPO_ROOT/main.py" "$RESOURCES_DIR/"
if [[ -f "$REPO_ROOT/requirements.txt" ]]; then
    cp "$REPO_ROOT/requirements.txt" "$RESOURCES_DIR/"
fi

if [[ -f "$REPO_ROOT/assets/AppIcon.icns" ]]; then
    cp "$REPO_ROOT/assets/AppIcon.icns" "$RESOURCES_DIR/"
fi
if [[ -f "$REPO_ROOT/assets/icon.png" ]]; then
    mkdir -p "$RESOURCES_DIR/assets"
    cp "$REPO_ROOT/assets/icon.png" "$RESOURCES_DIR/assets/"
    cp "$REPO_ROOT/assets/icon.png" "$RESOURCES_DIR/"
fi

# 3. Touch bundle to invalidate system caches
touch "$TARGET_APP"

echo "=================================================="
echo " Update Complete!"
echo " Application updated at: $TARGET_APP"
echo " User data and configuration remain untouched at:"
echo "   Database: $HOME/Library/Application Support/TimeClock"
echo "   Config:   $HOME/.config/time_clock"
echo "=================================================="
