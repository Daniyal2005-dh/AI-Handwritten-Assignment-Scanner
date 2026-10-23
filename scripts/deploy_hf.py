"""Deploy the AI Assignment Scanner to a Hugging Face Space.

Prerequisites (one time):
    pip install -c requirements.txt huggingface_hub
    run and login in the browser when prompted (needs an HF account)

Usage:
    .venv\\Scripts\\python scripts\\deploy_hf.py                  # creates + pushes the Space
    .venv\\Scripts\\python scripts\\deploy_hf.py --space-token?    # see --help
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

HF_FRONTMATTER = """\
---
title: AI Assignment Scanner
emoji: \U0001f58b\ufe0f
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 7860
pinned: true
---

"""

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "data", "node_modules"}
SKIP_FILES = {".gitignore", ".dockerignore"}


def default_username() -> str | None:
    from huggingface_hub import HfApi

    try:
        return HfApi().whoami()["name"]
    except Exception:
        return None


def read_with_frontmatter(path: Path) -> bytes:
    """Prefix the repo README with Space metadata when pushing to HF."""
    body = path.read_text(encoding="utf-8")
    return (HF_FRONTMATTER + body).encode("utf-8")


def collect_files() -> list[tuple[Path, str]]:
    """All project files for upload, excluding local-only artifacts."""
    out: list[tuple[Path, str]] = []

    def walk(d: Path) -> None:
        for entry in d.iterdir():
            if entry.name in SKIP_FILES:
                continue
            if entry.is_dir():
                if entry.name in SKIP_DIRS:
                    continue
                walk(entry)
            elif entry.is_file():
                rel = entry.relative_to(ROOT).as_posix()
                if entry.suffix in (".pyc", ".db", ".csv"):
                    continue
                if rel.startswith("data/") or "pycache" in rel:
                    continue
                out.append((entry, rel))

    walk(ROOT)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--space-name",
        default="AI-Assignment-Scanner",
        help="Space repo name under your account",
    )
    parser.add_argument("--hardware", default="cpu-basic")
    parser.add_argument("--private", action="store_true", help="create a private Space")
    parser.add_argument("--mock", action="store_true", help="deploy in mock mode (no secrets)")
    args = parser.parse_args()

    try:
        from huggingface_hub import HfApi, create_repo, get_token
    except ImportError:
        print("First run: .venv\\Scripts\\pip install huggingface_hub")
        sys.exit(1)

    if get_token() is None:
        print("No HF token found — starting browser login…")
        from huggingface_hub import login

        login()  # interactive browser flow

    username = default_username()
    if username is None:
        print("Could not determine HF username (login failed?)")
        sys.exit(1)

    repo_id = f"{username}/{args.space_name}"
    api = HfApi()

    print(f"Creating Space {repo_id} (sdk=docker, hardware={args.hardware}) …")
    create_repo(
        repo_id,
        repo_type="space",
        space_sdk="docker",
        space_hardware=args.hardware,
        exist_ok=True,
        private=args.private,
    )

    print("Uploading files …")
    upload_files: list[tuple[str, bytes]] = []
    for src, rel in collect_files():
        if rel == "README.md":
            upload_files.append((rel, read_with_frontmatter(src)))
        else:
            upload_files.append((rel, src.read_bytes()))

    for rel, blob in upload_files:
        api.upload_file(
            path_or_fileobj=blob,
            path_in_repo=rel,
            repo_id=repo_id,
            repo_type="space",
        )
        print(f"  + {rel}")

    print("Set SCANNER_RECOGNIZER=trocr …")
    api.add_space_secret(
        repo_id=repo_id,
        key="SCANNER_RECOGNIZER",
        value=("mock" if args.mock else "trocr"),
    )

    print()
    print("=" * 60)
    print("Deployed! Build progress & URL:")
    print(f"  https://huggingface.co/spaces/{repo_id}")
    print("Live app URL after build (~5-10 min first build, big torch image):")
    print(f"  https://{username.lower().replace('.', '-')}-{args.space_name.lower().replace('_', '-')}.hf.space")
    print("=" * 60)


if __name__ == "__main__":
    main()
