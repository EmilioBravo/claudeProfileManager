#!/bin/bash
# Installation script for claudeProfileManager
# Makes the claudeProfileManager command available globally

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/venv/bin/python3"
MAIN_SCRIPT="$SCRIPT_DIR/claude_keys.py"
INSTALL_DIR="$HOME/.local/bin"
COMMAND_NAME="claudeProfileManager"

# Detect shell rc file
if [ -n "$ZSH_VERSION" ] || [ "$(basename "$SHELL")" = "zsh" ]; then
    SHELL_RC="$HOME/.zshrc"
else
    SHELL_RC="$HOME/.bashrc"
fi
SHELL_RC_NAME="$(basename "$SHELL_RC")"

echo "========================================================================"
echo "Claude Profile Manager Installation"
echo "========================================================================"
echo

# Check if venv exists
if [ ! -d "$SCRIPT_DIR/venv" ]; then
    echo "Virtual environment not found. Creating it now..."
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "Virtual environment created"
fi

# Install dependencies
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing dependencies..."
    "$SCRIPT_DIR/venv/bin/pip" install -q -r "$SCRIPT_DIR/requirements.txt"
    echo "Dependencies installed"
fi
echo

# Create ~/.local/bin if it doesn't exist
mkdir -p "$INSTALL_DIR"

# Create wrapper script
WRAPPER_PATH="$INSTALL_DIR/$COMMAND_NAME"
cat > "$WRAPPER_PATH" <<EOF
#!/bin/bash
# claudeProfileManager launcher
cd "$SCRIPT_DIR"
exec "$VENV_PYTHON" "$MAIN_SCRIPT" "\$@"
EOF

# Make it executable
chmod +x "$WRAPPER_PATH"

echo "Command installed to: $WRAPPER_PATH"
echo

# Check if ~/.local/bin is in PATH
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
    echo "WARNING: $INSTALL_DIR is not in your PATH"
    echo
    echo "Add this line to your ~/$SHELL_RC_NAME:"
    echo
    echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
    echo
    echo "Then run: source ~/$SHELL_RC_NAME"
    echo
else
    echo "$INSTALL_DIR is already in your PATH"
    echo
    echo "You can now run: claudeProfileManager"
fi

# Add shell function to rc file if not already present
MARKER="# claudeProfileManager shell function"
SHELL_FUNC_FILE="$SCRIPT_DIR/shell_function.sh"

if [ -f "$SHELL_RC" ] && grep -qF "$MARKER" "$SHELL_RC"; then
    echo "Shell function already in ~/$SHELL_RC_NAME"
else
    cat "$SHELL_FUNC_FILE" >> "$SHELL_RC"
    echo "Added claudeProfileManager shell function to ~/$SHELL_RC_NAME"
    echo "Run: source ~/$SHELL_RC_NAME  (or open a new terminal)"
fi

echo
echo "========================================================================"
echo "Installation Complete!"
echo "========================================================================"
