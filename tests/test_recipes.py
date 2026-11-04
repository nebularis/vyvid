# SPDX-License-Identifier: MIT
"""VYD-6: recipes, the briefing and its budget, the generated skills and rule file, and the recipes
that vyd context lists."""

from __future__ import annotations

import sys
from pathlib import Path

import pyoxigraph as ox
import pytest

from test_index_core import Words
from vyvid import ask, cli, embed, install, recipes
from vyvid import build as builder
from vyvid.config import ConfigError, Recipe, load
from vyvid.model import RDF_TYPE, RDFS_LABEL, index_graph, ki, node
from vyvid.resolve import layers

CONFIG = """
[framework]
store = "STORE"

[[domains]]
name = "wide"
path = "WIDE"
description = "Notes on wide things"
families = { NOTE = { defined = "self:notes.md", type = "note" } }

[[domains.recipes]]
name = "same"
description = "The wide version"
steps = [{ step = "include", ids = ["NOTE-1"] }]

[[domains.recipes]]
name = "notes"
description = "When a note decides it"
steps = [{ step = "include", ids = ["NOTE-1"] }]

[[domains]]
name = "tools"
path = "TOOLS"
parents = ["wide"]

[[projects]]
name = "proj"
code = "CODE"
domains = ["tools"]

[projects.families]
STD = {}
ADR = {}
CAP = {}

RECIPES
"""

# Three standards of falling closeness to "ledger", two decisions and a capability.
ENTRIES = [("proj", "STD-1", "Standard", "ledger"), ("proj", "STD-2", "Standard", "ledger ledger"), ("proj", "STD-3", "Standard", "graph"),
           ("proj", "ADR-1", "Decision", "slow"), ("proj", "ADR-2", "Decision", "slow slow"), ("proj", "CAP-1", "Capability", "graph graph"),
           ("wide", "NOTE-1", "Note", "minting")]
EDGES = [("STD-1", "decidedBy", "ADR-1"), ("STD-2", "decidedBy", "ADR-1"), ("STD-3", "decidedBy", "ADR-2")]


def recipe_text(name, steps, extra=""):
    return f'[[projects.recipes]]\nname = "{name}"\ndescription = "Use {name}"\n{extra}steps = [\n{steps}\n]\n'


class World:
    """A configuration of two domains and a project, and a store holding ENTRIES and EDGES."""

    def __init__(self, tmp_path, recipes_toml="", manifest=""):
        self.tmp, self.code = tmp_path, tmp_path / "code"
        self.code.mkdir()
        (tmp_path / "wide").mkdir()
        (tmp_path / "wide" / "rules.md").write_text("# Wide rules\n\nKeep it wide.\n", encoding="utf-8")
        (tmp_path / "tools").mkdir()
        if manifest:
            (tmp_path / "tools" / "domain.toml").write_text(manifest, encoding="utf-8")
        text = CONFIG.replace("RECIPES", recipes_toml).replace("STORE", (tmp_path / "idx").as_posix())
        for name in ("WIDE", "TOOLS", "CODE"):
            text = text.replace(f'"{name}"', f'"{(tmp_path / name.lower()).as_posix()}"')
        self.path = tmp_path / "config.toml"
        self.path.write_text(text, encoding="utf-8")
        self.config = load(self.path)
        self.project = self.config.projects["proj"]
        self.stack = layers(self.config, self.project)
        self.store = ox.Store()
        self.ask = ask.Asker(self.config, self.project, self.stack, tmp_path / "idx", self.store, Words())
        for scope, ident, kind, claim in ENTRIES:
            n = node(scope, ident)
            self.store.extend([ox.Quad(s, p, o, index_graph(scope)) for s, p, o in (
                (n, ki("identifier"), ox.Literal(ident)), (n, ki("claim"), ox.Literal(claim)),
                (n, RDF_TYPE, ki(kind)), (n, RDFS_LABEL, ox.Literal(ident.lower())))])
        for ident, prop, other in EDGES:
            self.store.add(ox.Quad(node("proj", ident), ki(prop), node("proj", other), index_graph("proj")))
        entries = {str(r["n"].value): embed.join_text([r["label"] and r["label"].value, r["claim"].value, None, None])
                   for r in self.store.query(builder.TEXTS)}
        embed.build(entries, self.ask.directory, self.config.embedding, self.ask.model)

    def run(self, name, question="ledger"):
        recipe = recipes.available(self.stack)[name]
        return [e["id"] for e in recipes.run(self.ask, recipe, question)]


def find(**keys):
    """A find step of the project's recipe, as TOML."""
    return "  { step = \"find\", words = \"{question}\", " + ", ".join(f"{k} = {v!r}".replace("'", '"') for k, v in keys.items()) + " },"


def test_find_joins_the_rows_of_the_question_with_its_filters(tmp_path):
    w = World(tmp_path, recipe_text("r", find(kind="standard", limit=2)))
    assert w.run("r") == ["STD-1", "STD-2"], "the template put the question in, the kind filter left the rest out, the limit cut"


def test_the_words_of_find_are_a_template_around_the_question(tmp_path):
    w = World(tmp_path, recipe_text("r", '  { step = "find", words = "graph {question}", kind = ["capability"], limit = 1 },'))
    assert w.run("r", "graph") == ["CAP-1"]


def test_linked_follows_declared_edges_in_the_direction_named(tmp_path):
    standards = find(kind="standard", limit=2)
    w = World(tmp_path, recipe_text("out", standards + '\n  { step = "linked", edges = ["decidedBy"], direction = "out" },')
              + recipe_text("in", '  { step = "include", ids = ["ADR-1"] },\n  { step = "linked", edges = ["decidedBy"], direction = "in" },')
              + recipe_text("none", standards + '\n  { step = "linked", edges = ["supports"] },'))
    assert w.run("out") == ["STD-1", "STD-2", "ADR-1"], "ADR-1 is reached from both standards and joins once"
    reached = w.run("in")
    assert reached[0] == "ADR-1" and sorted(reached[1:]) == ["STD-1", "STD-2"], "an edge followed against its direction"
    assert w.run("none") == ["STD-1", "STD-2"], "an edge nothing declares reaches nothing"


def test_include_resolves_identifiers_in_the_scope_that_declares_the_recipe(tmp_path):
    w = World(tmp_path, recipe_text("r", '  { step = "include", ids = ["CAP-1", "wide:NOTE-1"] },')
              + recipe_text("missing", '  { step = "include", ids = ["CAP-9"] },'))
    assert w.run("r") == ["CAP-1", "wide:NOTE-1"], "an entry of another scope is shown as scope:LOCAL"
    assert w.run("notes") == ["wide:NOTE-1"], "NOTE-1 means the domain's own in the domain's recipe"
    with pytest.raises(recipes.RecipeError, match="CAP-9"):
        w.run("missing")


def test_take_keeps_the_first_rows_or_the_first_of_each_kind(tmp_path):
    steps = find(kind="standard,decision,capability", limit=9) + '\n  { step = "linked", edges = ["decidedBy"] },\n  { step = "include", ids = ["CAP-1"] },'
    w = World(tmp_path, recipe_text("first", steps + '\n  { step = "take", n = 2 },')
              + recipe_text("kinds", steps + '\n  { step = "take", n = 1, per_kind = true },'))
    assert w.run("first") == ["STD-1", "STD-2"]
    assert w.run("kinds", "ledger") == ["STD-1", "ADR-1", "CAP-1"]


def test_the_result_holds_an_entry_once(tmp_path):
    w = World(tmp_path, recipe_text("r", find(kind="standard", limit=1) + '\n  { step = "include", ids = ["STD-1", "CAP-1"] },'))
    assert w.run("r") == ["STD-1", "CAP-1"]


def test_an_entry_carries_what_find_prints_under_it(tmp_path):
    w = World(tmp_path, recipe_text("r", '  { step = "include", ids = ["STD-1"] },'))
    w.store.add(ox.Quad(node("proj", "STD-1"), ki("doesNotCover"), ox.Literal("a write to two graphs"), index_graph("proj")))
    entry = recipes.run(w.ask, recipes.available(w.stack)["r"], "q")[0]
    assert entry["kind"] == "Standard" and entry["scope"] == "proj" and entry["claim"] == "ledger"
    assert entry["signposts"] == ["Does not cover: a write to two graphs."]


def glue(tmp_path, body, name="glue"):
    script = tmp_path / f"{name}.py"
    script.write_text(body, encoding="utf-8")
    return f'  {{ step = "glue", command = ["{Path(sys.executable).as_posix()}", "{script.as_posix()}"] }},'


def test_a_projects_glue_step_gets_the_result_on_stdin_in_the_code_folder(tmp_path):
    step = glue(tmp_path, "import json, os, sys\nxs = json.load(sys.stdin)\n"
                          "xs.append({'id': 'GLUE-1', 'kind': 'Note', 'claim': f'saw {len(xs)} in {os.getcwd()}'})\n"
                          "json.dump(xs[::-1], sys.stdout)\n")
    w = World(tmp_path, recipe_text("r", find(kind="standard", limit=2) + "\n" + step))
    entries = recipes.run(w.ask, recipes.available(w.stack)["r"], "ledger")
    assert [e["id"] for e in entries] == ["GLUE-1", "STD-2", "STD-1"], "the output replaced the result"
    saw, cwd = entries[0]["claim"].removeprefix("saw ").split(" in ", 1)
    assert saw == "2" and Path(cwd).resolve() == w.code.resolve()
    assert entries[0]["signposts"] == [] and entries[0]["pointer"] == "", "a missing field is filled in"


def test_a_failing_glue_step_is_a_recipe_error(tmp_path):
    w = World(tmp_path, recipe_text("fails", glue(tmp_path, "import sys\nsys.exit('no')\n"))
              + recipe_text("text", glue(tmp_path, "print('not json')\n", "text")))
    with pytest.raises(recipes.RecipeError, match="exited 1"):
        w.run("fails")
    with pytest.raises(recipes.RecipeError, match="did not print JSON"):
        w.run("text")


def test_a_domains_glue_step_is_refused_at_load(tmp_path):
    manifest = '[[recipes]]\nname = "r"\ndescription = "d"\nsteps = [{ step = "glue", command = ["sh", "-c", "true"] }]\n'
    with pytest.raises(ConfigError, match="a cloned domain runs no code"):
        World(tmp_path, manifest=manifest)


def test_a_recipe_that_cannot_be_used_is_refused_with_every_problem(tmp_path):
    steps = '  { step = "find" },\n  { step = "linked", edges = ["likes"], direction = "up" },\n  { step = "take", n = 0 },\n  { step = "dance" },'
    with pytest.raises(ConfigError) as error:
        World(tmp_path, recipe_text("bad", steps, "budget = 0\n") + recipe_text("Bad", steps))
    problems = "\n".join(error.value.problems)
    for expected in ("a recipe needs a unique lower-case name, not 'Bad'", "needs 'words'", "'edges' must be a list of", "'direction' must be one of",
                     "'n' must be a whole number", "a step needs a 'step' of", "budget must be a whole number"):
        assert expected in problems


def test_a_narrower_scopes_recipe_replaces_a_wider_ones_of_the_same_name(tmp_path):
    w = World(tmp_path, recipe_text("same", '  { step = "include", ids = ["CAP-1"] },'))
    assert recipes.available(w.stack)["same"].scope == "proj" and w.run("same") == ["CAP-1"]
    assert [r.scope for r in recipes.available(w.stack).values()] == ["proj", "wide"], "the other recipe of the domain stays"
    assert recipes.available([w.stack[0], w.stack[1]])["same"].scope == "wide", "outside the project the domain's stands"


def test_a_domains_manifest_declares_recipes_too(tmp_path):
    manifest = '[[recipes]]\nname = "own"\ndescription = "From the manifest"\nbudget = 300\nsteps = [{ step = "include", ids = ["NOTE-1"] }]\n'
    w = World(tmp_path, manifest=manifest)
    assert recipes.available(w.stack)["own"] == Recipe("own", "From the manifest", ({"step": "include", "ids": ["NOTE-1"]},), 300, "tools")


# ---- The briefing and its budget -----------------------------------------------------------------


def entries_of(n):
    return [{"node": "", "id": f"STD-{i}", "kind": "Standard", "scope": "proj", "claim": f"Claim {i} " + "word " * 20,
             "pointer": f"docs/standards.md:{i}-{i + 3}", "signposts": ["Open debt: TD-1."] if i == 1 else []} for i in range(1, 7)][:n]


def test_the_briefing_is_one_block_per_entry_and_drops_the_last_over_the_budget():
    recipe = Recipe("r", "d", (), 100)
    text, size, dropped = recipes.briefing(recipe, "a question", entries_of(6))
    lines = text.splitlines()
    assert lines[0] == 'Recipe r, for "a question"'
    assert lines[1] == "STD-1  Standard  docs/standards.md:1-4" and lines[2].startswith("  Claim 1 ") and lines[2].endswith("Open debt: TD-1.")
    assert dropped > 0 and size <= 100 and size == -(-len(text) // 4), "the estimate is the characters over four"
    assert lines[-1] == f"{dropped} more entries not shown, to stay within 100 tokens. Run with --all to see every one."
    assert f"STD-{6 - dropped}  " in text and f"STD-{7 - dropped}  " not in text, "the last entries went"


def test_all_keeps_every_entry_whatever_the_budget():
    text, size, dropped = recipes.briefing(Recipe("r", "d", (), 100), "q", entries_of(6), everything=True)
    assert dropped == 0 and "STD-6  " in text and "--all" not in text and size > 100


def test_the_first_entry_is_kept_however_small_the_budget():
    text, _, dropped = recipes.briefing(Recipe("r", "d", (), 1), "q", entries_of(3))
    assert "STD-1  " in text and "STD-2  " not in text and dropped == 2


# ---- The command line ----------------------------------------------------------------------------


def test_recipe_list_and_context_name_the_recipes_of_the_stack(tmp_path, monkeypatch, capsys):
    w = World(tmp_path, recipe_text("r", '  { step = "include", ids = ["CAP-1"] },'))
    monkeypatch.setenv("VYVID_CONFIG", str(w.path))
    assert cli.main(["recipe", "list", "--in", str(w.code)]) == 0
    listed = capsys.readouterr().out
    assert "r  " in listed and "proj" in listed and "Use r" in listed and "notes" in listed and "When a note decides it" in listed
    assert cli.main(["context", str(w.code), "--no-pull"]) == 0
    context = capsys.readouterr().out
    assert context.index("domain wide") < context.index("recipe notes  When a note decides it") < context.index("project proj")
    assert "   recipe r  Use r" in context
    assert cli.main(["recipe", "run", "absent", "q", "--in", str(w.code)]) == 1
    assert "no recipe 'absent'" in capsys.readouterr().err


# ---- vyd install ---------------------------------------------------------------------------------


def test_install_writes_the_rule_file_and_a_skill_per_domain(tmp_path):
    w = World(tmp_path)
    target = tmp_path / "client"
    assert install.install(w.config, "claude-code", target, dry_run=False) == 0
    rule = (target / "rules" / "vyvid.md").read_text(encoding="utf-8")
    assert rule.splitlines()[0] == install.MARK
    assert "run `vyd context`" in rule and "`vyd find`" in rule and "vyd recipe run" in rule and "vyd misses --near" in rule
    wide = (target / "skills" / "vyvid-wide" / "SKILL.md").read_text(encoding="utf-8")
    assert wide.startswith("---\nname: vyvid-wide\ndescription: \"Notes on wide things\"\n---\n" + install.MARK)
    assert wide.index("Keep it wide.") < wide.index("## Recipes") < wide.index("## Registers")
    assert 'vyd recipe run notes "<question>"`. When a note decides it' in wide and "- NOTE (note) in " in wide
    tools = (target / "skills" / "vyvid-tools" / "SKILL.md").read_text(encoding="utf-8")
    assert 'description: "Use when working on tools"' in tools and "## Recipes" not in tools
    assert install.install(w.config, "claude-code", target, dry_run=False) == 0, "a file it generated is written again"


def test_install_never_overwrites_a_file_it_did_not_generate(tmp_path, capsys):
    w = World(tmp_path)
    target = tmp_path / "client"
    (target / "rules").mkdir(parents=True)
    (target / "rules" / "vyvid.md").write_text("my own rule\n", encoding="utf-8")
    assert install.install(w.config, "claude-code", target, dry_run=False) == 1
    assert (target / "rules" / "vyvid.md").read_text(encoding="utf-8") == "my own rule\n"
    assert "left " in capsys.readouterr().out and (target / "skills" / "vyvid-wide" / "SKILL.md").exists(), "the rest is still written"


def test_install_dry_run_writes_nothing(tmp_path, capsys):
    w = World(tmp_path)
    target = tmp_path / "client"
    assert install.install(w.config, "claude-code", target, dry_run=True) == 0
    out = capsys.readouterr().out
    assert not target.exists() and f"would write {target / 'rules' / 'vyvid.md'}" in out and "vyvid-wide" in out and "vyvid-tools" in out


def test_install_writes_nothing_into_a_projects_folder(tmp_path, capsys):
    w = World(tmp_path)
    assert install.install(w.config, "claude-code", w.code / ".claude", dry_run=False) == 2
    assert not (w.code / ".claude").exists() and "project proj" in capsys.readouterr().out


def test_an_unknown_client_is_an_argument_error_naming_the_supported_ones(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("VYVID_CONFIG", str(tmp_path / "none.toml"))
    with pytest.raises(SystemExit) as exit:
        cli.main(["install", "--client", "cursor", "--target", str(tmp_path)])
    assert exit.value.code == 2 and "claude-code" in capsys.readouterr().err
