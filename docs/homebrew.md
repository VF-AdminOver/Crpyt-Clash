# Homebrew Distribution Guide (No Personal Name)

This document explains how to distribute the game through Homebrew using an organization-style tap name.

## Recommended public command name

Use:

- `cryptclash` (primary)
- `crypt-clash` (alias)

Legacy aliases (`dnd`, `DND`) can remain temporarily for compatibility.

## Naming model for Homebrew (without personal username branding)

Homebrew taps must live under a GitHub owner namespace, but that owner can be an org (not a person).

Recommended setup:

1. Create an org, for example: `cryptclash`.
2. Create tap repo: `homebrew-games` (or `homebrew-tap`).
3. Users install with:

```bash
brew tap cryptclash/games
brew install crypt-clash
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

- `/Users/brianvassell/DND-cli/docs/homebrew-tap.md`

## 1) Build release artifacts (optional)

From this repo:

```bash
python3 -m pip install --upgrade build
python3 -m build
```

Publish a GitHub release (for example `v0.2.0`) and attach source tarball.

## 2) Create formula in tap repo

File path in tap repo:

`Formula/crypt-clash.rb`

If you want the sha256 computed automatically, use:

```bash
python3 /Users/brianvassell/DND-cli/scripts/make_homebrew_formula.py --org <ORG> --repo <REPO> --tag v0.2.0 --out Formula/crypt-clash.rb
```

Starter formula:

```ruby
class CryptClash < Formula
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
brew install crypt-clash
```

## 4) User run

```bash
cryptclash
```

## Trademark-safe packaging tips

- Avoid brand names that may conflict with existing marks in package/formula names.
- Keep repo/formula/command aligned on neutral branding:
  - repo: `crypt-clash-cli`
  - formula: `crypt-clash`
  - command: `cryptclash`
- Keep legacy aliases only for migration, then remove in a major release.
