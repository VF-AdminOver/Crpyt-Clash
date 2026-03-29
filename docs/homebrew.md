# Homebrew Distribution Guide (No Personal Name)

This document explains how to distribute the game through Homebrew using an organization-style tap name.

## Recommended public command name

Use:

- `cryptclash` (primary)
- `crypt-clash` (alias)
- Homebrew formula: `dnd`

Legacy aliases (`dnd`, `DND`) can remain temporarily for compatibility.

## Naming model for Homebrew (without personal username branding)

Homebrew taps must live under a GitHub owner namespace, but that owner can be an org (not a person).

Recommended setup:

1. Create an org, for example: `cryptclash`.
2. Create tap repo: `homebrew-games` (or `homebrew-tap`).
3. Users install with:

```bash
brew tap cryptclash/games
brew install dnd
```

This avoids personal-name commands like `yourname/tap`.

## Fastest "brew-assisted" install today (no tap maintenance yet)

```bash
brew install pipx
pipx ensurepath
pipx install "git+https://github.com/<ORG>/<REPO>.git"
cryptclash
```

## Full tap workflow (recommended for public release)

## 0) Use the new tap guide

For end-to-end setup, follow:

- `/path/to/project/docs/homebrew-tap.md`

## 1) Build release artifacts (optional)

From this repo:

```bash
python3 -m pip install --upgrade build
python3 -m build
```

Publish a GitHub release (for example `v0.2.0`) and attach source tarball.

## 2) Create formula in tap repo

File path in tap repo:

`Formula/dnd.rb`

If you want the sha256 computed automatically, use:

```bash
python3 /path/to/project/scripts/make_homebrew_formula.py --org <ORG> --repo <REPO> --tag v0.2.0 --formula-name dnd --out Formula/dnd.rb
```

Important: Homebrew does not automatically install `pyproject.toml` dependencies into the virtualenv. You must vendor
Python deps (like `textual`) as `resource` blocks in the formula. The easiest way is:

```bash
brew update-python-resources --print-only --ignore-non-pypi-packages <ORG>/<TAP>/dnd
```

Starter formula:

```ruby
class Dnd < Formula
  include Language::Python::Virtualenv

  desc "Terminal RPG adventure game"
  homepage "https://github.com/<ORG>/<REPO>"
  url "https://github.com/<ORG>/<REPO>/archive/refs/tags/v0.2.0.tar.gz"
  sha256 "<RELEASE_TARBALL_SHA256>"
  license "MIT"

  depends_on "python@3.12"

  def install
    virtualenv_install_with_resources
  end

  test do
    output = shell_output("#{bin}/cryptclash tip")
    assert_match "Tip:", output
  end
end
```

## 3) User install

```bash
brew tap cryptclash/games
brew install dnd
```

## 4) User run

```bash
cryptclash
```

## Trademark-safe packaging tips

- Avoid brand names that may conflict with existing marks in package/formula names.
- Keep repo/formula/command aligned on neutral branding:
  - repo: `crypt-clash-cli`
  - formula: `dnd`
  - command: `cryptclash`
- Keep legacy aliases only for migration, then remove in a major release.
