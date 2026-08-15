# claude-switch

CLI tool to manage and switch Claude Code API provider configurations.

Quickly switch between different API providers (OpenRouter, Anthropic direct, custom gateways, etc.) without manually editing environment variables every time.

## Features

- 🔄 **Quick switching** — Switch between providers in one command
- 🔍 **Model auto-discovery** — Automatically fetch available models from your endpoint
- 📋 **Built-in templates** — Pre-configured for Anthropic, OpenRouter, and OpenAI-compatible gateways
- 🚀 **Shell alias** — Launch with `cc` instead of `claude`
- 🔐 **Secure** — API keys stored locally in `~/.claude-switch/`
- 🖥️ **Cross-platform** — Works on Windows, macOS, and Linux

## Install

```bash
pip install git+https://github.com/billiyagi/claude-switch.git
```

Or with [pipx](https://pypa.github.io/pipx/) (recommended for CLI tools):

```bash
pipx install git+https://github.com/billiyagi/claude-switch.git
```

Or clone and install locally:

```bash
git clone https://github.com/billiyagi/claude-switch.git
cd claude-switch
pip install -e .
```

## Usage

### Add a provider profile

```bash
claude-switch add openrouter
```

Interactive wizard guides you through:
1. Choose a template (Anthropic, OpenRouter, OpenAI-compatible, or Custom)
2. Enter Base URL and API Key/Auth Token
3. **Auto-discovers models** from your endpoint's `/models` API
4. Pick primary model and small/fast model from the discovered list

### List available models from endpoint

```bash
# From active profile
claude-switch models

# From a specific profile
claude-switch models openrouter
```

Shows all models available at the endpoint with the currently selected ones highlighted.

### List profiles

```bash
claude-switch list
```

### Switch active profile

```bash
claude-switch use openrouter
```

### Launch Claude with active profile

```bash
claude-switch run
# or pass args:
claude-switch run -- -c "hello"
```

### Check Claude binary location

```bash
claude-switch which
```

Shows platform info and where `claude` binary was detected. Searches:
- System PATH
- npm global installs
- nvm, volta, bun, scoop, homebrew paths
- Common platform-specific locations

### Edit a profile

```bash
claude-switch edit openrouter
```

When editing, you can re-fetch models from the endpoint and change your selection.

### Shell alias (recommended)

```bash
claude-switch init
```

This prints a shell function for your shell. Works with:

| Shell | Setup |
|-------|-------|
| **bash** | Add to `~/.bashrc` |
| **zsh** | Add to `~/.zshrc` |
| **fish** | Add to `~/.config/fish/config.fish` |
| **PowerShell** | Add to `$PROFILE` |
| **CMD** | Save as `cc.bat` in PATH |

Then use `cc` instead of `claude`:

```bash
cc  # Launches claude with active profile
```

### Export environment variables

```bash
# Unix/macOS — prints shell export commands
eval "$(claude-switch export openrouter)"

# Windows PowerShell — prints $env: assignments
claude-switch export openrouter | Invoke-Expression
```

## How it works

Profiles are stored in `~/.claude-switch/profiles.json`. When you run `claude-switch use <name>`, it saves the active profile name. When you run `claude-switch run`, it sets the appropriate environment variables and launches Claude Code.

## Environment variables

- `ANTHROPIC_BASE_URL` — API endpoint URL
- `ANTHROPIC_AUTH_TOKEN` — Bearer token for custom gateways
- `ANTHROPIC_API_KEY` — API key for direct Anthropic
- `ANTHROPIC_MODEL` — Main model name
- `ANTHROPIC_SMALL_FAST_MODEL` — Background/fast model

## Commands

| Command | Description |
|---------|-------------|
| `claude-switch add <name>` | Add a new profile (interactive, auto-discovers models) |
| `claude-switch list` | List all saved profiles |
| `claude-switch use <name>` | Set active profile |
| `claude-switch current` | Show active profile |
| `claude-switch run [-- args]` | Launch claude with active profile |
| `claude-switch export <name>` | Print shell export commands |
| `claude-switch edit <name>` | Edit existing profile (with model re-discovery) |
| `claude-switch remove <name>` | Delete a profile |
| `claude-switch models [name]` | List available models from endpoint |
| `claude-switch which` | Show detected claude binary and platform info |
| `claude-switch init` | Show shell function setup |

## Platform Support

| Platform | Status |
|----------|--------|
| Linux | ✅ Full support |
| macOS (Intel & Apple Silicon) | ✅ Full support |
| Windows (PowerShell) | ✅ Full support |
| Windows (CMD) | ✅ Full support |

Claude binary detection automatically searches platform-specific paths including npm global, nvm, volta, bun, homebrew (macOS), and scoop (Windows).

## License

MIT
