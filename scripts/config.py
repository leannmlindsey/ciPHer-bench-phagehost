"""Resolve env-sourced paths for ciPHer-bench-phagehost wrappers.

Usage:

    from config import PHAGEHOST_REPO, CIPHER_REPO, CIPHER_VAL_GENOMES, PHAGEHOST_OUTPUT_ROOT

Before running:

    cp config/phagehost.env.template phagehost.env
    pico phagehost.env  ; source phagehost.env
"""
import os
import sys
from pathlib import Path


def _require_env(name: str, hint: str = "") -> Path:
    val = os.environ.get(name)
    if not val:
        sys.exit(
            f"ERROR: env var {name} is not set.\n"
            f"  source <repo_root>/phagehost.env first. See SETUP.md. {hint}"
        )
    p = Path(val)
    if not p.exists():
        sys.exit(
            f"ERROR: env var {name} = {val} does not exist on disk.\n"
            f"  Edit phagehost.env to fix. {hint}"
        )
    return p


PHAGEHOST_REPO     = _require_env("PHAGEHOST_REPO", "(point at extracted PhageHost tarball dir)")
CIPHER_REPO        = _require_env("CIPHER_REPO", "(point at your cipher checkout)")
CIPHER_VAL_GENOMES = _require_env("CIPHER_VAL_GENOMES", "(point at cipher_data/validation_genomes)")

_out = os.environ.get("PHAGEHOST_OUTPUT_ROOT")
if not _out:
    sys.exit("ERROR: env var PHAGEHOST_OUTPUT_ROOT is not set. source phagehost.env first.")
PHAGEHOST_OUTPUT_ROOT = Path(_out)
PHAGEHOST_OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
