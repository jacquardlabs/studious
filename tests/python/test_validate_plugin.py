import json
from pathlib import Path

from validate_plugin import validate, validate_hooks

REPO = Path(__file__).resolve().parents[2]

GOOD = {
    "name": "studious",
    "description": "d",
    "version": "2.0.0",
    "author": {"name": "Jacquard Labs"},
    "repository": "https://github.com/jacquardlabs/studious",
    "license": "MIT",
    "keywords": ["review"],
}

GOOD_HOOKS = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gate-reminder.sh"',
                    }
                ],
            }
        ]
    }
}


def hooks_repo(tmp_path: Path) -> Path:
    (tmp_path / "hooks").mkdir()
    (tmp_path / "hooks" / "gate-reminder.sh").write_text("#!/usr/bin/env bash\n")
    return tmp_path


def test_good_manifest_passes() -> None:
    assert validate(GOOD) == []


def test_missing_required_field() -> None:
    data = dict(GOOD)
    del data["license"]
    assert any("license" in e for e in validate(data))


def test_bad_semver() -> None:
    data = dict(GOOD)
    data["version"] = "2.0"
    assert any("semver" in e for e in validate(data))


def test_bad_name_pattern() -> None:
    data = dict(GOOD)
    data["name"] = "Studious_X"
    assert any("name" in e for e in validate(data))


def test_author_without_name() -> None:
    data = dict(GOOD)
    data["author"] = {}
    assert any("author.name" in e for e in validate(data))


def test_keywords_must_be_list() -> None:
    data = dict(GOOD)
    data["keywords"] = "review"
    assert any("keywords" in e for e in validate(data))


def test_good_hooks_pass(tmp_path: Path) -> None:
    assert validate_hooks(GOOD_HOOKS, hooks_repo(tmp_path)) == []


def test_hooks_top_level_must_be_object(tmp_path: Path) -> None:
    assert any("top level" in e for e in validate_hooks([], hooks_repo(tmp_path)))


def test_hooks_key_must_be_object(tmp_path: Path) -> None:
    assert any("'hooks'" in e for e in validate_hooks({"hooks": []}, hooks_repo(tmp_path)))


def test_hooks_event_must_be_array(tmp_path: Path) -> None:
    data = {"hooks": {"PreToolUse": {}}}
    assert any("PreToolUse" in e for e in validate_hooks(data, hooks_repo(tmp_path)))


def test_hooks_entry_needs_hooks_array(tmp_path: Path) -> None:
    data = {"hooks": {"PreToolUse": [{"matcher": "Bash"}]}}
    assert any("'hooks' array" in e for e in validate_hooks(data, hooks_repo(tmp_path)))


def test_hooks_command_must_be_a_string(tmp_path: Path) -> None:
    data = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command"}]}]}}
    assert any("no command string" in e for e in validate_hooks(data, hooks_repo(tmp_path)))


def test_hooks_command_must_reference_a_plugin_file(tmp_path: Path) -> None:
    data = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "bash x.sh"}]}]}}
    assert any("references no" in e for e in validate_hooks(data, hooks_repo(tmp_path)))


def test_hooks_referenced_file_must_exist(tmp_path: Path) -> None:
    data = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [{"command": 'bash "${CLAUDE_PLUGIN_ROOT}/hooks/gone.sh"'}],
                }
            ]
        }
    }
    errors = validate_hooks(data, hooks_repo(tmp_path))
    assert any("missing file: hooks/gone.sh" in e for e in errors)


def test_shipped_hooks_json_passes() -> None:
    data = json.loads((REPO / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    assert validate_hooks(data, REPO) == []
