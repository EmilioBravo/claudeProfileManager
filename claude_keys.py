#!/usr/bin/env python3
"""Claude Profile Manager — manage multiple LLM API key profiles."""

import sys
import os

from config import (
    ACTIVE_ENV_PATH,
    CONSTANT_ENV_VARS,
    ENV_VAR_MAPPING,
    detect_shell_keys,
    detect_shell_rc,
    ensure_config_dir,
    extract_oauth_info,
    load_claude_credentials,
    load_claude_settings,
    load_profiles,
    profiles_exist,
    remove_claude_credentials,
    remove_claude_json_oauth,
    save_claude_credentials,
    save_claude_settings,
    save_profiles,
    update_claude_json_oauth,
)


def find_profile(data, name):
    """Find a profile by name. Returns the profile dict or None."""
    for p in data.get("profiles", []):
        if p["name"] == name:
            return p
    return None


def build_oauth_profile(name, description, oauth_info, model=None):
    """Build an OAuth profile dict from extracted OAuth info."""
    profile = {
        "name": name,
        "description": description or f"Claude Pro - {oauth_info['emailAddress']}",
        "type": "oauth",
        "accountUuid": oauth_info.get("accountUuid"),
        "organizationUuid": oauth_info.get("organizationUuid"),
        "emailAddress": oauth_info.get("emailAddress"),
        "displayName": oauth_info.get("displayName"),
        "organizationName": oauth_info.get("organizationName"),
        "organizationRole": oauth_info.get("organizationRole"),
    }
    if oauth_info.get("credentials"):
        profile["credentials"] = oauth_info["credentials"]
    if oauth_info.get("oauthAccount"):
        profile["oauthAccount"] = oauth_info["oauthAccount"]
    if model:
        profile["model"] = model
    return profile


def _set_settings_env(settings, base_url=None):
    """Update or clean up the env dict in settings for ANTHROPIC_BASE_URL."""
    env = settings.get("env", {})
    if base_url:
        env["ANTHROPIC_BASE_URL"] = base_url
    else:
        env.pop("ANTHROPIC_BASE_URL", None)
    if env:
        settings["env"] = env
    else:
        settings.pop("env", None)


def update_claude_settings(profile=None):
    """Update ~/.claude/settings.json for the active profile.

    For OAuth profiles: Removes apiKeyHelper override (lets Claude use native OAuth)
    For API profiles: Sets apiKeyHelper and ANTHROPIC_BASE_URL
    If profile is None: Removes all managed settings
    """
    settings = load_claude_settings()

    if profile:
        profile_type = profile.get("type", "api")

        if profile_type == "oauth":
            # OAuth profile: Remove overrides, let Claude Code use native OAuth
            settings.pop("apiKeyHelper", None)
            _set_settings_env(settings)
        else:
            # API profile: Set apiKeyHelper and base URL
            if profile.get('api_key'):
                settings["apiKeyHelper"] = f"echo {profile['api_key']}"
            elif profile.get('base_url'):
                # No API key but has base_url (e.g. Ollama) — use a dummy key
                # so Claude Code doesn't fall back to OAuth/login prompt
                settings["apiKeyHelper"] = "echo ollama"
            else:
                settings.pop("apiKeyHelper", None)

            _set_settings_env(settings, profile.get("base_url"))

        # Handle model override (applies to both types)
        model = profile.get("model")
        if model:
            settings["model"] = model
        else:
            settings.pop("model", None)
    else:
        # Clear all managed settings
        settings.pop("apiKeyHelper", None)
        settings.pop("model", None)
        _set_settings_env(settings)

    save_claude_settings(settings)


def write_env_file(profile):
    """Write the sourceable env file for the given profile."""
    ensure_config_dir()
    lines = []
    profile_type = profile.get("type", "api")

    for env_var, field in ENV_VAR_MAPPING.items():
        # For OAuth profiles, unset all LLM provider vars (Claude Code manages OAuth internally)
        if profile_type == "oauth":
            lines.append(f'unset {env_var}')
        # For API key profiles, skip ANTHROPIC_AUTH_TOKEN (only use ANTHROPIC_API_KEY)
        elif profile_type == "api" and env_var == "ANTHROPIC_AUTH_TOKEN":
            lines.append(f'unset {env_var}')
        else:
            value = profile.get(field, "")
            # For profiles with no API key but a base_url (e.g. Ollama),
            # use a dummy key so tools don't reject empty auth
            if not value and field == "api_key" and profile.get("base_url"):
                value = "ollama"
            lines.append(f'export {env_var}="{value}"')

    for env_var, value in CONSTANT_ENV_VARS.items():
        lines.append(f'export {env_var}="{value}"')

    with open(ACTIVE_ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")

    # Handle OAuth credentials
    if profile_type == "oauth":
        # Restore credentials and oauthAccount for OAuth profiles
        credentials = profile.get("credentials")
        if credentials:
            save_claude_credentials(credentials)
        oauth_account = profile.get("oauthAccount")
        if oauth_account:
            update_claude_json_oauth(oauth_account)
    else:
        # Remove OAuth credentials for API key profiles
        remove_claude_credentials()
        remove_claude_json_oauth()

    update_claude_settings(profile)


def clear_env():
    """Write an env file that unsets all LLM-related variables."""
    ensure_config_dir()
    lines = []
    for env_var in ENV_VAR_MAPPING:
        lines.append(f'unset {env_var}')
    for env_var in CONSTANT_ENV_VARS:
        lines.append(f'unset {env_var}')
    with open(ACTIVE_ENV_PATH, "w") as f:
        f.write("\n".join(lines) + "\n")
    remove_claude_credentials()
    remove_claude_json_oauth()
    update_claude_settings(None)
    data = load_profiles()
    data["active"] = None
    save_profiles(data)
    print("Cleared all environment variables.")
    print(f"Environment written to {ACTIVE_ENV_PATH}")


def save_current_oauth_credentials(data):
    """If the currently active profile is OAuth, save fresh credentials back to it.

    Claude Code refreshes OAuth tokens periodically, so we need to capture
    the latest tokens before switching away to avoid restoring stale ones later.
    """
    active = data.get("active")
    if not active:
        return
    p = find_profile(data, active)
    if p and p.get("type") == "oauth":
        credentials = load_claude_credentials()
        if credentials:
            p["credentials"] = credentials
        oauth_info = extract_oauth_info()
        if oauth_info and oauth_info.get("oauthAccount"):
            p["oauthAccount"] = oauth_info["oauthAccount"]
        save_profiles(data)


def switch_profile(name):
    """Switch to the named profile."""
    data = load_profiles()
    profile = find_profile(data, name)
    if not profile:
        print(f"Profile '{name}' not found.")
        return False
    # Save fresh OAuth credentials before switching away
    save_current_oauth_credentials(data)
    data["active"] = name
    save_profiles(data)
    write_env_file(profile)
    print(f"Switched to: {name} ({profile['description']})")
    print(f"Environment written to {ACTIVE_ENV_PATH}")
    return True


def print_profile_list(profiles, active):
    """Print a formatted list of profiles."""
    for i, p in enumerate(profiles, 1):
        marker = "  [ACTIVE]" if p["name"] == active else ""
        profile_type = p.get("type", "api")
        type_badge = " [OAuth]" if profile_type == "oauth" else " [API]"
        print(f"  {i}. {p['name']:<20s}{type_badge:<8s} - {p['description']}{marker}")


def list_profiles():
    """Display all profiles."""
    data = load_profiles()
    active = data.get("active")
    profiles = data.get("profiles", [])
    if not profiles:
        print("No profiles configured. Run 'claudeProfileManager add' to create one.")
        return
    print()
    print_profile_list(profiles, active)
    print()


def show_current():
    """Show the currently active profile."""
    data = load_profiles()
    active = data.get("active")
    if not active:
        print("No active profile.")
        return
    p = find_profile(data, active)
    if not p:
        print(f"{active} (profile data not found)")
        return

    profile_type = p.get("type", "api")
    print(f"{active} ({p['description']})")

    if profile_type == "oauth":
        print(f"  Type: OAuth (Claude Pro Subscription)")
        if p.get("emailAddress"):
            print(f"  Account: {p['emailAddress']}")
        if p.get("organizationName"):
            print(f"  Organization: {p['organizationName']}")
        if p.get("accountUuid"):
            print(f"  Account UUID: {p['accountUuid']}")
        print(f"  Auth: Native Claude Code OAuth (from ~/.claude.json)")
    elif p.get('api_key'):
        print(f"  Type: API Key")
        print(f"  API Key: {p['api_key'][:8]}...{p['api_key'][-4:]}" if len(p['api_key']) > 12 else f"  API Key: {p['api_key']}")
        if p.get('base_url'):
            print(f"  Base URL: {p['base_url']}")
    else:
        print(f"  Type: No Auth (e.g., Ollama)")
        if p.get('base_url'):
            print(f"  Base URL: {p['base_url']}")

    if p.get("model"):
        print(f"  Model: {p['model']}")


def add_profile(exit_on_activate=False):
    """Interactively add a new profile.

    Args:
        exit_on_activate: If True, returns True when profile is activated
    """
    print()
    print("Add new profile")
    print("─" * 40)

    name = input("  Profile name (e.g. claude-direct): ").strip()
    if not name:
        print("Cancelled.")
        return
    # Check for duplicate names
    data = load_profiles()
    if find_profile(data, name):
        print(f"Profile '{name}' already exists.")
        return

    description = input("  Description: ").strip()
    print()
    print("  Profile Types:")
    print("    1. OAuth - Use Claude Pro subscription (via claude code setup-token)")
    print("    2. API Key - Use API key from Anthropic Console or proxy")
    print()
    profile_type = input("  Select type [1/2] (default: 2): ").strip() or "2"

    if profile_type == "1":
        # OAuth profile - extract from ~/.claude.json
        oauth_info = extract_oauth_info()
        if not oauth_info:
            print()
            print("  ERROR: No OAuth account found in ~/.claude.json")
            print("  Run 'claude code setup-token' first to authenticate with Claude Pro.")
            return

        print()
        print(f"  Found OAuth account: {oauth_info['emailAddress']}")
        if oauth_info.get("organizationName"):
            print(f"  Organization: {oauth_info['organizationName']}")
        print()

        model = input("  Claude Code model override (blank for default): ").strip()

        profile = build_oauth_profile(name, description, oauth_info, model)
    else:
        # API key profile
        api_key = input("  API Key (blank for none, e.g. Ollama): ").strip()
        base_url = input("  Base URL (e.g. https://api.anthropic.com): ").strip()
        model = input("  Claude Code model override (blank for default): ").strip()

        profile = {
            "name": name,
            "description": description or name,
            "type": "api",
            "api_key": api_key,
            "base_url": base_url,
        }
        if model:
            profile["model"] = model

    data["profiles"].append(profile)

    # If this is the first profile, make it active
    activated = False
    if len(data["profiles"]) == 1:
        data["active"] = name
        write_env_file(profile)
        print(f"\nProfile '{name}' added and activated (first profile).")
        activated = True
    else:
        print(f"\nProfile '{name}' added.")

    save_profiles(data)

    if exit_on_activate and activated:
        return True
    return False


def remove_profile(name=None, exit_on_switch=False):
    """Remove a profile by name or number, with confirmation.

    Args:
        exit_on_switch: If True, returns True when active profile changes
    """
    data = load_profiles()
    profiles = data.get("profiles", [])
    if not profiles:
        print("No profiles to remove.")
        return False

    if not name:
        list_profiles()
        name = input("Enter profile name or # to remove: ").strip()
        if not name:
            print("Cancelled.")
            return False

    found = None
    # Check if input is a number (index)
    if name.isdigit():
        idx = int(name) - 1
        if 0 <= idx < len(profiles):
            found = idx
            name = profiles[idx]["name"]  # Get the actual profile name for messages
    else:
        # Look up by name
        for i, p in enumerate(profiles):
            if p["name"] == name:
                found = i
                break

    if found is None:
        print(f"Profile '{name}' not found.")
        return False

    try:
        confirm = input(f"Remove profile '{name}'? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return False
    except EOFError:
        # Non-interactive mode (e.g., piped input), proceed without confirmation
        pass

    profiles.pop(found)

    # If we removed the active profile, clear active or set to first remaining
    switched = False
    if data.get("active") == name:
        if profiles:
            data["active"] = profiles[0]["name"]
            write_env_file(profiles[0])
            print(f"Active profile changed to: {profiles[0]['name']}")
            switched = True
        else:
            data["active"] = None
            # Clear the env file
            if os.path.exists(ACTIVE_ENV_PATH):
                os.remove(ACTIVE_ENV_PATH)
            switched = True

    data["profiles"] = profiles
    save_profiles(data)
    print(f"Profile '{name}' removed.")

    return exit_on_switch and switched


def interactive_menu():
    """Show interactive menu for profile management."""
    while True:
        data = load_profiles()
        active = data.get("active")
        profiles = data.get("profiles", [])

        # Find active profile description
        active_profile = find_profile(data, active) if active else None
        active_desc = active_profile["description"] if active_profile else ""

        print()
        print("=" * 45)
        print("  Claude Profile Manager")
        print("=" * 45)

        if active:
            print(f"  Active: {active} ({active_desc})")
        else:
            print("  Active: (none)")
        print()

        if profiles:
            print_profile_list(profiles, active)
        else:
            print("  (no profiles configured)")
        print()
        print("  a. Add new profile")
        print("  r. Remove a profile")
        print("  c. Clear all env variables")
        print("  q. Quit")
        print("─" * 45)

        choice = input("Select profile # or action: ").strip().lower()

        if choice == "q":
            break
        elif choice == "a":
            if add_profile(exit_on_activate=True):
                print("Exiting to apply changes...")
                break
        elif choice == "r":
            if remove_profile(exit_on_switch=True):
                print("Exiting to apply changes...")
                break
        elif choice == "c":
            clear_env()
            print("Exiting to apply changes...")
            break
        elif choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(profiles):
                if switch_profile(profiles[idx]["name"]):
                    # Exit menu so shell function can source the new env
                    print("Exiting to apply changes...")
                    break
            else:
                print("Invalid selection.")
        else:
            print("Invalid choice.")


def first_run():
    """Handle first-run experience: import from .bashrc or create first profile."""
    print()
    print("=" * 45)
    print("  Claude Profile Manager — First Run Setup")
    print("=" * 45)
    print()

    # Try to detect existing keys in shell rc files
    detected = detect_shell_keys()
    if detected:
        print(f"Found {len(detected)} potential profile(s) in shell config:")
        for p in detected:
            print(f"  - {p['name']}: {p['description']}")
            print(f"    Key: {p['api_key'][:8]}...  URL: {p['base_url']}")
        print()
        import_choice = input("Import these profiles? [Y/n]: ").strip().lower()
        if import_choice != "n":
            data = {"active": detected[0]["name"], "profiles": detected}
            save_profiles(data)
            write_env_file(detected[0])
            print(f"\nImported {len(detected)} profile(s). Active: {detected[0]['name']}")
            install_shell_function()
            return

    print("No existing profiles found. Let's create your first profile.")
    print()

    # Create default structure and save so add_profile works
    ensure_config_dir()
    save_profiles(dict(active=None, profiles=[]))
    add_profile()

    install_shell_function()


SHELL_FUNCTION_MARKER = "# claudeProfileManager shell function"
SHELL_FUNCTION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "shell_function.sh")


def install_shell_function():
    """Add the claudeProfileManager shell function to the user's shell rc file."""
    rc_path = detect_shell_rc()
    rc_name = os.path.basename(rc_path)

    if not os.path.exists(rc_path):
        print(f"~/{rc_name} not found — skipping shell function install.")
        return

    with open(rc_path, "r") as f:
        content = f.read()

    if SHELL_FUNCTION_MARKER in content:
        print(f"Shell function already in ~/{rc_name}")
        return

    with open(SHELL_FUNCTION_FILE, "r") as f:
        shell_function_block = f.read()

    with open(rc_path, "a") as f:
        f.write(shell_function_block)

    print(f"Added claudeProfileManager shell function to ~/{rc_name}")
    print(f"Run: source ~/{rc_name}  (or open a new terminal)")


def import_oauth_profile():
    """Import OAuth profile from ~/.claude.json."""
    oauth_info = extract_oauth_info()
    if not oauth_info:
        print()
        print("ERROR: No OAuth account found in ~/.claude.json")
        print("Run 'claude code setup-token' first to authenticate with Claude Pro.")
        return

    print()
    print("Found OAuth Account")
    print("─" * 40)
    print(f"  Email: {oauth_info['emailAddress']}")
    if oauth_info.get("displayName"):
        print(f"  Name: {oauth_info['displayName']}")
    if oauth_info.get("organizationName"):
        print(f"  Organization: {oauth_info['organizationName']}")
    if oauth_info.get("organizationRole"):
        print(f"  Role: {oauth_info['organizationRole']}")
    print()

    name = input("  Profile name (default: claude-pro): ").strip() or "claude-pro"

    # Check for duplicate names
    data = load_profiles()
    if find_profile(data, name):
        print(f"Profile '{name}' already exists.")
        return

    description = input("  Description (default: Claude Pro Subscription): ").strip() or "Claude Pro Subscription"
    model = input("  Claude Code model override (blank for default): ").strip()

    profile = build_oauth_profile(name, description, oauth_info, model)

    data["profiles"].append(profile)
    save_profiles(data)

    print(f"\nOAuth profile '{name}' added.")
    print(f"Use 'claudeProfileManager switch {name}' to activate.")


def main():
    args = sys.argv[1:]

    if not args:
        # Interactive mode
        if not profiles_exist():
            first_run()
        else:
            interactive_menu()
        return

    command = args[0]

    if command == "switch":
        if len(args) < 2:
            print("Usage: claudeProfileManager switch <profile-name>")
            sys.exit(1)
        if not switch_profile(args[1]):
            sys.exit(1)

    elif command == "list":
        list_profiles()

    elif command == "current":
        show_current()

    elif command == "add":
        if not profiles_exist():
            ensure_config_dir()
            save_profiles(dict(active=None, profiles=[]))
        add_profile()

    elif command == "remove":
        name = args[1] if len(args) > 1 else None
        remove_profile(name)

    elif command == "clear":
        clear_env()

    elif command == "import-oauth":
        import_oauth_profile()

    elif command == "help":
        print_usage()

    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


def print_usage():
    """Print usage information."""
    print()
    print("Usage: claudeProfileManager [command]")
    print()
    print("Commands:")
    print("  (none)          Interactive menu")
    print("  switch <name>   Switch to a profile")
    print("  list            List all profiles")
    print("  current         Show active profile")
    print("  add             Add a new profile")
    print("  remove [name]   Remove a profile")
    print("  import-oauth    Import OAuth profile from ~/.claude.json")
    print("  clear           Unset all env variables")
    print("  help            Show this help")
    print()


if __name__ == "__main__":
    main()
