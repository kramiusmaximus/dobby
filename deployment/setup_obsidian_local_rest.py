from __future__ import annotations

import json
import secrets
import sys
import time
import urllib.request
from pathlib import Path


PLUGIN_ID = "obsidian-local-rest-api"
PLUGIN_VERSION = "4.1.1"
PLUGIN_URL_BASE = f"https://github.com/coddingtonbear/{PLUGIN_ID}/releases/download/{PLUGIN_VERSION}"


def _load_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key] = value.strip().strip("'\"")
    return values


def _write_env(path: Path, updates: dict[str, str]) -> None:
    lines = path.read_text().splitlines() if path.exists() else []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0]
            if key in updates:
                out.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
    path.write_text("\n".join(out).rstrip() + "\n")


def _read_json(path: Path, default: object) -> object:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return default


def _download_plugin(plugin_dir: Path) -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("main.js", "manifest.json", "styles.css"):
        url = f"{PLUGIN_URL_BASE}/{filename}"
        with urllib.request.urlopen(url, timeout=30) as response:
            (plugin_dir / filename).write_bytes(response.read())


def main() -> int:
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    env_path = root / ".env"
    wiki_root = root / "wiki"
    obsidian_config = root / "obsidian-config"

    env = _load_env(env_path)
    api_key = env.get("OBSIDIAN_API_KEY") or secrets.token_urlsafe(48)
    _write_env(
        env_path,
        {
            "OBSIDIAN_API_URL": "http://obsidian:27123",
            "OBSIDIAN_API_KEY": api_key,
            "OBSIDIAN_VERIFY_TLS": "false",
            "OBSIDIAN_ENABLED": "true",
        },
    )

    vault_config = wiki_root / ".obsidian"
    plugin_dir = vault_config / "plugins" / PLUGIN_ID
    _download_plugin(plugin_dir)

    community_plugins_path = vault_config / "community-plugins.json"
    plugins = _read_json(community_plugins_path, [])
    if not isinstance(plugins, list):
        plugins = []
    if PLUGIN_ID not in plugins:
        plugins.append(PLUGIN_ID)
    community_plugins_path.write_text(json.dumps(plugins, indent=2) + "\n")

    app_config_path = vault_config / "app.json"
    app_config = _read_json(app_config_path, {})
    if not isinstance(app_config, dict):
        app_config = {}
    app_config["safeMode"] = False
    app_config_path.write_text(json.dumps(app_config, indent=2) + "\n")

    (plugin_dir / "data.json").write_text(
        json.dumps(
            {
                "apiKey": api_key,
                "port": 27124,
                "insecurePort": 27123,
                "enableInsecureServer": True,
                "enableSecureServer": False,
                "bindingHost": "0.0.0.0",
                "authorizationHeaderName": "Authorization",
            },
            indent=2,
        )
        + "\n"
    )

    app_profile = obsidian_config / ".config" / "obsidian"
    app_profile.mkdir(parents=True, exist_ok=True)
    (app_profile / "obsidian.json").write_text(
        json.dumps(
            {
                "vaults": {
                    "dobby": {
                        "path": "/config/dobby",
                        "ts": int(time.time() * 1000),
                        "open": True,
                    }
                }
            },
            indent=2,
        )
        + "\n"
    )
    (app_profile / "dobby.json").write_text(json.dumps({"frame": "native"}, indent=2) + "\n")
    print("Obsidian Local REST API configured for http://obsidian:27123")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
