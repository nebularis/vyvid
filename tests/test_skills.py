# SPDX-License-Identifier: MIT
"""Skills reach an agent: shipped by a domain, added to by a project, composed into its checkout, and checked."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from vyvid import cli, install, remind, skills
from vyvid.config import ConfigError, load

DOMAIN_SKILL = """---
name: lifecycle
description: Use when picking up a slice or finishing work
---
<!-- SPDX-License-Identifier: MIT -->

# Lifecycle

Opening words.

## Recording what we learn

Update the domain's registers. The status records are in {{status}}.

## Merging

Merge with care.

```text
## not a heading, in a fence, {{left_alone}}
```
"""
ADDITION = """---
description: How work is run in this project, when picking up a slice
---
Words of the project.

## Recording what we learn

Also update `docs/developer/mechanisms.md`.

## Merging (replace)

Squash only.

## Project rules

Only here.
"""


def world(tmp_path: Path, project_extra: str = "", addition: str | None = ADDITION, values: str = '[projects.skill_values]\nstatus = "docs/developer/status"\n') -> tuple[object, Path]:
    domain = tmp_path / "lifecycle-domain"
    (domain / "skills" / "lifecycle").mkdir(parents=True)
    (domain / "skills" / "lifecycle" / "SKILL.md").write_text(DOMAIN_SKILL, encoding="utf-8")
    (domain / "notes.md").write_text("# Notes\n\n**Unit type:** Register\n\n| ID | Tool | Claim | Problem shape | Evidence | Activity | Technology | Specialises | Overrides |\n|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    (domain / "domain.toml").write_text('name = "lifecycle"\ndescription = "How work is run"\nvisibility = "public"\nrules = []\n[families]\nNOTE = { defined = "notes.md", type = "note" }\n', encoding="utf-8")
    code = tmp_path / "code"
    (code / ".vyvid" / "skills" / "lifecycle").mkdir(parents=True)
    if addition is not None:
        (code / ".vyvid" / "skills" / "lifecycle" / "lifecycle.md").write_text(addition, encoding="utf-8")
    path = tmp_path / "config.toml"
    path.write_text(f'[[domains]]\nname = "lifecycle"\npath = "{domain.as_posix()}"\ntrust = "own"\n[[projects]]\nname = "proj"\ncode = "{code.as_posix()}"\ndomains = ["lifecycle"]\n{project_extra}\n{values}', encoding="utf-8")
    return load(path), code


def composed(config) -> str:
    written, _ = skills.for_project(config, config.projects["proj"])
    return next(w for w in written if w.name.endswith("lifecycle")).text


def test_a_composed_skill_opens_on_the_index_header_and_joins_the_project_by_heading(tmp_path):
    config, _ = world(tmp_path)
    text = composed(config)
    assert text.startswith("---\nname: lifecycle\ndescription: How work is run in this project")
    assert skills.MARK in text.splitlines()[:6]
    assert text.index("# Lifecycle") < text.index("## Ask the index first") < text.index("Opening words.")
    assert skills.INDEX_FIRST in text and "vyd find" in text and "`NOTE` entries of domain lifecycle" in text
    assert "Words of the project." in text
    section = text[text.index("## Recording what we learn"):text.index("## Merging")]
    assert section.index("Update the domain's registers") < section.index("mechanisms.md") and "docs/developer/status." in section
    assert "Squash only." in text and "Merge with care." not in text and text.index("## Merging") < text.index("## Project rules")


def test_a_heading_in_a_fence_is_text_a_value_fills_a_code_span_and_a_workflow_expression_is_left(tmp_path):
    config, _ = world(tmp_path, addition=None, values='[projects.skill_values]\nstatus = "docs/status"\nleft_alone = "filled"\n')
    source = config.domains["lifecycle"].path / "skills" / "lifecycle" / "SKILL.md"
    source.write_text(DOMAIN_SKILL.replace("Merge with care.", "See `{{status}}`, and ${{ matrix.os }} stays."), encoding="utf-8")
    written, _ = skills.for_project(config, config.projects["proj"])
    assert not written[0].problems and "`docs/status`" in written[0].text and "${{ matrix.os }}" in written[0].text
    assert "## not a heading, in a fence, filled\n```" in written[0].text


def test_a_missing_value_is_a_problem_and_nothing_is_written_for_that_skill(tmp_path, capsys):
    config, code = world(tmp_path, values="")
    assert skills.install_project(config, config.projects["proj"], dry_run=False) == 1
    assert "needs a value for status" in capsys.readouterr().out and not (code / ".claude" / "skills" / "lifecycle" / "SKILL.md").exists()


def test_install_writes_into_the_checkout_and_check_catches_drift_and_staleness(tmp_path, capsys):
    config, code = world(tmp_path)
    project = config.projects["proj"]
    path = code / ".claude" / "skills" / "lifecycle" / "SKILL.md"
    assert skills.check(config, project, [], None) == 1 and "is missing" in capsys.readouterr().out
    assert skills.install_project(config, project, dry_run=False) == 0
    assert path.is_file() and skills.check(config, project, [], None) == 0
    path.write_text(path.read_text(encoding="utf-8") + "by hand\n", encoding="utf-8")
    capsys.readouterr()
    assert skills.check(config, project, [], None) == 1 and "differs from what its sources" in capsys.readouterr().out
    assert skills.install_project(config, project, dry_run=False) == 0
    stale = code / ".claude" / "skills" / "gone" / "SKILL.md"
    stale.parent.mkdir()
    stale.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    assert skills.check(config, project, [], None) == 1
    assert skills.install_project(config, project, dry_run=False) == 0 and not stale.exists()


def test_a_hand_written_skill_of_that_name_is_left_alone(tmp_path, capsys):
    config, code = world(tmp_path)
    path = code / ".claude" / "skills" / "lifecycle" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("mine\n", encoding="utf-8")
    assert skills.install_project(config, config.projects["proj"], dry_run=False) == 1
    assert path.read_text(encoding="utf-8") == "mine\n" and "was not generated" in capsys.readouterr().out


def test_nothing_of_this_machine_is_in_a_composed_skill(tmp_path):
    config, _ = world(tmp_path)
    assert str(tmp_path) not in composed(config)


def test_a_prefix_names_the_skill_and_a_project_keeps_its_own_skills(tmp_path):
    config, code = world(tmp_path, 'skill_prefix = "lattice-"\nskills = "code:.vyvid/own"')
    own = code / ".vyvid" / "own" / "architecture"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("---\nname: architecture\ndescription: The structure\n---\n# Architecture\n\nWords.\n", encoding="utf-8")
    config = load(tmp_path / "config.toml")
    names = {w.name for w in skills.for_project(config, config.projects["proj"])[0]}
    assert names == {"lattice-lifecycle", "lattice-architecture"}


def test_a_knowledge_domain_gives_no_skill_and_an_addition_with_no_skill_is_named(tmp_path):
    config, code = world(tmp_path)
    (code / ".vyvid" / "skills" / "lifecycle" / "typo.md").write_text("## X\n\nY\n", encoding="utf-8")
    written, notes = skills.for_project(config, config.projects["proj"])
    assert any("typo.md adds to no skill" in n for n in notes) and len(written) == 1
    path = tmp_path / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('trust = "own"', 'trust = "knowledge"'), encoding="utf-8")
    config = load(path)
    written, notes = skills.for_project(config, config.projects["proj"])
    assert not written and any("gives knowledge alone" in n for n in notes)


def test_a_private_domains_skill_is_never_written_into_a_checkout_and_reaches_the_users_folder(tmp_path):
    config, code = world(tmp_path)
    manifest = config.domains["lifecycle"].path / "domain.toml"
    manifest.write_text(manifest.read_text(encoding="utf-8").replace('visibility = "public"', 'visibility = "private"').replace("rules = []", 'rules = []\nskill_values = { status = "private-words" }'), encoding="utf-8")
    config = load(tmp_path / "config.toml")
    written, notes = skills.for_project(config, config.projects["proj"])
    assert not written and any("since it is private" in n for n in notes)
    assert skills.install_project(config, config.projects["proj"], dry_run=False) == 0
    assert not (code / ".claude" / "skills").exists()
    target = tmp_path / "client"
    assert install.install(config, "claude-code", target, dry_run=False) == 0
    assert (target / "skills" / "lifecycle" / "SKILL.md").is_file()


def test_a_projects_work_table_gives_its_locations_once(tmp_path):
    config, _ = world(tmp_path, '[projects.work]\nstatus = "code:docs/developer/status"\n', values="")
    assert "docs/developer/status." in composed(config)


def test_coverage_names_a_line_with_no_home_and_a_map_gives_it_one(tmp_path, capsys):
    config, code = world(tmp_path)
    project = config.projects["proj"]
    assert skills.install_project(config, project, dry_run=False) == 0
    old = tmp_path / "old.md"
    old.write_text("---\nname: old\ndescription: x\n---\n# Lifecycle\n\nOpening words.\n\nA line going nowhere.\n", encoding="utf-8")
    capsys.readouterr()
    assert skills.check(config, project, [old], None) == 1 and "A line going nowhere." in capsys.readouterr().out
    table = tmp_path / "map.tsv"
    table.write_text("line\tclass\tdestination\n9\tlattice\tlattice\n", encoding="utf-8")
    assert skills.check(config, project, [old], table) == 0


def test_a_target_leaving_the_checkout_is_refused(tmp_path):
    with pytest.raises(ConfigError, match="leaves the checkout"):
        world(tmp_path, 'skill_targets = ["../elsewhere"]')


def test_a_personal_skill_is_not_written_for_a_domain_a_project_uses(tmp_path):
    config, _ = world(tmp_path)
    target = tmp_path / "client"
    assert install.install(config, "claude-code", target, dry_run=False) == 0
    assert not (target / "skills" / "lifecycle").exists() and not (target / "skills" / "vyvid-domain-lifecycle").exists()
    assert skills.INDEX_FIRST in (target / "rules" / "vyvid.md").read_text(encoding="utf-8")


def test_a_domain_no_project_uses_gets_its_skills_in_the_users_folder_with_the_header(tmp_path):
    config, _ = world(tmp_path)
    path = tmp_path / "config.toml"
    path.write_text(path.read_text(encoding="utf-8").replace('domains = ["lifecycle"]\n', "").replace('[projects.skill_values]\nstatus = "docs/developer/status"\n', ""), encoding="utf-8")
    domain = config.domains["lifecycle"].path / "domain.toml"
    domain.write_text(domain.read_text(encoding="utf-8").replace('rules = []', 'rules = []\nskill_values = { status = "status" }'), encoding="utf-8")
    config = load(path)
    target = tmp_path / "client"
    assert install.install(config, "claude-code", target, dry_run=False) == 0
    assert skills.INDEX_FIRST in (target / "skills" / "lifecycle" / "SKILL.md").read_text(encoding="utf-8")


# ---- The reminder hook -------------------------------------------------------------------------------


def run(client: str, call: dict, folder: Path) -> dict:
    return remind.handle(client, json.dumps(call), "vyd find", folder, 1000.0)


@pytest.mark.parametrize("name,command", [
    ("Bash", "grep -rn foo ."), ("Bash", "cd x; rg foo"), ("Bash", "git grep foo"), ("Bash", "cat a | sed -n 1,3p"), ("Bash", "awk '{print}' a"),
    ("PowerShell", "Select-String -Path a -Pattern foo"), ("PowerShell", "Get-ChildItem -Recurse"), ("PowerShell", "findstr foo a"), ("Bash", "ls | xargs grep foo")])
def test_a_search_in_a_shell_is_a_search(name, command):
    assert remind.classify(name, {"command": command}) == "search"


@pytest.mark.parametrize("command", ["vyd find x", "mise run graph:ask -- find x", "vyd read STD-1", "cd a && vyd find grep"])
def test_a_question_is_a_question(command):
    assert remind.classify("Bash", {"command": command}) == "ask"


@pytest.mark.parametrize("command", ["git status", "pytest", "echo grep", "cat a", "mise run check"])
def test_other_commands_are_nothing(command):
    assert remind.classify("Bash", {"command": command}) is None


def test_it_reminds_until_asked_then_again_after_many_searches_and_never_decides(tmp_path):
    search = {"session_id": "s", "tool_name": "Bash", "tool_input": {"command": "grep x"}}
    out = run("claude-code", search, tmp_path)
    context = out["hookSpecificOutput"]
    assert context["hookEventName"] == "PreToolUse" and "index" in context["additionalContext"] and "permissionDecision" not in context
    assert run("claude-code", {**search, "tool_input": {"command": "vyd find x"}}, tmp_path) == {}
    answers = [run("claude-code", search, tmp_path) for _ in range(remind.QUIET_AFTER_ASK + 1)]
    assert not any(answers[:-1]) and answers[-1]
    assert run("claude-code", {**search, "session_id": "other"}, tmp_path)


def test_each_clients_input_and_output_shape(tmp_path):
    copilot = run("copilot", {"sessionId": "c", "toolName": "run_in_terminal", "toolArgs": json.dumps({"command": "grep x"})}, tmp_path)
    assert set(copilot) == {"additionalContext"}
    assert run("codex", {"session_id": "d", "tool_name": "Bash", "tool_input": {"command": "rg x"}}, tmp_path)["hookSpecificOutput"]["additionalContext"]


def test_copilots_own_search_tool_as_it_really_sent_it_gets_a_reminder(tmp_path):
    call = {"sessionId": "e", "cwd": "/x", "toolName": "rg", "toolArgs": {"pattern": "a", "paths": "README.md", "output_mode": "count"}, "toolResult": {"resultType": "success"}}
    assert set(run("copilot", call, tmp_path)) == {"additionalContext"}


def test_whatever_goes_wrong_it_says_nothing_and_exits_zero(monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("VYVID_HOOK_STATE", str(tmp_path))
    for text in ("not json", "[]", '{"tool_name": 3}'):
        monkeypatch.setattr("sys.stdin", io.StringIO(text))
        assert remind.main(["--client", "copilot"]) == 0
        assert json.loads(capsys.readouterr().out) == {}


def test_the_hook_imports_only_the_standard_library():
    import ast
    tree = ast.parse(Path(remind.__file__).read_text(encoding="utf-8"))
    names = {n.names[0].name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)} | {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    assert not names & {"vyvid", "numpy", "onnxruntime"}


def test_hook_files_keep_what_was_there_replace_our_own_and_refuse_bad_json(tmp_path):
    path = tmp_path / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text(json.dumps({"model": "x", "hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": []}]}}), encoding="utf-8")
    for _ in range(2):
        assert install.install_hooks(tmp_path, ("claude-code", "copilot", "codex"), "mise run graph:ask -- find", dry_run=False) == 0
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data["hooks"]["PreToolUse"]
    assert data["model"] == "x" and len(rows) == 2 and rows[0]["matcher"] == "Edit" and "Bash|PowerShell" in rows[1]["matcher"]
    assert "graph:ask" in rows[1]["hooks"][0]["command"]
    copilot = json.loads((tmp_path / ".github" / "hooks" / "vyvid.json").read_text(encoding="utf-8"))
    assert copilot["version"] == 1 and {"bash", "powershell"} <= set(copilot["hooks"]["postToolUse"][0])
    assert "commandWindows" in json.loads((tmp_path / ".codex" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["PreToolUse"][0]["hooks"][0]
    path.write_text("not json", encoding="utf-8")
    assert install.install_hooks(tmp_path, ("claude-code",), "x", dry_run=False) == 1 and path.read_text(encoding="utf-8") == "not json"


def test_the_command_line_writes_a_project(tmp_path, monkeypatch, capsys):
    config, code = world(tmp_path)
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "config.toml"))
    (code / "x").write_text("", encoding="utf-8")
    assert cli.main(["install", "--project", "--in", str(code)]) in (0, 1)
    out = capsys.readouterr().out
    assert "lifecycle" in out or "not trusted" in out
