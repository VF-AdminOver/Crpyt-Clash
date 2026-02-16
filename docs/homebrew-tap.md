# Homebrew Tap Setup (Public Distribution)

This guide makes your game installable via:

```bash
brew tap <ORG>/games
brew install crypt-clash
cryptclash
```

## What you need

- A public GitHub org/user and repo for the game (example: `<ORG>/<REPO>`)
- A separate public GitHub repo for the Homebrew tap (example: `<ORG>/homebrew-games`)
- A git tag + GitHub release for the game (example: `v0.1.0`)

## 1) Create the tap repo

On GitHub, create a new public repo under your org/user:

- Repo name: `homebrew-games`
- (Homebrew requires the `homebrew-` prefix for tap repos)

Clone it:

```bash
git clone https://github.com/<ORG>/homebrew-games.git
cd homebrew-games
mkdir -p Formula
```

## 2) Tag and publish a release for the game

In your game repo:

1. Update version in `pyproject.toml` (and docs if needed).
2. Commit the change.
3. Create and push a tag:

```bash
git tag v0.1.0
git push --tags
```

GitHub automatically serves a stable source tarball at:

- `https://github.com/<ORG>/<REPO>/archive/refs/tags/v0.1.0.tar.gz`

Tip: if your system Python blocks `pip install` (PEP 668), use a venv for build tooling:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip build
python -m build
```

## 3) Generate the formula file

From this repo (`/Users/brianvassell/DND-cli`), generate `Formula/crypt-clash.rb` for your tap:

```bash
python3 /Users/brianvassell/DND-cli/scripts/make_homebrew_formula.py \
  --org <ORG> \
  --repo <REPO> \
  --tag v0.1.0 \
  --out Formula/crypt-clash.rb
```

That script downloads the tag tarball and computes the `sha256` automatically.

Commit + push from inside the tap repo:

```bash
git add Formula/crypt-clash.rb
git commit -m "Add crypt-clash v0.1.0"
git push
```

## 4) Verify install (as a player)

On a clean machine (or after uninstalling old installs), run:

```bash
brew tap <ORG>/games https://github.com/<ORG>/homebrew-games
brew install crypt-clash
cryptclash tip
cryptclash
```

To upgrade after you publish a new release:

```bash
brew update
brew upgrade crypt-clash
```

## 5) Update for a new version

When you release `v0.1.1`:

1. Update version + tag + push in the game repo.
2. Re-run the generator with `--tag v0.1.1` and overwrite `Formula/crypt-clash.rb`.
3. Commit + push the tap repo.
