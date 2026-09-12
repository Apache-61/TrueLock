"""The `worker` command line (orchestrator/workers/cli.py, config.py).

Covers argument wiring and the two things a new machine gets wrong:
identity (`WORKER_ID`) and configuration loading.
"""
from __future__ import annotations


import pytest

from orchestrator.workers.cli import build_parser
from orchestrator.workers.config import (
    ConfigError,
    find_repo_root,
    load_config,
    parse_dotenv,
    validate_worker_id,
)

ENV = {"WORKER_ID": "WORKER-01", "GITHUB_OWNER": "apache-61", "GITHUB_REPO": "truelock"}


class TestWorkerId:
    @pytest.mark.parametrize("worker_id", ["WORKER-01", "WORKER-04", "laptop-ana", "ci_runner_2"])
    def test_valid_identities(self, worker_id):
        assert validate_worker_id(worker_id) == worker_id

    @pytest.mark.parametrize("worker_id", ["", "  ", "ab", "1worker", "worker 01", "w"*33,
                                           "worker/01", "worker@host"])
    def test_invalid_identities_are_refused(self, worker_id):
        with pytest.raises(ConfigError):
            validate_worker_id(worker_id)

    def test_the_missing_id_message_tells_you_what_to_type(self):
        """A new machine's first failure should be self-service."""
        with pytest.raises(ConfigError) as caught:
            validate_worker_id("")
        message = str(caught.value)
        assert 'export WORKER_ID="WORKER-01"' in message
        assert "CONTRIBUTING.md" in message


class TestDotEnv:
    def test_parses_the_projects_env_example_shape(self):
        values = parse_dotenv(
            "# comment\n"
            "WORKER_ID=WORKER-02\n"
            "export GITHUB_TOKEN=abc123\n"
            'GITHUB_OWNER="apache-61"\n'
            "GITHUB_REPO=truelock   # trailing comment\n"
            "\n"
            "EMPTY=\n"
        )
        assert values == {
            "WORKER_ID": "WORKER-02",
            "GITHUB_TOKEN": "abc123",
            "GITHUB_OWNER": "apache-61",
            "GITHUB_REPO": "truelock",
            "EMPTY": "",
        }

    def test_a_hash_inside_a_quoted_value_is_kept(self):
        assert parse_dotenv('TOKEN="abc#def"')["TOKEN"] == "abc#def"

    def test_the_real_env_example_parses(self):
        example = find_repo_root() / ".env.example"
        values = parse_dotenv(example.read_text(encoding="utf-8"))
        assert "WORKER_ID" in values
        assert "GITHUB_TOKEN" in values
        assert values["GITHUB_OWNER"] == "apache-61"


class TestLoadConfig:
    def test_environment_supplies_identity(self, tmp_path):
        config = load_config(repo_root=tmp_path, environ=dict(ENV))
        assert config.worker_id == "WORKER-01"
        assert config.slug == "apache-61/truelock"
        assert config.base_branch == "main"

    def test_cli_overrides_beat_the_environment(self, tmp_path):
        config = load_config(repo_root=tmp_path, environ=dict(ENV),
                             overrides={"worker_id": "WORKER-03"})
        assert config.worker_id == "WORKER-03"

    def test_dotenv_is_read_when_the_environment_is_silent(self, tmp_path):
        (tmp_path / ".env").write_text(
            "WORKER_ID=WORKER-04\nGITHUB_OWNER=apache-61\nGITHUB_REPO=truelock\n"
        )
        config = load_config(repo_root=tmp_path, environ={})
        assert config.worker_id == "WORKER-04"

    def test_the_environment_beats_dotenv(self, tmp_path):
        (tmp_path / ".env").write_text(
            "WORKER_ID=WORKER-04\nGITHUB_OWNER=a\nGITHUB_REPO=b\n"
        )
        config = load_config(repo_root=tmp_path, environ=dict(ENV))
        assert config.worker_id == "WORKER-01"

    def test_missing_repository_coordinates_are_refused(self, tmp_path):
        with pytest.raises(ConfigError) as caught:
            load_config(repo_root=tmp_path, environ={"WORKER_ID": "WORKER-01"})
        assert "GITHUB_OWNER" in str(caught.value)

    def test_a_live_run_without_a_token_is_refused_with_a_way_forward(self, tmp_path):
        config = load_config(repo_root=tmp_path, environ=dict(ENV))
        with pytest.raises(ConfigError) as caught:
            config.requires_token()
        assert "--dry-run" in str(caught.value)

    def test_find_repo_root_locates_this_repository(self):
        assert (find_repo_root() / "PROJECT_STATE.md").is_file()

    def test_find_repo_root_refuses_outside_a_repository(self, tmp_path):
        with pytest.raises(ConfigError):
            find_repo_root(tmp_path)


class TestArgumentParsing:
    def parse(self, *argv):
        return build_parser().parse_args(argv)

    def test_start_defaults_are_safe(self):
        """Unattended behaviour must be opted into, never inherited."""
        args = self.parse("start")
        assert args.continuous is False
        assert args.dry_run is False
        assert args.allow_auto_merge is False
        assert args.max_tasks == 0

    def test_once_and_continuous_are_mutually_exclusive(self):
        with pytest.raises(SystemExit):
            self.parse("start", "--once", "--continuous")

    def test_safety_limits_are_parsed(self):
        args = self.parse("start", "--continuous", "--max-tasks", "3", "--max-runtime", "45")
        assert args.continuous is True
        assert args.max_tasks == 3
        assert args.max_runtime == 45.0

    def test_dry_run_and_mock_adapter(self):
        args = self.parse("start", "--dry-run", "--adapter", "mock")
        assert args.dry_run is True
        assert args.adapter == "mock"

    def test_an_unknown_adapter_is_refused(self):
        with pytest.raises(SystemExit):
            self.parse("start", "--adapter", "gemini")

    def test_the_documented_subcommands_exist(self):
        for command in ("start", "status", "doctor"):
            assert self.parse(command).command == command

    def test_a_command_is_required(self):
        with pytest.raises(SystemExit):
            self.parse()
