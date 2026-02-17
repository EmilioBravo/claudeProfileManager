"""Configuration management for Claude Profile Manager."""

import json
import os
import re

CONFIG_DIR = os.path.expanduser("~/.config/claudeProfileManager")
PROFILES_PATH = os.path.join(CONFIG_DIR, "profiles.json")
ACTIVE_ENV_PATH = os.path.join(CONFIG_DIR, "active_env")
CLAUDE_JSON_PATH = os.path.expanduser("~/.claude.json")
CLAUDE_SETTINGS_PATH = os.path.expanduser("~/.claude/settings.json")
CLAUDE_CREDENTIALS_PATH = os.path.expanduser("~/.claude/.credentials.json")

# Environment variables that get set when a profile is activated
ENV_VAR_MAPPING = {
    "LITELLM_PROXY_API_KEY": "api_key",
    "LITELLM_PROXY_URL": "base_url",
    "GEMINI_API_KEY": "api_key",
    "GEMINI_BASE_URL": "base_url",
    "OPENAI_API_KEY": "api_key",
    "OPENAI_BASE_URL": "base_url",
    "ANTHROPIC_AUTH_TOKEN": "api_key",
    "ANTHROPIC_API_KEY": "api_key",
    "ANTHROPIC_BASE_URL": "base_url",
}

# Constant env vars (always set regardless of profile)
CONSTANT_ENV_VARS = {
    "OLLAMA_API_BASE": "http://127.0.0.1:11434",
}

DEFAULT_PROFILES = {
    "active": None,
    "profiles": []
}


def detect_shell_rc():
    """Detect the current shell's rc file path.

    Returns the path to ~/.zshrc or ~/.bashrc based on the SHELL env var.
    Falls back to ~/.bashrc if the shell can't be determined.
    """
    shell = os.environ.get("SHELL", "")
    if shell.endswith("/zsh"):
        return os.path.expanduser("~/.zshrc")
    return os.path.expanduser("~/.bashrc")


def ensure_config_dir():
    """Create config directory if it doesn't exist."""
    os.makedirs(CONFIG_DIR, exist_ok=True)


def load_profiles():
    """Load profiles from JSON file. Returns default structure if not found."""
    if not os.path.exists(PROFILES_PATH):
        return dict(DEFAULT_PROFILES)
    with open(PROFILES_PATH, "r") as f:
        return json.load(f)


def save_profiles(data):
    """Save profiles to JSON file."""
    ensure_config_dir()
    with open(PROFILES_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def profiles_exist():
    """Check if profiles.json exists and has profiles."""
    if not os.path.exists(PROFILES_PATH):
        return False
    data = load_profiles()
    return len(data.get("profiles", [])) > 0


def load_claude_settings():
    """Load Claude Code settings.json."""
    if not os.path.exists(CLAUDE_SETTINGS_PATH):
        return {}
    with open(CLAUDE_SETTINGS_PATH, "r") as f:
        return json.load(f)


def save_claude_settings(settings):
    """Save Claude Code settings.json."""
    os.makedirs(os.path.dirname(CLAUDE_SETTINGS_PATH), exist_ok=True)
    with open(CLAUDE_SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")


def load_claude_credentials():
    """Load OAuth credentials from ~/.claude/.credentials.json.

    Returns dict with credentials or None if not found.
    """
    if not os.path.exists(CLAUDE_CREDENTIALS_PATH):
        return None
    try:
        with open(CLAUDE_CREDENTIALS_PATH, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def save_claude_credentials(credentials):
    """Save OAuth credentials to ~/.claude/.credentials.json."""
    os.makedirs(os.path.dirname(CLAUDE_CREDENTIALS_PATH), exist_ok=True)
    with open(CLAUDE_CREDENTIALS_PATH, "w") as f:
        json.dump(credentials, f, indent=2)
        f.write("\n")
    # Restrict permissions — credentials contain tokens
    os.chmod(CLAUDE_CREDENTIALS_PATH, 0o600)


def remove_claude_credentials():
    """Remove ~/.claude/.credentials.json (for non-OAuth profiles)."""
    if os.path.exists(CLAUDE_CREDENTIALS_PATH):
        os.remove(CLAUDE_CREDENTIALS_PATH)


def update_claude_json_oauth(oauth_account):
    """Update the oauthAccount field in ~/.claude.json and remove apiKeyHelper."""
    if not os.path.exists(CLAUDE_JSON_PATH):
        return
    try:
        with open(CLAUDE_JSON_PATH, "r") as f:
            data = json.load(f)
        data["oauthAccount"] = oauth_account
        # Remove apiKeyHelper so Claude Code uses OAuth instead of API key
        data.pop("apiKeyHelper", None)
        with open(CLAUDE_JSON_PATH, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except (json.JSONDecodeError, OSError):
        pass


def remove_claude_json_oauth():
    """Remove the oauthAccount field from ~/.claude.json."""
    if not os.path.exists(CLAUDE_JSON_PATH):
        return
    try:
        with open(CLAUDE_JSON_PATH, "r") as f:
            data = json.load(f)
        data.pop("oauthAccount", None)
        with open(CLAUDE_JSON_PATH, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
    except (json.JSONDecodeError, OSError):
        pass


def extract_oauth_info():
    """Extract OAuth account info from ~/.claude.json and credentials for storage.

    Returns dict with account info and credentials, or None if not found.
    """
    if not os.path.exists(CLAUDE_JSON_PATH):
        return None

    try:
        with open(CLAUDE_JSON_PATH, "r") as f:
            data = json.load(f)

        oauth = data.get("oauthAccount")
        if not oauth:
            return None

        result = {
            "accountUuid": oauth.get("accountUuid"),
            "organizationUuid": oauth.get("organizationUuid"),
            "emailAddress": oauth.get("emailAddress"),
            "displayName": oauth.get("displayName"),
            "organizationName": oauth.get("organizationName"),
            "organizationRole": oauth.get("organizationRole"),
            "hasExtraUsageEnabled": oauth.get("hasExtraUsageEnabled", False),
            "oauthAccount": oauth,
        }

        # Also capture credentials file if it exists
        credentials = load_claude_credentials()
        if credentials:
            result["credentials"] = credentials

        return result
    except (json.JSONDecodeError, KeyError):
        return None


def detect_shell_keys():
    """Detect LLM API key blocks in the shell rc file for import.

    Scans ~/.bashrc and ~/.zshrc (whichever exist) for export statements.
    """
    rc_candidates = [
        os.path.expanduser("~/.bashrc"),
        os.path.expanduser("~/.zshrc"),
    ]

    content = ""
    source_name = "shell rc"
    for rc_path in rc_candidates:
        if os.path.exists(rc_path):
            with open(rc_path, "r") as f:
                content += f.read() + "\n"
            source_name = os.path.basename(rc_path)

    if not content:
        return []

    profiles = []

    # Look for common patterns: export ANTHROPIC_API_KEY=...
    # Detect FortyAU/LiteLLM proxy config
    litellm_key = re.search(r'export\s+LITELLM_PROXY_API_KEY=["\']?([^"\'\s#]+)', content)
    litellm_url = re.search(r'export\s+LITELLM_PROXY_URL=["\']?([^"\'\s#]+)', content)
    if litellm_key and litellm_url:
        profiles.append({
            "name": "litellm-proxy",
            "description": f"LiteLLM Proxy (imported from {source_name})",
            "type": "api",
            "api_key": litellm_key.group(1),
            "base_url": litellm_url.group(1),
        })

    # Detect direct Anthropic key
    anthropic_key = re.search(r'export\s+ANTHROPIC_API_KEY=["\']?([^"\'\s#]+)', content)
    if anthropic_key:
        key_val = anthropic_key.group(1)
        # Skip if it references another variable like $LITELLM_PROXY_API_KEY
        if not key_val.startswith("$"):
            profiles.append({
                "name": "anthropic-direct",
                "description": f"Anthropic Direct (imported from {source_name})",
                "type": "api",
                "api_key": key_val,
                "base_url": "https://api.anthropic.com",
            })

    # Detect OpenAI key
    openai_key = re.search(r'export\s+OPENAI_API_KEY=["\']?([^"\'\s#]+)', content)
    openai_url = re.search(r'export\s+OPENAI_BASE_URL=["\']?([^"\'\s#]+)', content)
    if openai_key:
        key_val = openai_key.group(1)
        if not key_val.startswith("$"):
            profiles.append({
                "name": "openai-direct",
                "description": f"OpenAI Direct (imported from {source_name})",
                "type": "api",
                "api_key": key_val,
                "base_url": openai_url.group(1) if openai_url else "https://api.openai.com/v1",
            })

    return profiles
