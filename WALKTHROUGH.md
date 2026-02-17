# Claude Profile Manager — Code Walkthrough

A function-by-function guide to how the application works.

## Table of Contents

- [High-Level Flow](#high-level-flow)
- [File: config.py — Configuration & I/O](#file-configpy)
- [File: claude_keys.py — CLI & Profile Logic](#file-claude_keyspy)
- [File: shell_function.sh — Shell Integration](#file-shell_functionsh)
- [File: claudeProfileManager — Bash Launcher](#file-claudeprofilemanager)
- [File: install.sh — Installer](#file-installsh)
- [File: uninstall.sh — Uninstaller](#file-uninstallsh)

---

## High-Level Flow

When a user runs `claudeProfileManager switch my-profile`, here's what happens:

1. `main()` parses args and calls `switch_profile("my-profile")`
2. `switch_profile()` loads profiles from disk, saves fresh OAuth tokens from any outgoing OAuth profile, then marks the new profile active
3. `write_env_file()` writes a sourceable bash file (`active_env`) with `export`/`unset` statements for all LLM env vars
4. `update_claude_settings()` patches `~/.claude/settings.json` with `apiKeyHelper`, `model`, and `ANTHROPIC_BASE_URL`
5. For OAuth profiles: credentials are restored to `~/.claude/.credentials.json` and `oauthAccount` is set in `~/.claude.json`
6. The shell wrapper function (in `.bashrc` or `.zshrc`) auto-sources `active_env` so env vars apply to the current shell

---

## File: config.py

This file handles all disk I/O, path constants, and config file management. It has zero business logic — it just reads and writes files.

### Constants

```python
CONFIG_DIR     = "~/.config/claudeProfileManager"
PROFILES_PATH  = CONFIG_DIR + "/profiles.json"
ACTIVE_ENV_PATH = CONFIG_DIR + "/active_env"
CLAUDE_JSON_PATH = "~/.claude.json"
CLAUDE_SETTINGS_PATH = "~/.claude/settings.json"
CLAUDE_CREDENTIALS_PATH = "~/.claude/.credentials.json"
```

```python
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

CONSTANT_ENV_VARS = {
    "OLLAMA_API_BASE": "http://127.0.0.1:11434",
}
```

`ENV_VAR_MAPPING` maps each environment variable name to which profile field it reads from (`api_key` or `base_url`). Every profile's key and URL get broadcast to all supported providers. `CONSTANT_ENV_VARS` are always set regardless of profile (Ollama's local endpoint).

### `ensure_config_dir()`

Creates `~/.config/claudeProfileManager/` if it doesn't exist (`os.makedirs` with `exist_ok=True`).

### `load_profiles()`

Reads `profiles.json` from disk. If the file doesn't exist, returns the default structure: `{"active": None, "profiles": []}`. No validation — trusts the JSON.

### `save_profiles(data)`

Writes the profile data dict to `profiles.json` with `indent=2` formatting. Calls `ensure_config_dir()` first so the directory is guaranteed to exist.

### `profiles_exist()`

Returns `True` if `profiles.json` exists on disk **and** contains at least one profile. Used by `main()` to decide whether to run first-run setup or the interactive menu.

### `load_claude_settings()`

Reads `~/.claude/settings.json`. Returns an empty dict if the file doesn't exist. This is Claude Code's own settings file.

### `save_claude_settings(settings)`

Writes the settings dict to `~/.claude/settings.json`. Creates the `~/.claude/` directory if needed.

### `load_claude_credentials()`

Reads `~/.claude/.credentials.json` (OAuth tokens). Returns `None` if the file doesn't exist or can't be parsed. Used to capture fresh tokens before switching away from an OAuth profile.

### `save_claude_credentials(credentials)`

Writes OAuth credentials to `~/.claude/.credentials.json` and sets file permissions to `0o600` (owner-only read/write) since it contains tokens.

### `remove_claude_credentials()`

Deletes `~/.claude/.credentials.json`. Called when switching **to** an API key profile so Claude Code doesn't try to use stale OAuth tokens.

### `update_claude_json_oauth(oauth_account)`

Reads `~/.claude.json`, sets the `oauthAccount` field to the given dict, and removes any `apiKeyHelper` field. This tells Claude Code to use OAuth authentication. Silently no-ops if the file doesn't exist or can't be parsed.

### `remove_claude_json_oauth()`

Reads `~/.claude.json` and removes the `oauthAccount` field. Called when switching to an API key profile.

### `extract_oauth_info()`

Reads `~/.claude.json` and extracts the `oauthAccount` object along with credentials from `~/.claude/.credentials.json`. Returns a dict with `accountUuid`, `organizationUuid`, `emailAddress`, `displayName`, `organizationName`, `organizationRole`, `oauthAccount` (the full object), and `credentials`. Returns `None` if no OAuth account is found.

### `detect_shell_rc()`

Detects the current shell's rc file path by checking the `SHELL` environment variable. Returns `~/.zshrc` for zsh, `~/.bashrc` for everything else.

### `detect_shell_keys()`

Scans both `~/.bashrc` and `~/.zshrc` (whichever exist) for `export` lines that set LLM API keys. Uses regex to detect three patterns:
- **LiteLLM proxy**: looks for `LITELLM_PROXY_API_KEY` + `LITELLM_PROXY_URL`
- **Anthropic direct**: looks for `ANTHROPIC_API_KEY` (skips variable references like `$LITELLM_PROXY_API_KEY`)
- **OpenAI direct**: looks for `OPENAI_API_KEY` and optionally `OPENAI_BASE_URL`

Returns a list of profile dicts ready to be imported. Used during first-run setup.

---

## File: claude_keys.py

This is the main entry point. It contains all CLI commands, the interactive menu, and the profile switching logic.

### `find_profile(data, name)`

Linear search through `data["profiles"]` for a profile with a matching `name` field. Returns the profile dict or `None`. Used throughout the codebase whenever a profile needs to be looked up.

### `build_oauth_profile(name, description, oauth_info, model=None)`

Constructs a profile dict for an OAuth profile from the extracted OAuth info. Sets `type: "oauth"` and copies account fields (`accountUuid`, `emailAddress`, etc.). Conditionally includes `credentials`, `oauthAccount`, and `model` if they exist.

### `_set_settings_env(settings, base_url=None)`

Helper that manages the `env` dict inside Claude Code's `settings.json`. If a `base_url` is provided, sets `env.ANTHROPIC_BASE_URL`. If not, removes it. Cleans up the `env` key entirely if the dict becomes empty. Keeps `settings.json` tidy.

### `update_claude_settings(profile=None)`

The central function for patching `~/.claude/settings.json`. Three modes:

- **OAuth profile**: Removes `apiKeyHelper` (lets Claude Code use native OAuth) and clears `ANTHROPIC_BASE_URL`
- **API profile**: Sets `apiKeyHelper` to `echo <key>` (or `echo ollama` for keyless providers), and sets `ANTHROPIC_BASE_URL` if the profile has a `base_url`
- **`profile=None`**: Clears all managed settings (used by `clear_env()`)

Also handles `model` override for all profile types — sets or removes the `model` key.

### `write_env_file(profile)`

Writes `~/.config/claudeProfileManager/active_env`, a bash-sourceable file. For each entry in `ENV_VAR_MAPPING`:

- **OAuth profiles**: writes `unset VAR` for every var (Claude Code manages auth internally)
- **API profiles**: writes `export VAR="value"` using the profile's `api_key`/`base_url`, except `ANTHROPIC_AUTH_TOKEN` which is always unset

Also writes `CONSTANT_ENV_VARS` (Ollama endpoint).

After writing the env file, handles OAuth credentials:
- **OAuth**: restores `~/.claude/.credentials.json` and updates `oauthAccount` in `~/.claude.json`
- **API**: removes credentials file and clears `oauthAccount`

Finally calls `update_claude_settings(profile)`.

### `clear_env()`

Writes an env file that `unset`s every known LLM variable. Removes OAuth credentials, clears Claude settings, sets `active` to `None`, and saves. Used by the `clear` CLI command.

### `save_current_oauth_credentials(data)`

If the currently active profile is OAuth, reads the **latest** credentials from disk and saves them back into the profile data. This is important because Claude Code refreshes OAuth tokens periodically — without this step, switching away from an OAuth profile would discard fresh tokens, and switching back would restore stale ones.

### `switch_profile(name)`

The main profile-switching function:
1. Loads profiles from disk
2. Looks up the target profile by name
3. Calls `save_current_oauth_credentials()` to preserve fresh tokens from the outgoing profile
4. Updates `active` in the profile data
5. Calls `write_env_file()` which does all the real work (env file, settings, credentials)
6. Prints confirmation

Returns `True` on success, `False` if the profile wasn't found.

### `print_profile_list(profiles, active)`

Formats and prints a numbered list of profiles. Each line shows: number, name (left-padded to 20 chars), type badge (`[API]` or `[OAuth]`), description, and `[ACTIVE]` marker if applicable.

### `list_profiles()`

Loads profiles and calls `print_profile_list()`. Prints a helpful message if no profiles exist.

### `show_current()`

Displays detailed info about the active profile. Shows different fields based on type:
- **OAuth**: account email, organization, UUID, auth method
- **API with key**: masked API key (first 8 + last 4 chars), base URL
- **API without key**: base URL only (e.g., Ollama)
- **All types**: model override if set

### `add_profile(exit_on_activate=False)`

Interactive profile creation flow:
1. Prompts for name and description
2. Checks for duplicate names
3. Asks for profile type (OAuth or API key)
4. **OAuth path**: calls `extract_oauth_info()` to pull from `~/.claude.json`, shows account details, builds profile via `build_oauth_profile()`
5. **API path**: prompts for API key, base URL, and model override
6. Appends the new profile to the list
7. If it's the first profile, auto-activates it and writes the env file

The `exit_on_activate` parameter lets the interactive menu know it should exit (so the shell function can source the new env).

### `remove_profile(name=None, exit_on_switch=False)`

Removes a profile by name or number:
1. If no name given, shows the profile list and prompts
2. Accepts either a profile name or a 1-based index number
3. Asks for confirmation (skips in non-interactive/piped mode via `EOFError` catch)
4. If the removed profile was active, switches to the first remaining profile (or clears everything if none left)

The `exit_on_switch` parameter tells the interactive menu to exit when the active profile changes.

### `interactive_menu()`

The main menu loop. Displays:
- Header with active profile name and description
- Numbered profile list
- Options: (a)dd, (r)emove, (c)lear, (q)uit

Entering a number switches to that profile. The loop breaks after any action that changes the active profile (switch, add first profile, remove active, clear) so the shell wrapper can source the updated env file.

### `first_run()`

Handles the first-run experience when no `profiles.json` exists:
1. Calls `detect_shell_keys()` to scan for existing API keys in `.bashrc`/`.zshrc`
2. If keys found, offers to import them as profiles
3. If declined or none found, calls `add_profile()` to create the first profile
4. Calls `install_shell_function()` to set up the shell wrapper

### `install_shell_function()`

Detects the user's shell via `detect_shell_rc()` and appends `shell_function.sh` to the appropriate rc file (`~/.bashrc` or `~/.zshrc`) if the marker comment (`# claudeProfileManager shell function`) isn't already present. Skips if the rc file doesn't exist.

### `import_oauth_profile()`

Standalone command to import an OAuth profile from `~/.claude.json`:
1. Calls `extract_oauth_info()` to read the current OAuth account
2. Displays account details (email, name, org, role)
3. Prompts for profile name (default: `claude-pro`) and description
4. Checks for duplicate names
5. Builds and saves the profile via `build_oauth_profile()`

Does **not** auto-activate — prints a hint to use `switch` instead.

### `main()`

Entry point. Parses `sys.argv`:

| Command | Action |
|---------|--------|
| *(none)* | `first_run()` or `interactive_menu()` based on `profiles_exist()` |
| `switch <name>` | `switch_profile(name)` |
| `list` | `list_profiles()` |
| `current` | `show_current()` |
| `add` | `add_profile()` (creates empty profiles.json if needed) |
| `remove [name]` | `remove_profile(name)` |
| `clear` | `clear_env()` |
| `import-oauth` | `import_oauth_profile()` |
| `help` | `print_usage()` |

Unknown commands print usage and exit with code 1.

### `print_usage()`

Prints a formatted help message listing all available commands and their descriptions.

---

## File: shell_function.sh

```bash
claudeProfileManager() {
    command claudeProfileManager "$@"
    source ~/.config/claudeProfileManager/active_env
}
```

This shell function wraps the real `claudeProfileManager` binary. After the Python script finishes (which writes `active_env` to disk), the function sources it into the current shell. Without this wrapper, env vars would only exist in the Python subprocess and be lost when it exits. The syntax is compatible with both bash and zsh.

The `command` keyword ensures the real binary is called, not the function recursively.

---

## File: claudeProfileManager (Bash Launcher)

```bash
cd "$(dirname "$0")"
venv/bin/python3 claude_keys.py "$@"
```

Development launcher. Changes to the project directory (so relative imports work) and runs `claude_keys.py` through the venv Python. Passes all args through.

---

## File: install.sh

The installer does four things:
1. **Creates a venv** in the project directory if one doesn't exist, and installs any `requirements.txt` deps
2. **Creates a wrapper script** at `~/.local/bin/claudeProfileManager` that `cd`s to the project dir and runs `claude_keys.py` via the venv Python
3. **Checks PATH** and warns if `~/.local/bin` isn't in it
4. **Appends the shell function** from `shell_function.sh` to the detected shell rc file (`~/.bashrc` or `~/.zshrc`)

---

## File: uninstall.sh

The uninstaller:
1. **Removes** `~/.local/bin/claudeProfileManager`
2. **Optionally removes** the venv directory (prompts user)
3. **Optionally removes** `~/.config/claudeProfileManager/` (prompts user)
4. **Removes the shell function** from the detected rc file using `sed` to delete from the marker comment to the closing `}` (uses portable `sed -i` that works on both GNU/Linux and BSD/macOS)
5. Prints a hint to manually delete the project directory
