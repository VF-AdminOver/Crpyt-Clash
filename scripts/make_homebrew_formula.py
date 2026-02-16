#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import sys
import textwrap
import urllib.request


def _sha256_of_url(url: str) -> str:
    with urllib.request.urlopen(url) as resp:  # noqa: S310
        h = hashlib.sha256()
        while True:
            chunk = resp.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
        return h.hexdigest()


def _render_formula(*, org: str, repo: str, tag: str, sha256: str, python_dep: str) -> str:
    homepage = f"https://github.com/{org}/{repo}"
    url = f"https://github.com/{org}/{repo}/archive/refs/tags/{tag}.tar.gz"
    return textwrap.dedent(
        f"""\
        class CryptClash < Formula
          include Language::Python::Virtualenv

          desc "Terminal RPG adventure game"
          homepage "{homepage}"
          url "{url}"
          sha256 "{sha256}"
          license "MIT"

          depends_on "{python_dep}"

          def install
            virtualenv_install_with_resources
          end

          test do
            output = shell_output("#{{bin}}/cryptclash tip")
            assert_match "Tip:", output
          end
        end
        """
    )


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(
        description="Generate a Homebrew formula for Crypt Clash from a GitHub tag tarball."
    )
    p.add_argument("--org", required=True, help="GitHub org/user, e.g. cryptclash")
    p.add_argument("--repo", required=True, help="GitHub repo, e.g. crypt-clash-cli")
    p.add_argument("--tag", required=True, help="Git tag, e.g. v0.1.0")
    p.add_argument(
        "--python",
        default="python@3.12",
        dest="python_dep",
        help='Homebrew python dependency, e.g. "python@3.12"',
    )
    p.add_argument(
        "--sha256",
        default="",
        help="Optional sha256; if omitted, downloads the tag tarball and computes it.",
    )
    p.add_argument(
        "--out",
        default="",
        help="Write formula to a file path (otherwise prints to stdout).",
    )
    args = p.parse_args(argv)

    url = f"https://github.com/{args.org}/{args.repo}/archive/refs/tags/{args.tag}.tar.gz"
    sha256 = args.sha256.strip() or _sha256_of_url(url)

    formula = _render_formula(
        org=args.org,
        repo=args.repo,
        tag=args.tag,
        sha256=sha256,
        python_dep=args.python_dep,
    )

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(formula)
        return 0

    sys.stdout.write(formula)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

