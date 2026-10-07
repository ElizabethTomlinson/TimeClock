#!/usr/bin/env bash
# ==============================================================================
# Time Clock - macOS Application Installer
# Builds and installs Time Clock.app into /Applications or ~/Applications
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Installation target resolution
INSTALL_DIR="/Applications"
if [[ "${1:-}" == "--user" ]]; then
    INSTALL_DIR="$HOME/Applications"
elif [[ -n "${1:-}" && "${1:-}" != --* ]]; then
    INSTALL_DIR="$1"
elif [[ ! -w "/Applications" ]]; then
    echo "Notice: /Applications is not writable without administrative privileges."
    echo "Falling back to user applications directory: $HOME/Applications"
    INSTALL_DIR="$HOME/Applications"
fi

mkdir -p "$INSTALL_DIR"
APP_NAME="Time Clock.app"
APP_BUNDLE="$INSTALL_DIR/$APP_NAME"
CONTENTS_DIR="$APP_BUNDLE/Contents"
MACOS_DIR="$CONTENTS_DIR/MacOS"
RESOURCES_DIR="$CONTENTS_DIR/Resources"

echo "=================================================="
echo "Installing Time Clock to: $APP_BUNDLE"
echo "=================================================="

# 1. Ensure icon assets are generated
if [[ ! -f "$REPO_ROOT/assets/AppIcon.icns" ]]; then
    echo "Generating application icon assets..."
    python3 "$REPO_ROOT/scripts/generate_icon.py"
fi

# Detect Python 3 used during installation
INSTALL_PYTHON=""
if [[ -n "${PYTHON_EXECUTABLE:-}" && -x "$PYTHON_EXECUTABLE" ]]; then
    INSTALL_PYTHON="$PYTHON_EXECUTABLE"
elif command -v python3 >/dev/null 2>&1; then
    INSTALL_PYTHON="$(command -v python3)"
fi

# 2. Create bundle directory hierarchy
mkdir -p "$MACOS_DIR"
mkdir -p "$RESOURCES_DIR/assets"

# 3. Create Info.plist
cat > "$CONTENTS_DIR/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>en</string>
    <key>CFBundleDisplayName</key>
    <string>Time Clock</string>
    <key>CFBundleExecutable</key>
    <string>Time Clock</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.timeclock.desktop</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>CFBundleName</key>
    <string>Time Clock</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>LSMinimumSystemVersion</key>
    <string>10.13.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>NSHumanReadableCopyright</key>
    <string>Time Clock</string>
</dict>
</plist>
EOF

# 4. Create executable launcher script
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
for candidate in "\${CANDIDATES[@]}"; do
    if [ -n "\$candidate" ] && [ -x "\$candidate" ]; then
        if "\$candidate" -c "import tkinter" >/dev/null 2>&1; then
            PYTHON_CMD="\$candidate"
            break
        fi
    fi
done

if [ -z "\$PYTHON_CMD" ]; then
    osascript -e 'display alert "Python 3 Required" message "Time Clock requires Python 3 with Tkinter to run. Please install Python 3 from python.org or Homebrew."'
    exit 1
fi

export PYTHONPATH="\$RESOURCES_DIR:\${PYTHONPATH:-}"
cd "\$RESOURCES_DIR"
exec "\$PYTHON_CMD" "\$RESOURCES_DIR/main.py" "\$@"
EOF

chmod +x "$MACOS_DIR/Time Clock"

# 5. Copy application source files and assets into Resources
echo "Copying application resources..."
rm -rf "$RESOURCES_DIR/time_clock"
cp -R "$REPO_ROOT/time_clock" "$RESOURCES_DIR/"
cp "$REPO_ROOT/main.py" "$RESOURCES_DIR/"

if [[ -f "$REPO_ROOT/assets/AppIcon.icns" ]]; then
    cp "$REPO_ROOT/assets/AppIcon.icns" "$RESOURCES_DIR/"
fi
if [[ -f "$REPO_ROOT/assets/icon.png" ]]; then
    cp "$REPO_ROOT/assets/icon.png" "$RESOURCES_DIR/assets/"
    cp "$REPO_ROOT/assets/icon.png" "$RESOURCES_DIR/"
fi

# 6. Initialize default config and application support directories
mkdir -p "$HOME/Library/Application Support/TimeClock"
mkdir -p "$HOME/.config/time_clock"

# Migrate local repository database if target does not already exist
TARGET_DB="$HOME/Library/Application Support/TimeClock/time_clock.db"
if [[ ! -f "$TARGET_DB" && -f "$REPO_ROOT/data/time_clock.db" ]]; then
    echo "Migrating existing database from data/time_clock.db..."
    cp "$REPO_ROOT/data/time_clock.db" "$TARGET_DB"
fi

# Touch application bundle to refresh Finder cache
touch "$APP_BUNDLE"
xattr -dr com.apple.quarantine "$APP_BUNDLE" 2>/dev/null || true

echo "=================================================="
echo " Installation Complete!"
echo " App location: $APP_BUNDLE"
echo " Database dir: $HOME/Library/Application Support/TimeClock"
echo " Config dir:   $HOME/.config/time_clock"
echo "=================================================="
echo ""
echo "To open Time Clock:"
echo "  - Open Spotlight (Cmd + Space) and type 'Time Clock'"
echo "  - Or open Finder -> Applications -> Time Clock"
echo "  - Drag the app icon from Applications into your Dock to keep it pinned"
echo ""
