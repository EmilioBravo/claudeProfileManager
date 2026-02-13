# claudeProfileManager — Claude Profile Manager

Manage multiple LLM API key profiles from the command line. Switch between Anthropic, OpenAI, LiteLLM proxies, and local Ollama with a single command.

## Quick Start

```bash
# Install globally
./install.sh

# Run interactive menu
claudeProfileManager

# Or run directly
python3 claude_keys.py
```

## Usage

### Interactive Mode (default)

```
$ claudeProfileManager

=============================================
  Claude Profile Manager
=============================================
  Active: claude-direct (Luis Escobar Claude Direct)

  1. fortyau-litellm      - FortyAU LiteLLM Proxy
  2. claude-direct         - Luis Escobar Claude Direct  [ACTIVE]
  3. ollama-local          - Local Ollama

  a. Add new profile
  r. Remove a profile
  q. Quit
---------------------------------------------
Select profile # or action:
```

### CLI Commands

```bash
claudeProfileManager switch <name>   # Switch to a profile
claudeProfileManager list            # List all profiles
claudeProfileManager current         # Show active profile
claudeProfileManager add             # Add a new profile
claudeProfileManager remove [name]   # Remove a profile
claudeProfileManager help            # Show usage
```

## Shell Integration

The shell function is automatically added to `~/.bashrc` on first run or install. It auto-sources environment variables when you switch profiles:

```bash
claudeProfileManager() {
    command claudeProfileManager "$@"
    if [ -f ~/.config/claudeProfileManager/active_env ]; then
        source ~/.config/claudeProfileManager/active_env
    fi
}
```

## Environment Variables

When a profile is activated, these environment variables are set:

| Variable | Value |
|----------|-------|
| `LITELLM_PROXY_API_KEY` | Profile API key |
| `LITELLM_PROXY_URL` | Profile base URL |
| `GEMINI_API_KEY` | Profile API key |
| `GEMINI_BASE_URL` | Profile base URL |
| `OPENAI_API_KEY` | Profile API key |
| `OPENAI_BASE_URL` | Profile base URL |
| `ANTHROPIC_AUTH_TOKEN` | Profile API key |
| `ANTHROPIC_API_KEY` | Profile API key |
| `ANTHROPIC_BASE_URL` | Profile base URL |
| `OLLAMA_API_BASE` | Always `http://127.0.0.1:11434` |

## Installation

```bash
./install.sh
```

This creates a virtual environment and installs `claudeProfileManager` to `~/.local/bin/`.

## Uninstallation

```bash
./uninstall.sh
```
