# Codebase Graph Publishing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish `codebase-graph` to `humeo/codebase-graph`, add a tag-driven GitHub release workflow, and ship a `curl -fsSL ... | bash` installer that installs `cg` from GitHub release wheels.

**Architecture:** Keep the release-critical logic small and testable. A Python release helper validates tag/version alignment, a POSIX shell installer resolves a GitHub release wheel and installs it with `uv tool install --force`, and a GitHub Actions workflow wires together checkout, uv setup, tests, build, and release creation on `v*` tags.

**Tech Stack:** Python 3.12+, uv, pytest, click, hatchling, POSIX shell, GitHub Actions, GitHub CLI

---

## File Structure

- Modify: `.gitignore` — ignore local-only publish noise
- Modify: `README.md` — public install, release, and verification docs
- Create: `docs/releasing.md` — maintainer release runbook
- Create: `.github/workflows/release.yml` — tag-triggered build/test/release workflow
- Create: `scripts/install.sh` — public installer entry point for `curl | bash`
- Create: `scripts/verify_release_version.py` — thin CLI wrapper used by CI
- Create: `src/codebase_graph/release.py` — testable version/tag validation logic
- Create: `tests/test_release.py` — unit tests for release version guard
- Create: `tests/test_install_script.py` — integration-style tests for installer behavior with fake `curl`/`uv`

---

### Task 1: Release Version Guard

**Files:**
- Create: `src/codebase_graph/release.py`
- Create: `scripts/verify_release_version.py`
- Create: `tests/test_release.py`

- [ ] **Step 1: Write the failing release guard tests**

`tests/test_release.py`:

```python
"""Tests for release version helpers."""

from pathlib import Path

import pytest

from codebase_graph.release import (
    normalize_release_tag,
    project_version_from_pyproject,
    verify_release_tag,
)


def test_normalize_release_tag_adds_prefix():
    assert normalize_release_tag("0.1.0") == "v0.1.0"


def test_normalize_release_tag_keeps_prefixed_tag():
    assert normalize_release_tag("v0.1.0") == "v0.1.0"


def test_project_version_from_pyproject_reads_project_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "codebase-graph"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    assert project_version_from_pyproject(pyproject) == "0.1.0"


def test_verify_release_tag_raises_on_version_mismatch(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "codebase-graph"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="does not match"):
        verify_release_tag("v0.1.1", pyproject)


def test_verify_release_tag_accepts_matching_version(tmp_path):
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        '[project]\nname = "codebase-graph"\nversion = "0.1.0"\n',
        encoding="utf-8",
    )

    verify_release_tag("v0.1.0", pyproject)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
cd /Users/koltenluca/code-github/codebase-graph
uv run pytest tests/test_release.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'codebase_graph.release'`.

- [ ] **Step 3: Implement the release helper module**

`src/codebase_graph/release.py`:

```python
"""Helpers for validating GitHub release metadata."""

from pathlib import Path
import tomllib


def normalize_release_tag(tag: str) -> str:
    return tag if tag.startswith("v") else f"v{tag}"


def project_version_from_pyproject(pyproject_path: Path) -> str:
    data = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    return data["project"]["version"]


def verify_release_tag(tag: str, pyproject_path: Path) -> None:
    normalized = normalize_release_tag(tag)
    expected = f"v{project_version_from_pyproject(pyproject_path)}"
    if normalized != expected:
        raise ValueError(
            f"Release tag {normalized!r} does not match pyproject version {expected!r}."
        )
```

- [ ] **Step 4: Add the CI wrapper script**

`scripts/verify_release_version.py`:

```python
#!/usr/bin/env python3
"""Fail CI if the pushed release tag and package version disagree."""

from pathlib import Path
import sys

from codebase_graph.release import verify_release_tag


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Usage: verify_release_version.py <tag>", file=sys.stderr)
        return 2

    tag = argv[1]
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"

    try:
        verify_release_tag(tag, pyproject)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"Release tag {tag} matches pyproject.toml")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
```

- [ ] **Step 5: Run the focused tests and wrapper**

Run:

```bash
uv run pytest tests/test_release.py -v
uv run python scripts/verify_release_version.py v0.1.0
```

Expected:
- tests PASS
- script prints `Release tag v0.1.0 matches pyproject.toml`

- [ ] **Step 6: Commit the release guard**

```bash
git add src/codebase_graph/release.py scripts/verify_release_version.py tests/test_release.py
git commit -m "feat(release): validate tag version against package metadata"
```

---

### Task 2: Release Wheel Installer

**Files:**
- Create: `scripts/install.sh`
- Create: `tests/test_install_script.py`

- [ ] **Step 1: Write failing installer tests**

`tests/test_install_script.py`:

```python
"""Tests for the public install script."""

from pathlib import Path
import os
import subprocess
import textwrap


ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "install.sh"


def _write_fake_bin(bin_dir: Path, name: str, body: str) -> None:
    path = bin_dir / name
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _run_install(tmp_path, *, release_json: str, version: str | None = None):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "calls.log"

    _write_fake_bin(
        bin_dir,
        "curl",
        textwrap.dedent(
            f"""\
            #!/bin/sh
            echo "curl:$*" >> "{log_path}"
            case "$*" in
              *api.github.com*)
                printf '%s' '{release_json}'
                ;;
              *example.test*|*releases/download*)
                out=""
                while [ "$#" -gt 0 ]; do
                  if [ "$1" = "-o" ]; then
                    out="$2"
                    shift 2
                    continue
                  fi
                  shift
                done
                printf 'wheel' > "$out"
                ;;
              *astral.sh/uv/install.sh*)
                printf '#!/bin/sh\\nexit 0\\n'
                ;;
            esac
            """
        ),
    )
    _write_fake_bin(
        bin_dir,
        "uname",
        """#!/bin/sh\nprintf 'Linux\\n'\n""",
    )
    _write_fake_bin(
        bin_dir,
        "uv",
        textwrap.dedent(
            f"""\
            #!/bin/sh
            echo "uv:$*" >> "{log_path}"
            exit 0
            """
        ),
    )

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"
    env["HOME"] = str(tmp_path)
    if version is not None:
        env["CODEBASE_GRAPH_VERSION"] = version

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result, log_path.read_text(encoding="utf-8")


def test_install_script_uses_latest_release_when_version_unset(tmp_path):
    result, calls = _run_install(
        tmp_path,
        release_json='{"assets":[{"name":"codebase_graph-0.1.0-py3-none-any.whl","browser_download_url":"https://example.test/v0.1.0/codebase_graph-0.1.0-py3-none-any.whl"}]}',
    )

    assert result.returncode == 0
    assert "releases/latest" in calls
    assert "uv:tool install --force" in calls


def test_install_script_normalizes_explicit_version(tmp_path):
    result, calls = _run_install(
        tmp_path,
        release_json='{"assets":[{"name":"codebase_graph-0.1.0-py3-none-any.whl","browser_download_url":"https://example.test/v0.1.0/codebase_graph-0.1.0-py3-none-any.whl"}]}',
        version="0.1.0",
    )

    assert result.returncode == 0
    assert "releases/tags/v0.1.0" in calls


def test_install_script_fails_without_matching_wheel(tmp_path):
    result, _calls = _run_install(
        tmp_path,
        release_json='{"assets":[{"name":"codebase_graph-0.1.0.tar.gz","browser_download_url":"https://example.test/v0.1.0/codebase_graph-0.1.0.tar.gz"}]}',
    )

    assert result.returncode == 1
    assert "No wheel asset found" in result.stderr


def test_install_script_fails_on_unsupported_platform(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "uname").write_text("#!/bin/sh\nprintf 'FreeBSD\\n'\n", encoding="utf-8")
    (bin_dir / "uname").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Unsupported platform" in result.stderr
```

- [ ] **Step 2: Run the installer tests to verify they fail**

Run:

```bash
uv run pytest tests/test_install_script.py -v
```

Expected: FAIL because `scripts/install.sh` does not exist yet.

- [ ] **Step 3: Implement the install script**

`scripts/install.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

REPO="${CODEBASE_GRAPH_REPO:-humeo/codebase-graph}"
VERSION="${CODEBASE_GRAPH_VERSION:-}"
API_BASE="https://api.github.com/repos/${REPO}/releases"

need_cmd() {
  command -v "$1" >/dev/null 2>&1
}

platform_name() {
  case "$(uname -s)" in
    Linux|Darwin) return 0 ;;
    *)
      echo "Unsupported platform: $(uname -s). Only Linux and macOS are supported." >&2
      exit 1
      ;;
  esac
}

download() {
  if need_cmd curl; then
    curl -fsSL "$@"
    return
  fi
  if need_cmd wget; then
    wget -qO- "$1"
    return
  fi
  echo "Either curl or wget is required." >&2
  exit 1
}

download_to_file() {
  local url="$1"
  local out="$2"
  if need_cmd curl; then
    curl -fsSL "$url" -o "$out"
    return
  fi
  wget -qO "$out" "$url"
}

ensure_uv() {
  if need_cmd uv; then
    return
  fi
  if ! need_cmd curl; then
    echo "uv is missing and curl is required to bootstrap it." >&2
    exit 1
  fi
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  need_cmd uv || {
    echo "uv installation completed but uv was not found on PATH." >&2
    exit 1
  }
}

release_url() {
  if [ -z "$VERSION" ]; then
    printf '%s/latest' "$API_BASE"
    return
  fi

  case "$VERSION" in
    v*) printf '%s/tags/%s' "$API_BASE" "$VERSION" ;;
    *) printf '%s/tags/v%s' "$API_BASE" "$VERSION" ;;
  esac
}

select_wheel_url() {
  awk -F'"' '/browser_download_url/ && /codebase_graph-.*-py3-none-any\\.whl/ { print $4; exit }'
}

main() {
  platform_name
  ensure_uv

  local tmpdir
  tmpdir="$(mktemp -d)"
  trap 'rm -rf "$tmpdir"' EXIT

  local release_json wheel_url wheel_path
  release_json="$(download "$(release_url)")"
  wheel_url="$(printf '%s' "$release_json" | select_wheel_url)"

  if [ -z "$wheel_url" ]; then
    echo "No wheel asset found in GitHub release metadata." >&2
    exit 1
  fi

  wheel_path="$tmpdir/codebase-graph.whl"
  download_to_file "$wheel_url" "$wheel_path"
  uv tool install --force "$wheel_path"
  echo "codebase-graph installed. Run 'cg --version' to verify."
}

main "$@"
```

- [ ] **Step 4: Run the installer tests until they pass**

Run:

```bash
uv run pytest tests/test_install_script.py -v
```

Expected: PASS.

- [ ] **Step 5: Run a local smoke check on the script entry point**

Run:

```bash
bash -n scripts/install.sh
```

Expected: no output, exit status `0`.

- [ ] **Step 6: Commit the installer**

```bash
git add scripts/install.sh tests/test_install_script.py
git commit -m "feat(installer): add GitHub release wheel installer"
```

---

### Task 3: Release Workflow, Docs, and Git Hygiene

**Files:**
- Create: `.github/workflows/release.yml`
- Create: `docs/releasing.md`
- Modify: `.gitignore`
- Modify: `README.md`

- [ ] **Step 1: Update git ignore rules for local-only files**

Append these entries to `.gitignore`:

```gitignore
.pytest_cache/
.merge-backups/
.nvimlog
```

- [ ] **Step 2: Update the README install and release sections**

Revise `README.md` so it explicitly includes all of these items from the spec:

- public repository URL: `https://github.com/humeo/codebase-graph`
- latest install command
- pinned-version install command
- install verification commands
- short explanation that the installer bootstraps `uv` if it is missing
- short explanation that installs come from GitHub release wheels, not `main`

The `Install` section must include these exact commands:

```bash
curl -fsSL https://raw.githubusercontent.com/humeo/codebase-graph/main/scripts/install.sh | bash
curl -fsSL https://raw.githubusercontent.com/humeo/codebase-graph/main/scripts/install.sh | CODEBASE_GRAPH_VERSION=0.1.0 bash
cg --version
cg --help
```

Keep the existing local-development instructions under a separate "Install From Source" or "Development" section.

- [ ] **Step 3: Add the maintainer release runbook**

`docs/releasing.md`:

````md
# Releasing codebase-graph

## Preconditions

- Working tree is clean
- `uv run pytest -v --tb=short` passes
- `uv build` passes
- `pyproject.toml` and `src/codebase_graph/__init__.py` contain the target version

## Release steps

1. Commit the release-ready changes.
2. Create the public repository if it does not exist:

```bash
gh repo create humeo/codebase-graph --public --source=. --remote=origin --push
```

3. Tag the release:

```bash
git tag v0.1.0
git push origin v0.1.0
```

4. Watch the release workflow complete.
5. Verify the release assets and install command.
````

- [ ] **Step 4: Add the GitHub Actions release workflow**

`.github/workflows/release.yml`:

```yaml
name: release

on:
  push:
    tags:
      - "v*"

permissions:
  contents: write

jobs:
  build-and-release:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v6

      - name: Install uv
        run: |
          curl -LsSf https://astral.sh/uv/install.sh | sh
          echo "$HOME/.local/bin" >> "$GITHUB_PATH"

      - name: Install Python 3.12
        run: uv python install 3.12

      - name: Verify release version
        run: uv run python scripts/verify_release_version.py "${{ github.ref_name }}"

      - name: Sync dependencies
        run: uv sync --python 3.12

      - name: Run tests
        run: uv run pytest -v --tb=short

      - name: Build distributions
        run: uv build

      - name: Create GitHub release
        env:
          GH_TOKEN: ${{ github.token }}
        run: gh release create "${{ github.ref_name }}" dist/* --generate-notes --verify-tag
```

- [ ] **Step 5: Verify docs and workflow locally**

Run:

```bash
uv run python scripts/verify_release_version.py v0.1.0
uv build
git diff -- .gitignore README.md docs/releasing.md .github/workflows/release.yml
```

Expected:
- version script passes
- build produces `dist/*.whl` and `dist/*.tar.gz`
- diff shows only the intended publish/docs/workflow changes

- [ ] **Step 6: Commit the release workflow and docs**

```bash
git add .gitignore README.md docs/releasing.md .github/workflows/release.yml
git commit -m "feat(release): add GitHub release workflow and publish docs"
```

---

### Task 4: Publish the Repository and Create the First Release

**Files:**
- Modify: `.git/config` via git/gh commands
- Remote state: `humeo/codebase-graph`

- [ ] **Step 1: Run the full local verification suite**

Run:

```bash
uv run pytest -v --tb=short
uv build
```

Expected:
- all tests PASS
- build creates the wheel and source distribution in `dist/`

- [ ] **Step 2: Inspect the worktree and commit any remaining intended changes**

There should be no new implementation files left to commit here, because Tasks 1-3 already end with commits.

Run:

```bash
git status --short
```

Expected: working tree is clean except for unrelated untracked files you intentionally leave alone. If it is not clean, stop and understand why before publishing.

- [ ] **Step 3: Create the public GitHub repository and push `main`**

Run:

```bash
gh repo create humeo/codebase-graph --public --source=. --remote=origin --push
```

Expected:
- `origin` is added
- `main` is pushed
- the repository exists at `https://github.com/humeo/codebase-graph`

- [ ] **Step 4: Create and push the first release tag**

Run:

```bash
git tag v0.1.0
git push origin v0.1.0
```

Expected: GitHub Actions release workflow starts for tag `v0.1.0`.

- [ ] **Step 5: Watch the workflow and verify the release**

Run:

```bash
gh run list -R humeo/codebase-graph --workflow release.yml --limit 1
gh run watch -R humeo/codebase-graph
gh release view v0.1.0 -R humeo/codebase-graph
```

Expected:
- workflow finishes successfully
- release `v0.1.0` exists
- release includes both `dist/*.whl` and `dist/*.tar.gz`

- [ ] **Step 6: Verify the public installer against the real repository**

Run:

```bash
curl -fsSL https://raw.githubusercontent.com/humeo/codebase-graph/main/scripts/install.sh | bash
cg --version
cg --help
```

Expected:
- installer succeeds
- `cg --version` reports `0.1.0`
- `cg --help` shows the CLI commands

- [ ] **Step 7: Final cleanup commit if documentation drift was introduced during verification**

If no files changed during verification, skip this step. Otherwise:

```bash
git add README.md docs/releasing.md
git commit -m "chore: finalize publishing verification notes"
git push origin main
```
