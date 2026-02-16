# Crypt Clash Installation Guide

This guide is for regular players who want to install and run Crypt Clash locally.

## Requirements

- macOS, Linux, or Windows (with a terminal)
- Python `3.11+`
- Git

## Fastest install (Homebrew + pipx)

```bash
brew install pipx
pipx ensurepath
pipx install "git+https://github.com/<your-org>/<your-repo>.git"
cryptclash
```

## Homebrew tap install (best UX once you publish a tap)

After you publish a Homebrew tap (see `/Users/brianvassell/DND-cli/docs/homebrew-tap.md`), players can run:

```bash
brew tap VF-AdminOver/games
brew install crypt-clash
cryptclash
```

Or as a single command:

```bash
brew install vf-adminover/games/crypt-clash && cryptclash
```

## One-command install (macOS/Linux)

If you host this repo on GitHub, players can run:

```bash
curl -fsSL https://raw.githubusercontent.com/VF-AdminOver/Crpyt-Clash/main/scripts/install.sh | bash -s -- --repo https://github.com/VF-AdminOver/Crpyt-Clash.git
cryptclash
```

## 1) Clone the repo

```bash
git clone <your-repo-url> /Users/brianvassell/DND-cli
cd /Users/brianvassell/DND-cli
```

## 2) Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 3) Install the game (local source)

```bash
pip install -e .
```

## 4) Start the game

```bash
cryptclash
```

Legacy aliases also work for now:

```bash
crypt-clash
DND
```

## If the command says `not found`

Run:

```bash
source /Users/brianvassell/DND-cli/.venv/bin/activate
pip install -e /Users/brianvassell/DND-cli
```

Then try:

```bash
cryptclash
```

## Optional: make launch simple every day (macOS zsh)

Add this to `~/.zshrc`:

```bash
alias cryptclash='source /Users/brianvassell/DND-cli/.venv/bin/activate && cryptclash'
```

Then reload shell config:

```bash
source ~/.zshrc
```

## Verify it works

```bash
cryptclash tip
cryptclash roster
```

If those commands run, your install is good.
