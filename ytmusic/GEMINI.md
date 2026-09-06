# Python Development on NixOS Guidelines

This guide outlines the standards, configurations, and workflows for developing Python applications within a NixOS environment. Because NixOS manages system libraries declaratively, standard Python workflows (like installing packages with compiled C-extensions via `pip`) require specific configurations to find headers and dynamic linkers.

---

## 1. Quick Start

We support two main paths for Python development environments on NixOS:
1. **Nix Flakes (`flake.nix`)** – Recommended for modern, reproducible environments with lockfiles.
2. **Classic Nix (`shell.nix`)** – Simple, quick, and works with standard nix-shell.

Both approaches are coupled with **`direnv`** to automatically activate the environment when you enter the directory.

### Step 1: Automatic Environment Loading (`direnv`)
Install `direnv` and `nix-direnv` on your system. Then, create a `.envrc` file in the root of the project:

```bash
# .envrc
use flake # If using Flakes (Option A)
# OR
# use nix   # If using shell.nix (Option B)
```

Allow the directory:
```bash
direnv allow
```

---

## 2. Environment Configurations

### Option A: Nix Flakes (Modern, Recommended)
Create a `flake.nix` in the root of your project:

```nix
{
  description = "Python Development Environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs {
          inherit system;
          config.allowUnfree = true;
        };

        # Choose your Python version
        pythonEnv = pkgs.python311.withPackages (ps: with ps; [
          pip
          virtualenv
          setuptools
          wheel
        ]);

        # Add native dependencies frequently required by Python C-extensions
        nativeLibs = with pkgs; [
          stdenv.cc.cc.lib
          zlib
          glib
          libffi
          openssl
        ];
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            pythonEnv
          ] ++ nativeLibs;

          shellHook = ''
            # Setup virtual environment if it doesn't exist
            if [ ! -d ".venv" ]; then
              virtualenv .venv
            fi
            source .venv/bin/activate

            # Ensure dynamic compiler/linker paths are set for C-extensions
            export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath nativeLibs}:$LD_LIBRARY_PATH"

            # Setup pip to point inside the virtualenv
            export PIP_REQUIRE_VIRTUALENV=true

            echo "🐍 Python NixOS DevShell Active!"
            python --version
          '';
        };
      });
}
```

### Option B: Classic Nix Shell (`shell.nix`)
If you prefer not to use Flakes, create a `shell.nix` in the root of your project:

```nix
{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python311.withPackages (ps: with ps; [
    pip
    virtualenv
    setuptools
    wheel
  ]);

  nativeLibs = with pkgs; [
    stdenv.cc.cc.lib
    zlib
    glib
    libffi
    openssl
  ];
in
pkgs.mkShell {
  buildInputs = [
    pythonEnv
  ] ++ nativeLibs;

  shellHook = ''
    if [ ! -d ".venv" ]; then
      virtualenv .venv
    fi
    source .venv/bin/activate

    export LD_LIBRARY_PATH="${pkgs.lib.makeLibraryPath nativeLibs}:$LD_LIBRARY_PATH"
    export PIP_REQUIRE_VIRTUALENV=true

    echo "🐍 Python NixOS Shell Active!"
    python --version
  '';
}
```

---

## 3. Resolving the "Dynamic Linker" / C-Extension Problem

On typical Linux distros, pre-compiled wheels (e.g., NumPy, Pandas, PyTorch) find libraries in hardcoded locations like `/lib` or `/usr/lib`. On NixOS, these paths do not exist, leading to errors like:
`ImportError: libstdc++.so.6: cannot open shared object file`

Here are the three standard ways to solve this in this codebase:

### Method 1: `LD_LIBRARY_PATH` via Dev Shell (Included in template)
By putting native libraries in `nativeLibs` and defining `LD_LIBRARY_PATH` inside the `shellHook`, virtualenv-installed C-extensions will successfully link against NixOS system libraries at runtime.

### Method 2: Global NixOS `nix-ld` Configuration (Highly Recommended)
Enable `nix-ld` in your system configuration (`/etc/nixos/configuration.nix`). This runs an interpreter multiplexer that resolves hardcoded dynamic linker paths automatically for unpatched pre-compiled binaries.

```nix
# In /etc/nixos/configuration.nix
programs.nix-ld.enable = true;
programs.nix-ld.libraries = with pkgs; [
  stdenv.cc.cc
  zlib
  glib
  libffi
  openssl
  # Add other libraries commonly needed by python wheels
];
```

### Method 3: Declaring Python Packages via Nix
Instead of installing packages with `pip` inside a `.venv`, declare Python dependencies directly inside your `flake.nix` or `shell.nix`:
```nix
pythonEnv = pkgs.python311.withPackages (ps: with ps; [
  pip
  numpy
  pandas
  scikit-learn
  requests
]);
```
This guarantees fully reproducible packages managed by Nix, avoiding any linking errors completely.

---

## 4. IDE and Editor Integration

To ensure autocomplete, linting, and definitions work correctly, your editor needs to run in the context of the Nix environment.

### VS Code
1. Install the **Direnv** extension (`mkhl.direnv`).
2. Install the **Python** extension (`ms-python.python`).
3. Set your default Python interpreter path to point to your local virtualenv: `.venv/bin/python`.

### PyCharm
1. Install the **EnvFile** plugin to support environment variable injection.
2. Alternatively, launch PyCharm from within an active nix shell/terminal:
   ```bash
   nix develop -c pycharm-professional .
   ```

---

## 5. Coding Standards & Tooling

To maintain clean and deterministic codebase quality, we enforce standard tools:

- **Linter & Formatter**: [Ruff](https://github.com/astral-sh/ruff)
  - Installed via Nix: Add `pkgs.ruff` to `buildInputs`.
  - Fast, modern replacement for Flake8, Black, and isort.
- **Type Checker**: [Pyright / Mypy](https://github.com/microsoft/pyright)
  - Configured to look inside `.venv/` for dependency resolution.
- **Test Runner**: [pytest](https://docs.pytest.org/)
  - Always run tests within the active shell (`pytest tests/`).
- **Whitespace Hygiene**:
  - Trailing whitespace must be completely removed from all lines (including empty lines) in all code, configuration, and markdown source files before committing.

---

## 6. Common Troubleshooting

### Error: `pip install` fails with `externally-managed-environment`
**Solution**: Nix-installed python interpreters block raw pip installations. Always ensure you are inside an active virtualenv (`source .venv/bin/activate`). The provided `shellHook` takes care of this automatically on shell entry.

### Error: `git` hooks fail because `nix-shell` or `python` is not found
**Solution**: Ensure your pre-commit hooks or CI workflows run in an environment where nix is available, or use `nix-shell --run` to execute hooks.

---

## 7. YouTube Music API (`ytmusicapi`) Automation Conventions

To maintain consistency and secure credential management across all YouTube Music automation scripts, follow these design patterns.

### 7.1. Secure Credentials & SOPS Decryption
Never hardcode credentials or commit plaintext session cookies. All scripts must use the standardized bootstrapping routine to decrypt `encrypted_browser.json` to `browser.json` using **SOPS** and a local **age** key prior to initializing `YTMusic`.

Use the following boilerplate at the start of your script's `main()` entrypoint:

```python
import subprocess
import sys
from pathlib import Path
from ytmusicapi import YTMusic

def bootstrap_ytmusic() -> YTMusic:
    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'

    # Always ensure a clean start to avoid race conditions or stale credentials
    if browser_file.exists():
        browser_file.unlink()

    if not encrypted_browser.exists():
        print(f"Error: {encrypted_browser} does not exist.")
        sys.exit(1)

    print("Decrypting browser.json...")
    key_path = Path.home() / '.config/sops/age/keys.txt'
    try:
        with open(browser_file, 'w') as fh:
            subprocess.run(
                ['sops', '--age', str(key_path), '-d', str(encrypted_browser)],
                stdout=fh,
                check=True,
                timeout=10
            )

        ytmusic = YTMusic(str(browser_file))
        return ytmusic
    finally:
        # Clean up unencrypted file immediately to maintain strict system security
        if browser_file.exists():
            browser_file.unlink()
```

### 7.2. Safe Playlist Clearing & Rebuilding
When syncing external sources (e.g., Beatport or BBC), always clear existing playlists safely before appending new items. Large list operations can fail; handle them robustly:

```python
def clear_playlist(ytmusic: YTMusic, playlist_id: str):
    """Safely clears all current tracks from a playlist."""
    try:
        playlist_info = ytmusic.get_playlist(playlist_id, limit=None)
        tracks = playlist_info.get('tracks', [])
        if tracks:
            print(f"Clearing {len(tracks)} tracks from playlist {playlist_id}...")
            ytmusic.remove_playlist_items(playlist_id, tracks)
    except Exception as e:
        print(f"Warning: Failed to clear playlist contents: {e}")

def rebuild_playlist(ytmusic: YTMusic, playlist_id: str, track_ids: list):
    """Clears and rebuilds a playlist with the given track video IDs."""
    clear_playlist(ytmusic, playlist_id)
    if track_ids:
        print(f"Adding {len(track_ids)} tracks to playlist...")
        ytmusic.add_playlist_items(playlist_id, track_ids, duplicates=False)
```

### 7.3. Video Matching and Searching
When resolving text queries to YouTube Music track identifiers:
* Always specify `filter='songs'` to avoid matching video uploads, albums, or artists.
* Fetch the first result safely and verify the existence of `videoId`.

```python
def find_track_id(ytmusic: YTMusic, search_query: str) -> str | None:
    results = ytmusic.search(query=search_query, filter='songs')
    if results and 'videoId' in results[0]:
        return results[0]['videoId']
    return None
```

### 7.4. Handling Uploads and Library Albums
* **Upload Tracking**: Check responses for explicit failed statuses (such as `"STATUS_FAILED"`) and exit with a non-zero code to ensure orchestrators (like Systemd timers) raise alerts:
  ```python
  response = ytmusic.upload_song(filepath)
  if isinstance(response, str) and "STATUS_FAILED" in response:
      print(f"Upload failed for {filepath}: {response}")
      sys.exit(1)
  ```
* **Parsing Library Upload Albums**: When fetching tracks from a library upload album, inspect the `tracks` key directly:
  ```python
  album_details = ytmusic.get_library_upload_album(album_id)
  tracks = album_details.get('tracks', [])
  ```
```
