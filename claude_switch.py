#!/usr/bin/env python3
"""
claude-switch — CLI tool to manage Claude Code provider configurations.

Quickly switch between different API providers (OpenRouter, Anthropic direct,
custom gateways, etc.) without manually editing env vars every time.

Usage:
    claude-switch add <name>       Add a new provider profile
    claude-switch list             List all saved profiles
    claude-switch use <name>       Activate a profile (prints export commands)
    claude-switch current          Show the active profile
    claude-switch remove <name>    Remove a profile
    claude-switch edit <name>      Edit an existing profile
    claude-switch run [args...]    Launch claude with active profile env
    claude-switch export <name>    Print shell export commands for a profile
    claude-switch init             Create a quick shell alias/function
    claude-switch models [name]    List available models from a profile's endpoint
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

# ── Paths ──────────────────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".claude-switch"
PROFILES_FILE = CONFIG_DIR / "profiles.json"
ACTIVE_FILE = CONFIG_DIR / "active"

# ── Colors ─────────────────────────────────────────────────────────────────
class C:
    BOLD  = "\033[1m"
    DIM   = "\033[2m"
    GREEN = "\033[32m"
    CYAN  = "\033[36m"
    YELLOW= "\033[33m"
    RED   = "\033[31m"
    RESET = "\033[0m"

def ok(msg):   print(f"{C.GREEN}✔{C.RESET} {msg}")
def info(msg): print(f"{C.CYAN}ℹ{C.RESET} {msg}")
def warn(msg): print(f"{C.YELLOW}⚠{C.RESET} {msg}")
def err(msg):  print(f"{C.RED}✘{C.RESET} {msg}", file=sys.stderr)

# ── Data helpers ───────────────────────────────────────────────────────────
def ensure_dir():
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

def load_profiles() -> dict:
    ensure_dir()
    if PROFILES_FILE.exists():
        return json.loads(PROFILES_FILE.read_text())
    return {}

def save_profiles(profiles: dict):
    ensure_dir()
    PROFILES_FILE.write_text(json.dumps(profiles, indent=2) + "\n")

def get_active_name() -> Optional[str]:
    ensure_dir()
    if ACTIVE_FILE.exists():
        name = ACTIVE_FILE.read_text().strip()
        return name if name else None
    return None

def set_active(name: str):
    ensure_dir()
    ACTIVE_FILE.write_text(name + "\n")

def get_active_profile() -> Optional[dict]:
    name = get_active_name()
    if not name:
        return None
    profiles = load_profiles()
    return profiles.get(name)

# ── Built-in provider templates ────────────────────────────────────────────
PROVIDER_TEMPLATES = {
    "anthropic": {
        "description": "Anthropic direct (default)",
        "base_url": "",
        "auth_token": "",
        "api_key": "",
        "model": "claude-sonnet-4-20250514",
        "small_fast_model": "claude-haiku-4-20250414",
    },
    "openrouter": {
        "description": "OpenRouter gateway",
        "base_url": "https://openrouter.ai/api/v1",
        "auth_token": "",
        "api_key": "",
        "model": "anthropic/claude-sonnet-4",
        "small_fast_model": "anthropic/claude-haiku-4",
    },
    "openai-compatible": {
        "description": "OpenAI-compatible gateway (LiteLLM, vLLM, etc.)",
        "base_url": "http://localhost:4000/v1",
        "auth_token": "",
        "api_key": "",
        "model": "claude-sonnet-4-20250514",
        "small_fast_model": "claude-haiku-4-20250414",
    },
}

# ── Model discovery ────────────────────────────────────────────────────────
def fetch_models(base_url: str, api_key: str = "", auth_token: str = "") -> list[str]:
    """Fetch available models from an OpenAI-compatible /models endpoint."""
    url = base_url.rstrip("/") + "/models"

    headers = {"Content-Type": "application/json"}
    token = auth_token or api_key
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.reason}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Connection failed: {e.reason}")
    except Exception as e:
        raise RuntimeError(str(e))

    # Handle both OpenAI format {"data": [{"id": ...}]} and plain list
    if isinstance(data, dict):
        items = data.get("data", data.get("models", []))
    elif isinstance(data, list):
        items = data
    else:
        return []

    models = []
    for item in items:
        if isinstance(item, str):
            models.append(item)
        elif isinstance(item, dict):
            mid = item.get("id", "")
            if mid:
                models.append(mid)

    return sorted(models)


def pick_model(models: list[str], label: str = "model", current: str = "") -> str:
    """Interactive model picker. Returns selected model ID."""
    if not models:
        warn("No models found from endpoint.")
        return ""

    print(f"\n{C.BOLD}Available models:{C.RESET}\n")
    for i, m in enumerate(models, 1):
        marker = f" {C.GREEN}(current){C.RESET}" if m == current else ""
        print(f"  {C.CYAN}{i:>3}{C.RESET}) {m}{marker}")

    print(f"\n  {C.DIM}Enter number, model name, or press Enter to keep '{current or 'manual'}'{C.RESET}")

    while True:
        choice = input(f"  Select {label}: ").strip()
        if not choice:
            return current
        # Direct model name
        if choice in models:
            return choice
        # Number selection
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except ValueError:
            pass
        # Accept freeform input (user might type a model not in list)
        warn(f"'{choice}' not in discovered list. Use anyway? (y/N)")
        confirm = input("  ").strip().lower()
        if confirm in ("y", "yes"):
            return choice


def cmd_models(args):
    """List available models from a profile's endpoint."""
    profiles = load_profiles()
    name = args.name or get_active_name()

    if not name or name not in profiles:
        if name:
            err(f"Profile '{name}' not found.")
        else:
            err("No active profile. Specify a profile name or run: claude-switch use <name>")
        sys.exit(1)

    p = profiles[name]
    base_url = p.get("base_url", "")
    if not base_url:
        err("This profile has no base_url (direct Anthropic). Models endpoint not available.")
        sys.exit(1)

    info(f"Fetching models from {base_url}/models ...")
    try:
        models = fetch_models(base_url, p.get("api_key", ""), p.get("auth_token", ""))
    except RuntimeError as e:
        err(f"Failed to fetch models: {e}")
        sys.exit(1)

    if not models:
        warn("No models returned by this endpoint.")
        return

    print(f"\n{C.BOLD}Models for '{name}' ({len(models)} available):{C.RESET}\n")
    current_model = p.get("model", "")
    current_small = p.get("small_fast_model", "")
    for m in models:
        tags = []
        if m == current_model:
            tags.append(f"{C.GREEN}primary{C.RESET}")
        if m == current_small:
            tags.append(f"{C.CYAN}small/fast{C.RESET}")
        tag_str = f"  ← {', '.join(tags)}" if tags else ""
        print(f"  • {m}{tag_str}")
    print()

# ── Profile env builder ────────────────────────────────────────────────────
def profile_to_env(profile: dict) -> dict:
    """Convert a profile dict to env var dict (only non-empty values)."""
    env = {}
    if profile.get("base_url"):
        env["ANTHROPIC_BASE_URL"] = profile["base_url"]
    if profile.get("auth_token"):
        env["ANTHROPIC_AUTH_TOKEN"] = profile["auth_token"]
    if profile.get("api_key"):
        env["ANTHROPIC_API_KEY"] = profile["api_key"]
    if profile.get("model"):
        env["ANTHROPIC_MODEL"] = profile["model"]
    if profile.get("small_fast_model"):
        env["ANTHROPIC_SMALL_FAST_MODEL"] = profile["small_fast_model"]
    return env

# ── Commands ───────────────────────────────────────────────────────────────
def cmd_add(args):
    """Add a new provider profile."""
    profiles = load_profiles()
    name = args.name

    if name in profiles and not args.force:
        err(f"Profile '{name}' already exists. Use --force to overwrite.")
        sys.exit(1)

    print(f"\n{C.BOLD}Adding profile: {name}{C.RESET}\n")

    # Show templates
    print(f"{C.DIM}Quick templates:{C.RESET}")
    for i, (key, tpl) in enumerate(PROVIDER_TEMPLATES.items(), 1):
        print(f"  {C.CYAN}{i}{C.RESET}) {tpl['description']}")
    print(f"  {C.CYAN}0{C.RESET}) Custom (manual input)\n")

    choice = input(f"Choose template [0]: ").strip() or "0"
    template = {}
    if choice in ("1", "2", "3"):
        keys = list(PROVIDER_TEMPLATES.keys())
        template = PROVIDER_TEMPLATES[keys[int(choice) - 1]]
        info(f"Using template: {template['description']}")

    def ask(field, prompt, default: str = "", secret=False):
        val = input(f"  {prompt} [{C.DIM}{default or '(empty)'}{C.RESET}]: ").strip()
        return val if val else default

    base_url = ask("base_url", "Base URL", template.get("base_url", ""))
    auth_token = ask("auth_token", "Auth Token (for custom gateway)", template.get("auth_token", ""), secret=True)
    api_key = ask("api_key", "API Key (for direct Anthropic)", template.get("api_key", ""), secret=True)
    description = ask("description", "Description", template.get("description", name))

    # Auto-discover models from endpoint
    model = template.get("model", "claude-sonnet-4-20250514")
    small_fast_model = template.get("small_fast_model", "claude-haiku-4-20250414")

    if base_url:
        info(f"Fetching available models from {base_url}/models ...")
        try:
            discovered = fetch_models(base_url, api_key, auth_token)
            if discovered:
                ok(f"Found {len(discovered)} models!")
                model = pick_model(discovered, "primary model", model)
                small_fast_model = pick_model(discovered, "small/fast model", small_fast_model)
            else:
                warn("No models discovered. Falling back to manual input.")
                model = ask("model", "Model", model)
                small_fast_model = ask("small_fast_model", "Small/fast model", small_fast_model)
        except RuntimeError as e:
            warn(f"Could not fetch models: {e}")
            warn("Falling back to manual input.")
            model = ask("model", "Model", model)
            small_fast_model = ask("small_fast_model", "Small/fast model", small_fast_model)
    else:
        model = ask("model", "Model", model)
        small_fast_model = ask("small_fast_model", "Small/fast model", small_fast_model)

    profile = {
        "description": description,
        "base_url": base_url,
        "auth_token": auth_token,
        "api_key": api_key,
        "model": model,
        "small_fast_model": small_fast_model,
    }

    profiles[name] = profile
    save_profiles(profiles)
    ok(f"Profile '{name}' saved.")

    # Auto-activate if it's the first profile or user wants
    if not get_active_name():
        set_active(name)
        info(f"Auto-activated '{name}' (first profile).")

def cmd_list(args):
    """List all profiles."""
    profiles = load_profiles()
    if not profiles:
        warn("No profiles saved yet. Run: claude-switch add <name>")
        return

    active = get_active_name()
    print(f"\n{C.BOLD}Profiles:{C.RESET}\n")
    for name, p in profiles.items():
        marker = f" {C.GREEN}● active{C.RESET}" if name == active else ""
        base = p.get("base_url") or "https://api.anthropic.com (direct)"
        model = p.get("model", "?")
        desc = p.get("description", "")
        print(f"  {C.BOLD}{name}{C.RESET}{marker}")
        if desc:
            print(f"    {C.DIM}{desc}{C.RESET}")
        print(f"    endpoint: {base}")
        print(f"    model:    {model}")
        print()

def cmd_use(args):
    """Switch active profile."""
    profiles = load_profiles()
    name = args.name
    if name not in profiles:
        err(f"Profile '{name}' not found.")
        print(f"  Available: {', '.join(profiles.keys())}")
        sys.exit(1)

    set_active(name)
    p = profiles[name]
    env = profile_to_env(p)

    ok(f"Switched to '{name}'")
    print(f"\n  {C.BOLD}Environment:{C.RESET}")
    for k, v in env.items():
        display = v[:8] + "***" if ("TOKEN" in k or "KEY" in k) and len(v) > 8 else v
        print(f"    {k}={display}")

    print(f"\n  {C.DIM}Use 'claude-switch run' to launch Claude with this profile.{C.RESET}")
    print(f"  {C.DIM}Or: eval \"$(claude-switch export {name})\" && claude{C.RESET}")

def cmd_current(args):
    """Show current active profile."""
    name = get_active_name()
    if not name:
        warn("No active profile. Run: claude-switch use <name>")
        return

    profiles = load_profiles()
    if name not in profiles:
        err(f"Active profile '{name}' no longer exists.")
        return

    p = profiles[name]
    env = profile_to_env(p)

    print(f"\n{C.BOLD}Active: {C.GREEN}{name}{C.RESET}")
    if p.get("description"):
        print(f"  {C.DIM}{p['description']}{C.RESET}")
    print()
    for k, v in env.items():
        display = v[:8] + "***" if ("TOKEN" in k or "KEY" in k) and len(v) > 8 else v
        print(f"  {k}={display}")
    print()

def cmd_export(args):
    """Print shell export commands for a profile."""
    profiles = load_profiles()
    name = args.name or get_active_name()
    if not name or name not in profiles:
        err(f"Profile '{name}' not found.")
        sys.exit(1)

    env = profile_to_env(profiles[name])
    for k, v in env.items():
        # Shell-safe quoting
        escaped = v.replace("'", "'\\''")
        print(f"export {k}='{escaped}'")

def cmd_remove(args):
    """Remove a profile."""
    profiles = load_profiles()
    name = args.name
    if name not in profiles:
        err(f"Profile '{name}' not found.")
        sys.exit(1)

    del profiles[name]
    save_profiles(profiles)

    if get_active_name() == name:
        ACTIVE_FILE.unlink(missing_ok=True)
        warn(f"Removed active profile. No active profile now.")

    ok(f"Profile '{name}' removed.")

def cmd_edit(args):
    """Edit an existing profile."""
    profiles = load_profiles()
    name = args.name
    if name not in profiles:
        err(f"Profile '{name}' not found.")
        sys.exit(1)

    p = profiles[name]
    print(f"\n{C.BOLD}Editing profile: {name}{C.RESET}")
    print(f"{C.DIM}(Press Enter to keep current value){C.RESET}\n")

    def ask(field, label, current):
        val = input(f"  {label} [{C.DIM}{current or '(empty)'}{C.RESET}]: ").strip()
        return val if val else current

    p["base_url"] = ask("base_url", "Base URL", p.get("base_url", ""))
    p["auth_token"] = ask("auth_token", "Auth Token", p.get("auth_token", ""))
    p["api_key"] = ask("api_key", "API Key", p.get("api_key", ""))
    p["description"] = ask("description", "Description", p.get("description", ""))

    # Offer model discovery if base_url is set
    base_url = p.get("base_url", "")
    if base_url:
        fetch_choice = input(f"  Fetch available models from endpoint? [Y/n]: ").strip().lower()
        if fetch_choice in ("", "y", "yes"):
            info(f"Fetching models from {base_url}/models ...")
            try:
                discovered = fetch_models(base_url, p.get("api_key", ""), p.get("auth_token", ""))
                if discovered:
                    ok(f"Found {len(discovered)} models!")
                    p["model"] = pick_model(discovered, "primary model", p.get("model", ""))
                    p["small_fast_model"] = pick_model(discovered, "small/fast model", p.get("small_fast_model", ""))
                else:
                    warn("No models discovered.")
                    p["model"] = ask("model", "Model", p.get("model", ""))
                    p["small_fast_model"] = ask("small_fast_model", "Small/fast model", p.get("small_fast_model", ""))
            except RuntimeError as e:
                warn(f"Could not fetch models: {e}")
                p["model"] = ask("model", "Model", p.get("model", ""))
                p["small_fast_model"] = ask("small_fast_model", "Small/fast model", p.get("small_fast_model", ""))
        else:
            p["model"] = ask("model", "Model", p.get("model", ""))
            p["small_fast_model"] = ask("small_fast_model", "Small/fast model", p.get("small_fast_model", ""))
    else:
        p["model"] = ask("model", "Model", p.get("model", ""))
        p["small_fast_model"] = ask("small_fast_model", "Small/fast model", p.get("small_fast_model", ""))

    profiles[name] = p
    save_profiles(profiles)
    ok(f"Profile '{name}' updated.")

def cmd_run(args):
    """Launch claude with the active profile's environment."""
    name = get_active_name()
    if not name:
        err("No active profile. Run: claude-switch use <name>")
        sys.exit(1)

    profiles = load_profiles()
    if name not in profiles:
        err(f"Active profile '{name}' no longer exists.")
        sys.exit(1)

    env = os.environ.copy()
    env.update(profile_to_env(profiles[name]))

    claude_bin = subprocess.run(
        ["which", "claude"], capture_output=True, text=True
    ).stdout.strip()
    if not claude_bin:
        err("Claude Code not found in PATH.")
        sys.exit(1)

    cmd = [claude_bin] + args.claude_args
    info(f"Launching claude with profile '{C.BOLD}{name}{C.RESET}{C.CYAN}'...")
    result = subprocess.run(cmd, env=env)
    sys.exit(result.returncode)

def cmd_init(args):
    """Print shell function for easy use."""
    shell = args.shell or os.environ.get("SHELL", "/bin/bash")
    shell_name = Path(shell).name

    if shell_name == "fish":
        func = """# Add to ~/.config/fish/config.fish
function cc --description "Launch claude with claude-switch profile"
    set -l profile (cat ~/.claude-switch/active 2>/dev/null | string trim)
    if test -z "$profile"
        echo "No active profile. Run: claude-switch use <name>"
        return 1
    end

    set -l tmpfile (mktemp)
    python3 claude_switch.py export $profile > $tmpfile
    and source $tmpfile
    and rm $tmpfile

    claude $argv
end"""
    elif shell_name == "zsh":
        func = """# Add to ~/.zshrc
cc() {
    local profile
    profile=$(cat ~/.claude-switch/active 2>/dev/null)
    if [[ -z "$profile" ]]; then
        echo "No active profile. Run: claude-switch use <name>"
        return 1
    fi
    eval "$(claude-switch export "$profile")"
    claude "$@"
}"""
    else:
        func = """# Add to ~/.bashrc
cc() {
    local profile
    profile=$(cat ~/.claude-switch/active 2>/dev/null)
    if [[ -z "$profile" ]]; then
        echo "No active profile. Run: claude-switch use <name>"
        return 1
    fi
    eval "$(claude-switch export "$profile")"
    claude "$@"
}"""

    print(f"\n{C.BOLD}Shell function for {shell_name}:{C.RESET}\n")
    print(func)
    print(f"\n{C.DIM}After adding, restart your shell or run: source ~/.{shell_name}rc{C.RESET}")
    print(f"{C.DIM}Then use: cc (instead of claude) to auto-load your active profile.{C.RESET}\n")

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        prog="claude-switch",
        description="Switch Claude Code API providers easily.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  claude-switch add openrouter       Add an OpenRouter profile
  claude-switch use openrouter       Switch to OpenRouter
  claude-switch run                  Launch claude with active profile
  claude-switch run -- -c "hello"    Pass args to claude
  claude-switch list                 Show all profiles
  claude-switch models               List models from active profile's endpoint
  claude-switch models openrouter    List models from a specific profile
  claude-switch init                 Show shell alias setup
        """,
    )

    sub = parser.add_subparsers(dest="command")

    # add
    p_add = sub.add_parser("add", help="Add a new provider profile")
    p_add.add_argument("name", help="Profile name (e.g., openrouter, local)")
    p_add.add_argument("--force", "-f", action="store_true", help="Overwrite existing")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", aliases=["ls"], help="List all profiles")
    p_list.set_defaults(func=cmd_list)

    # use
    p_use = sub.add_parser("use", help="Switch active profile")
    p_use.add_argument("name", help="Profile name")
    p_use.set_defaults(func=cmd_use)

    # current
    p_cur = sub.add_parser("current", aliases=["status"], help="Show active profile")
    p_cur.set_defaults(func=cmd_current)

    # export
    p_exp = sub.add_parser("export", help="Print shell export commands")
    p_exp.add_argument("name", nargs="?", help="Profile name (default: active)")
    p_exp.set_defaults(func=cmd_export)

    # remove
    p_rm = sub.add_parser("remove", aliases=["rm"], help="Remove a profile")
    p_rm.add_argument("name", help="Profile name")
    p_rm.set_defaults(func=cmd_remove)

    # edit
    p_edit = sub.add_parser("edit", help="Edit an existing profile")
    p_edit.add_argument("name", help="Profile name")
    p_edit.set_defaults(func=cmd_edit)

    # run
    p_run = sub.add_parser("run", help="Launch claude with active profile")
    p_run.add_argument("claude_args", nargs="*", help="Arguments passed to claude")
    p_run.set_defaults(func=cmd_run)

    # init
    p_init = sub.add_parser("init", help="Show shell alias/function setup")
    p_init.add_argument("--shell", help="Shell type (bash/zsh/fish)")
    p_init.set_defaults(func=cmd_init)

    # models
    p_models = sub.add_parser("models", help="List available models from profile's endpoint")
    p_models.add_argument("name", nargs="?", help="Profile name (default: active)")
    p_models.set_defaults(func=cmd_models)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    args.func(args)

if __name__ == "__main__":
    main()
