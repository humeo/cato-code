from __future__ import annotations

import pytest

from repocraft.config import RepoCraftConfig, parse_issue_url, repo_id_from_url


def test_config_parses_owner_repo():
    cfg = RepoCraftConfig(repo_url="https://github.com/psf/requests", issue_number=1)
    assert cfg.owner == "psf"
    assert cfg.repo == "requests"


def test_config_invalid_url():
    with pytest.raises(ValueError, match="Invalid GitHub repo URL"):
        RepoCraftConfig(repo_url="https://notgithub.com/foo", issue_number=1)


def test_parse_issue_url():
    owner, repo, num = parse_issue_url("https://github.com/psf/requests/issues/42")
    assert owner == "psf"
    assert repo == "requests"
    assert num == 42


def test_parse_issue_url_invalid():
    with pytest.raises(ValueError, match="Invalid GitHub issue URL"):
        parse_issue_url("https://github.com/psf/requests")


def test_repo_id_from_url():
    repo_id = repo_id_from_url("https://github.com/psf/requests")
    assert repo_id == "psf-requests"


def test_repo_id_from_url_with_git_suffix():
    repo_id = repo_id_from_url("https://github.com/psf/requests.git")
    assert repo_id == "psf-requests"
