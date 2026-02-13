# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**claudeProfileManager** is a Python CLI tool to manage multiple LLM API key profiles. It allows switching between different LLM providers (Anthropic, OpenAI, LiteLLM proxies, Ollama, Claude Pro OAuth) by writing environment variables to a sourceable file and updating Claude Code's own settings.

## Architecture

Flat structure, interactive-first, JSON config, bash launcher.

### Key Files

| File | Purpose |
|------|---------|
| `claude_keys.py` | Main entry point — CLI commands, interactive menu, profile switching logic |
| `config.py` | Config paths, env var mapping, profile I/O, OAuth credential management, `.bashrc` detection |
| `claudeProfileManager` | Bash launcher for local development |
| `install.sh` | Creates venv, installs to `~/.local/bin/claudeProfileManager` |
| `uninstall.sh` | Removes global command and optionally config |

### How Profile Switching Works

1. User selects a profile (interactive menu or `switch <name>`)
2. `write_env_file()` writes `~/.config/claudeProfileManager/active_env` with export/unset statements
3. `update_claude_settings()` writes `apiKeyHelper`, `env.ANTHROPIC_BASE_URL`, and `model` to `~/.claude/settings.json`
4. For OAuth profiles: restores `~/.claude/.credentials.json` and updates `oauthAccount` in `~/.claude.json`; for API profiles: removes those OAuth files
5. A shell function in `.bashrc` auto-sources `active_env` after each invocation so env vars apply to the current shell

### Profile Types

**API key profiles** (`"type": "api"`):
- Writes all env vars to `active_env`; skips `ANTHROPIC_AUTH_TOKEN`
- Sets `apiKeyHelper` in `~/.claude/settings.json` to `echo <key>` (or `echo ollama` for keyless)
- Removes `~/.claude/.credentials.json` and clears `oauthAccount` from `~/.claude.json`

**OAuth profiles** (`"type": "oauth"`):
- Unsets all LLM provider vars in `active_env` (Claude Code manages OAuth internally)
- Removes `apiKeyHelper` override from `~/.claude/settings.json`
- Restores `~/.claude/.credentials.json` and sets `oauthAccount` in `~/.claude.json`

### Profile Storage Schema

```json
{
  "active": "profile-name",
  "profiles": [
    {
      "name": "profile-name",
      "description": "Human readable description",
      "type": "api",
      "api_key": "sk-...",
      "base_url": "https://...",
      "model": "claude-opus-4-6"
    },
    {
      "name": "claude-pro",
      "description": "Claude Pro Subscription",
      "type": "oauth",
      "accountUuid": "...",
      "organizationUuid": "...",
      "emailAddress": "user@example.com",
      "displayName": "...",
      "organizationName": "...",
      "organizationRole": "...",
      "credentials": { ... },
      "oauthAccount": { ... }
    }
  ]
}
```

### Environment Variables Set (API profiles)

- `LITELLM_PROXY_API_KEY`, `LITELLM_PROXY_URL`
- `GEMINI_API_KEY`, `GEMINI_BASE_URL`
- `OPENAI_API_KEY`, `OPENAI_BASE_URL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL` (note: `ANTHROPIC_AUTH_TOKEN` is unset for API profiles)
- `OLLAMA_API_BASE` (always `http://127.0.0.1:11434`)

## CLI Commands

- `claudeProfileManager` — Interactive menu (default)
- `claudeProfileManager switch <name>` — Switch profile directly
- `claudeProfileManager list` — List profiles
- `claudeProfileManager current` — Show active profile details
- `claudeProfileManager add` — Add profile interactively (API key or OAuth type)
- `claudeProfileManager remove [name]` — Remove a profile
- `claudeProfileManager import-oauth` — Import OAuth profile from current `~/.claude.json`
- `claudeProfileManager clear` — Unset all env vars and remove managed settings
- `claudeProfileManager help` — Show usage

## Development Commands

```bash
# Run directly
python3 claude_keys.py

# Run via launcher
./claudeProfileManager

# Install globally
./install.sh
```

## Configuration Paths

| Path | Purpose |
|------|---------|
| `~/.config/claudeProfileManager/profiles.json` | Profile storage |
| `~/.config/claudeProfileManager/active_env` | Sourceable env file written on switch |
| `~/.claude/settings.json` | Claude Code settings (apiKeyHelper, model, ANTHROPIC_BASE_URL) |
| `~/.claude/.credentials.json` | OAuth credentials (saved/restored on OAuth profile switch) |
| `~/.claude.json` | oauthAccount field updated on OAuth profile switch |


## Dependencies

Zero external dependencies — pure Python standard library (`json`, `os`, `sys`, `re`).

## First-Run Behavior

1. Detects existing LLM keys in `~/.bashrc` and offers to import them
2. If declined, prompts to create first profile interactively
3. Automatically adds shell wrapper function to `~/.bashrc`
