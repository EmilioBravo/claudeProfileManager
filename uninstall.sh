#!/bin/bash
# Uninstallation script for claudeProfileManager
# Removes the global command and optionally cleans up local files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
COMMAND_NAME="claudeProfileManager"
WRAPPER_PATH="$INSTALL_DIR/$COMMAND_NAME"
CONFIG_DIR="$HOME/.config/claudeProfileManager"

# Detect shell rc file
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
else
    SHELL_RC="$HOME/.bashrc"
fi
SHELL_RC_NAME="$(basename "$SHELL_RC")"

echo "========================================================================"
echo "Claude Profile Manager Uninstallation"
echo "========================================================================"
echo

# Remove the global command
if [ -f "$WRAPPER_PATH" ]; then
    rm "$WRAPPER_PATH"
    echo "Removed global command: $WRAPPER_PATH"
else
    echo "Global command not found at: $WRAPPER_PATH"
fi

echo

# Ask about removing virtual environment
read -p "Remove virtual environment (venv)? [y/N]: " remove_venv
if [[ "$remove_venv" =~ ^[Yy]$ ]]; then
    if [ -d "$SCRIPT_DIR/venv" ]; then
        rm -rf "$SCRIPT_DIR/venv"
        echo "Removed virtual environment"
    else
        echo "Virtual environment not found"
    fi
else
    echo "Kept virtual environment"
fi

echo

# Ask about removing config directory
read -p "Remove config directory ($CONFIG_DIR)? [y/N]: " remove_config
if [[ "$remove_config" =~ ^[Yy]$ ]]; then
    if [ -d "$CONFIG_DIR" ]; then
        rm -rf "$CONFIG_DIR"
        echo "Removed config directory"
    else
        echo "Config directory not found"
    fi
else
    echo "Kept config directory (contains your profiles)"
fi

# Remove shell function from rc file
MARKER="# claudeProfileManager shell function"

if [ -f "$SHELL_RC" ] && grep -qF "$MARKER" "$SHELL_RC"; then
    # Use portable sed -i syntax (macOS BSD sed requires '' arg, GNU sed does not)
    if sed --version >/dev/null 2>&1; then
        # GNU sed
        sed -i "/$MARKER/,/^}/d" "$SHELL_RC"
    else
        # BSD sed (macOS)
        sed -i '' "/$MARKER/,/^}/d" "$SHELL_RC"
    fi
    echo "Removed claudeProfileManager shell function from ~/$SHELL_RC_NAME"
else
    echo "No shell function found in ~/$SHELL_RC_NAME"
fi

echo
echo "========================================================================"
echo "Uninstallation Complete!"
echo "========================================================================"
echo
echo "To completely remove claudeProfileManager, delete the directory:"
echo "  rm -rf $SCRIPT_DIR"
echo
