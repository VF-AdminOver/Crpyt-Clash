#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Crypt Clash installer (macOS/Linux)

Installs into: ~/.cryptclash (by default)
Creates launcher: ~/.local/bin/cryptclash (when possible)

Usage:
  bash scripts/install.sh --repo https://github.com/<ORG>/<REPO>.git
  bash scripts/install.sh --local

Options:
  --repo <url>     Git repo to clone (required unless --local)
  --ref <ref>      Git ref to checkout (branch/tag/sha). Default: main
  --dir <path>     Install dir. Default: ~/.cryptclash
  --python <exe>   Python executable to use. Default: python3
  --force          Delete existing install dir first
  --local          Install from current directory (no cloning/pulling)
  -h, --help       Show help

Notes:
  - Requires: bash, git, and Python (>= 3.10)
  - If ~/.local/bin is not on PATH, add it (or run ~/.cryptclash/venv/bin/cryptclash directly).
EOF
}

INSTALL_DIR="${HOME}/.cryptclash"
REPO_URL=""
GIT_REF="main"
PYTHON_EXE="python3"
FORCE="0"
LOCAL="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)
      REPO_URL="${2:-}"; shift 2
      ;;
    --ref)
      GIT_REF="${2:-}"; shift 2
      ;;
    --dir)
      INSTALL_DIR="${2:-}"; shift 2
      ;;
    --python)
      PYTHON_EXE="${2:-}"; shift 2
      ;;
    --force)
      FORCE="1"; shift
      ;;
    --local)
      LOCAL="1"; shift
      ;;
    -h|--help)
      usage; exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 2
      ;;
  esac
done

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

need_cmd bash
need_cmd "$PYTHON_EXE"
if [[ "$LOCAL" != "1" ]]; then
  need_cmd git
fi

"$PYTHON_EXE" - <<'PY'
import sys
major, minor = sys.version_info[:2]
if (major, minor) < (3, 10):
    raise SystemExit(f"Python >= 3.10 required; found {major}.{minor}")
PY

INSTALL_DIR="${INSTALL_DIR/#\~/$HOME}"

if [[ "$FORCE" == "1" && -d "$INSTALL_DIR" ]]; then
  rm -rf "$INSTALL_DIR"
fi

mkdir -p "$INSTALL_DIR"

SRC_DIR=""
if [[ "$LOCAL" == "1" ]]; then
  SRC_DIR="$(pwd)"
  if [[ ! -f "$SRC_DIR/pyproject.toml" ]]; then
    echo "No pyproject.toml found in $SRC_DIR; run from the repo root or omit --local." >&2
    exit 1
  fi
else
  if [[ -z "$REPO_URL" ]]; then
    echo "--repo is required unless --local is used." >&2
    usage
    exit 2
  fi

  SRC_DIR="$INSTALL_DIR/src"
  if [[ -d "$SRC_DIR/.git" ]]; then
    git -C "$SRC_DIR" fetch --tags --prune
  else
    rm -rf "$SRC_DIR"
    git clone "$REPO_URL" "$SRC_DIR"
  fi

  git -C "$SRC_DIR" checkout -q "$GIT_REF"
  # If it's a branch, pull; if it's a tag/sha, this is a no-op or harmless failure.
  git -C "$SRC_DIR" pull --ff-only >/dev/null 2>&1 || true
fi

VENV_DIR="$INSTALL_DIR/venv"
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
  "$PYTHON_EXE" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m pip install --upgrade pip >/dev/null
"$VENV_DIR/bin/python" -m pip install --upgrade "$SRC_DIR" >/dev/null

LAUNCHER_DIR="$HOME/.local/bin"
mkdir -p "$LAUNCHER_DIR"

cat >"$LAUNCHER_DIR/cryptclash" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec "$VENV_DIR/bin/cryptclash" "\$@"
EOF
chmod +x "$LAUNCHER_DIR/cryptclash"

if [[ ":$PATH:" != *":$LAUNCHER_DIR:"* ]]; then
  echo
  echo "Installed, but $LAUNCHER_DIR is not on your PATH."
  echo "Run with: $VENV_DIR/bin/cryptclash"
  echo "Or add to PATH (zsh/bash):"
  echo "  echo 'export PATH=\"$LAUNCHER_DIR:\$PATH\"' >> ~/.zshrc"
  echo "  source ~/.zshrc"
else
  echo
  echo "Installed. Run: cryptclash"
fi

