#!/bin/bash
# Uninstallation script for claudeProfileManager
# Removes the global command and optionally cleans up local files

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$HOME/.local/bin"
COMMAND_NAME="claudeProfileManager"
WRAPPER_PATH="$INSTALL_DIR/$COMMAND_NAME"
CONFIG_DIR="$HOME/.config/claudeProfileManager"

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

# Remove shell function from .bashrc
BASHRC="$HOME/.bashrc"
MARKER="# claudeProfileManager shell function"

if [ -f "$BASHRC" ] && grep -qF "$MARKER" "$BASHRC"; then
    # Remove the shell function block (from the marker comment to the closing brace)
    sed -i "/# claudeProfileManager shell function/,/^}/d" "$BASHRC"
    echo "Removed claudeProfileManager shell function from ~/.bashrc"
else
    echo "No shell function found in ~/.bashrc"
fi

echo
echo "========================================================================"
echo "Uninstallation Complete!"
echo "========================================================================"
echo
echo "To completely remove claudeProfileManager, delete the directory:"
echo "  rm -rf $SCRIPT_DIR"
echo
