# SPDX-License-Identifier: MIT
"""A project's extractor run as a command in its own checkout, over real scripts under a temporary
folder, a stand-in model, real git worktrees and no network."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pyoxigraph as ox
import pytest

from test_checkouts import git, quiet_git  # noqa: F401  quiet_git is an autouse fixture
from test_index_core import Words
from vyvid import ask
from vyvid import build as builder
from vyvid.config import ConfigError, load, run_limited
from vyvid.model import KI

PRELUDE = '''
import json, os, sys, time
req = json.load(sys.stdin)
KI, out, scope, graphs = "https://www.nebularis.org/vyvid/knowledge#", req["output"], req["scope"], req["graphs"]
if req["settings"].get("seen"):
    open(req["settings"]["seen"], "a").write(out + "\\n")
def triple(s, p, o, g):
    return f"<{s}> <{p}> {o} <{g}> .\\n"
def entry(n, claim, g=None):
    s, g = f"{KI}node/{scope}/{n}", g or graphs["index"]
    return (triple(s, KI + "identifier", json.dumps(n), g) + triple(s, KI + "claim", json.dumps(claim), g)
            + triple(s, "http://www.w3.org/1999/02/22-rdf-syntax-ns#type", f"<{KI}Standard>", g))
def term(n, claim):
    s, g = f"{KI}term/{scope}/{n}", graphs["terms"]
    return (triple(s, KI + "identifier", json.dumps(n), g) + triple(s, KI + "claim", json.dumps(claim), g)
            + triple(s, KI + "pointer", json.dumps("x.txt:1"), g))
def finish(quads="", **result):
    if quads:
        open(out + "/quads.nq", "w").write(quads)
    json.dump({"protocol": 1, **result}, open(out + "/result.json", "w"))
'''

GOOD = "finish(entry('GOOD-1', 'A ledger is kept.'))\n"
CONFIG = '[framework]\nstore = "{store}"\n\n[[projects]]\nname = "proj"\ncode = "{code}"\ndocs = "code:docs"\n'


def script(folder: Path, body: str, name: str = "ex.py") -> Path:
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PRELUDE + body, encoding="utf-8")
    return path


def block(kind: str, path: str, extra: str = "", paths: str = '["code:docs/*.md"]') -> str:
    command = f'[{json.dumps(sys.executable)}, {json.dumps(path)}]'
    return f'\n[[projects.extractors]]\nkind = "{kind}"\ncommand = {command}\npaths = {paths}\n{extra}\n'


def config_for(tmp_path: Path, *blocks: str, code: Path | None = None, extra: str = "") -> Path:
    code = code or tmp_path / "code"
    code.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "config.toml"
    path.write_text(CONFIG.format(store=(tmp_path / "idx").as_posix(), code=code.as_posix()) + extra + "".join(blocks), encoding="utf-8")
    return path


def built(tmp_path, *blocks, monkeypatch=None, **kwargs):
    """The build of the project over its blocks, and the store it made."""
    config = load(config_for(tmp_path, *blocks, **kwargs))
    project = config.projects["proj"]
    out = builder.build(config, project, model=Words())
    return out, ox.Store.read_only(str(builder.store_dir(config, project) / "store"))


def claims(store) -> dict[str, str]:
    return {r["id"].value: r["claim"].value for r in store.query(f"SELECT ?id ?claim WHERE {{ GRAPH ?g {{ ?n <{KI}identifier> ?id ; <{KI}claim> ?claim }} }}")}


def problems(out, kind: str) -> list[str]:
    return [p for p in out.problems if f"extractor '{kind}'" in p]


def test_a_command_extractors_terms_and_rows_are_indexed_and_found(tmp_path):
    body = ("finish(entry('CMD-1', 'A ledger is kept per key.') + term('Account', 'An account holds a ledger.'), version='1.2.3',\n"
            "       texts={f'{KI}term/{scope}/Account': 'An account holds a ledger.'}, counts={'made': 2}, prefixes={'ex': 'https://example.org/'})\n")
    ex = script(tmp_path / "code", body)
    out, store = built(tmp_path, block("cmd", ex.as_posix()))
    assert claims(store) == {"CMD-1": "A ledger is kept per key.", "Account": "An account holds a ledger."}
    assert out.counts["made"] == 2 and out.counts["embedded"] == 2, "the entry by its claim and the term by its given text"
    assert "extractor 'cmd' ran version 1.2.3" in out.findings and not problems(out, "cmd")
    a = ask.open_stack(load(tmp_path / "config.toml"), tmp_path / "code", model=Words())
    assert [r["id"] for r in ask.candidates(a, set(), set(), set())] == ["CMD-1"]
    assert [r["id"] for r in ask.candidates(a, {"Term"}, set(), set())] == ["Account"]


def test_a_text_for_a_node_the_extractor_wrote_nothing_about_is_reported(tmp_path):
    ex = script(tmp_path / "code", "finish(entry('CMD-1', 'x'), texts={f'{KI}node/{scope}/CMD-1': 'kept', f'{KI}node/{scope}/NOPE': 'lost'})\n")
    out, store = built(tmp_path, block("cmd", ex.as_posix()))
    assert any("NOPE" in p for p in problems(out, "cmd")) and out.counts["embedded"] == 1 and "CMD-1" in claims(store)


@pytest.mark.parametrize("body,extra,said", [
    ("sys.stderr.write('boom' * 1000)\nsys.exit(3)\n", "", "exited 3"),
    ("time.sleep(20)\n", "seconds = 0.5", "did not finish within 0.5 seconds"),
    ("open(out + '/result.json', 'w').write('not json')\n", "", "result.json"),
    ("pass\n", "", "no readable result.json"),
    ("json.dump({'protocol': 2}, open(out + '/result.json', 'w'))\n", "", "not protocol 1"),
    ("json.dump({'protocol': True}, open(out + '/result.json', 'w'))\n", "", "not protocol 1"),
    ("json.dump({'protocol': 1, 'counts': {'a': 'b'}}, open(out + '/result.json', 'w'))\n", "", "counts are malformed"),
    ("finish('this is not a quad\\n')\n", "", "quads.nq that does not parse"),
    ("finish(entry('X-1', 'x', 'https://example.org/other') + entry('X-2', 'x'))\n", "", "outside its own graphs"),
    ("finish(entry('X-2', 'x') + '<https://example.org/s> <https://example.org/p> \"o\" .\\n')\n", "", "outside its own graphs"),
])
def test_a_failed_extractor_is_a_problem_costs_only_its_entries_and_leaves_no_output_folder(tmp_path, body, extra, said):
    good = script(tmp_path / "code", GOOD, "good.py")
    seen = tmp_path / "seen.txt"
    bad = script(tmp_path / "code", body, "bad.py")
    out, store = built(tmp_path, block("good", good.as_posix()), block("bad", bad.as_posix(), f'{extra}\nseen = "{seen.as_posix()}"'))
    assert [said in p for p in problems(out, "bad")] == [True], problems(out, "bad")
    assert max(len(p) for p in problems(out, "bad")) < 2300, "a command's stderr is capped"
    assert set(claims(store)) == {"GOOD-1"}, "the other extractor's entries survive and none of the failed one's"
    assert not any(store_quads(store, g) for g in (ox.DefaultGraph(), ox.NamedNode("https://example.org/other")))
    assert seen.exists() and not any(Path(line).exists() for line in seen.read_text().split()), "the output folder is gone after failure too"
    assert not list((tmp_path / "idx").glob("extract-*"))


def store_quads(store, graph) -> list:
    return list(store.quads_for_pattern(None, None, None, graph))


def test_a_command_that_cannot_start_is_a_problem(tmp_path):
    good = script(tmp_path / "code", GOOD, "good.py")
    nothing = '\n[[projects.extractors]]\nkind = "gone"\ncommand = ["/no/such/program"]\npaths = ["code:docs/*.md"]\n'
    out, store = built(tmp_path, block("good", good.as_posix()), nothing)
    assert problems(out, "gone") and "cannot run" in problems(out, "gone")[0] and set(claims(store)) == {"GOOD-1"}


def test_the_output_folder_is_gone_after_success(tmp_path):
    seen = tmp_path / "seen.txt"
    ex = script(tmp_path / "code", GOOD)
    built(tmp_path, block("cmd", ex.as_posix(), f'seen = "{seen.as_posix()}"'))
    paths = seen.read_text().split()
    assert len(paths) == 1 and not Path(paths[0]).exists() and Path(paths[0]).parent == tmp_path / "idx"


def test_a_token_in_the_environment_does_not_reach_it_and_a_named_variable_does(tmp_path, monkeypatch):
    for name in ("GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "MY_VAR", "OTHER_VAR"):
        monkeypatch.setenv(name, "secret")
    ex = script(tmp_path / "code", "finish(entry('ENV-1', json.dumps(sorted(os.environ))))\n")
    _, store = built(tmp_path, block("cmd", ex.as_posix(), 'env = ["MY_VAR", "NOT_SET"]'))
    seen = set(json.loads(claims(store)["ENV-1"]))
    assert {"PATH", "MY_VAR"} <= seen
    assert seen.isdisjoint({"GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY", "OTHER_VAR", "NOT_SET"})


def test_a_command_kind_overrides_an_installed_one_for_this_project_alone(tmp_path):
    code, other = tmp_path / "code", tmp_path / "other"
    (other / "onto").mkdir(parents=True)
    (other / "onto" / "o.ttl").write_text('@prefix owl: <http://www.w3.org/2002/07/owl#> .\n@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .\n'
                                          '<https://example.org/o#Thing> a owl:Class ; rdfs:label "Thing" .\n', encoding="utf-8")
    ex = script(code, GOOD)
    path = config_for(tmp_path, block("owl-terms", ex.as_posix()), '\n[[projects]]\nname = "second"\ncode = "%s"\n[[projects.extractors]]\n'
                      'kind = "owl-terms"\npaths = ["code:onto/*.ttl"]\n' % other.as_posix())
    config = load(path)
    out = builder.build(config, config.projects["proj"], embed=False)
    store = ox.Store.read_only(str(builder.store_dir(config) / "store"))
    assert set(claims(store)) == {"GOOD-1"} and not out.counts.get("term")
    out = builder.build(config, config.projects["second"], embed=False)
    store = ox.Store.read_only(str(builder.store_dir(config) / "store"))
    assert out.counts["term"] == 1 and "GOOD-1" not in claims(store), "the installed kind still runs in process for the other project"


@pytest.mark.parametrize("where", ["manifest", "entry"])
def test_a_domain_may_not_declare_a_command(tmp_path, where):
    domain = tmp_path / "dom"
    domain.mkdir()
    declared = f'extractors = [{{ kind = "cmd", command = ["x"], paths = ["self:a"] }}]\n'
    (domain / "domain.toml").write_text(declared if where == "manifest" else "", encoding="utf-8")
    path = config_for(tmp_path, extra='domains = ["dom"]\n')
    path.write_text(f'[[domains]]\nname = "dom"\npath = "{domain.as_posix()}"\n' + (declared if where == "entry" else "") + path.read_text(encoding="utf-8"), encoding="utf-8")
    if where == "manifest":
        problems = [p for why in load(path).set_aside.values() for p in why]
    else:
        with pytest.raises(ConfigError) as error:
            load(path)
        problems = error.value.problems
    assert any("only a project's own entry" in p for p in problems), problems


def test_a_project_may_not_turn_a_domains_extractor_into_a_command(tmp_path):
    domain = tmp_path / "dom"
    domain.mkdir()
    (domain / "domain.toml").write_text('extractors = [{ kind = "owl-terms" }]\n', encoding="utf-8")
    path = config_for(tmp_path, '\n[projects.uses.dom.owl-terms]\npaths = ["code:x"]\ncommand = ["x"]\n', extra='domains = ["dom"]\n')
    path.write_text(f'[[domains]]\nname = "dom"\npath = "{domain.as_posix()}"\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(ConfigError, match="may not run as"):
        load(path)


@pytest.mark.parametrize("extra", ['command = []', 'seconds = 0', 'env = "X"', 'code = [1]'])
def test_a_bad_command_setting_or_one_without_a_command_is_refused(tmp_path, extra):
    block_ = block("cmd", "x.py")
    block_ = block_.replace(f"command = [{json.dumps(sys.executable)}, \"x.py\"]", extra if extra.startswith("command") else f"command = [\"x\"]\n{extra}")
    with pytest.raises(ConfigError):
        load(config_for(tmp_path, block_))
    with pytest.raises(ConfigError, match="without a command"):
        load(config_for(tmp_path, '\n[[projects.extractors]]\nkind = "owl-terms"\npaths = ["code:x"]\nseconds = 5\n'))


# ---- Each checkout runs its own ----------------------------------------------------------------------

WHICH = "finish(entry('{which}', os.getcwd()))\n"


class Checkouts:
    """A main checkout whose extractor writes MAIN and a worktree whose copy of it writes FEAT."""

    def __init__(self, tmp_path):
        self.tmp, self.code = tmp_path, tmp_path / "main"
        (self.code / "docs").mkdir(parents=True)
        git(self.code, "init", "-b", "main")
        git(self.code, "remote", "add", "origin", "git@github.com:acme/proj.git")
        script(self.code, WHICH.format(which="MAIN"), "tools/ex.py")
        self.commit(self.code)
        self.wt = tmp_path / "wt" / "x"
        git(self.code, "worktree", "add", "-b", "feat", str(self.wt))
        script(self.wt, WHICH.format(which="FEAT"), "tools/ex.py")
        self.commit(self.wt)
        blocks = block("cmd", "tools/ex.py", 'code = ["code:tools/ex.py"]', '["code:docs/*.md"]')
        self.config = load(config_for(tmp_path, blocks, code=self.code, extra='[projects.match]\nremote = "github.com/acme/proj"\n'))

    def commit(self, folder):
        git(folder, "add", "-A", "tools")
        git(folder, "commit", "-m", "x")

    def asker(self, folder):
        return ask.open_stack(self.config, folder, model=Words())

    def rows(self, folder):
        return {r["id"]: r["claim"] for r in ask.candidates(self.asker(folder), set(), set(), set())}


def test_two_worktrees_whose_extractor_differs_each_index_with_their_own_and_run_in_their_own_root(tmp_path):
    c = Checkouts(tmp_path)
    assert c.rows(c.code) == {"MAIN": str(c.code.resolve())}
    assert c.rows(c.wt) == {"FEAT": str(c.wt.resolve())}, "its own version, run in the rebased checkout's root"


def test_editing_the_extractor_in_one_checkout_makes_only_that_checkouts_index_stale(tmp_path):
    c = Checkouts(tmp_path)
    main, wt = c.asker(c.code), c.asker(c.wt)
    assert not ask.stale(main) and not ask.stale(wt)
    later = time.time() + 100
    os.utime(c.code / "tools" / "ex.py", (later, later))
    assert ask.stale(main) and not ask.stale(wt)
    os.utime(c.code / "tools" / "ex.py", (1, 1))
    (c.code / "tools" / "other.py").write_text("x", encoding="utf-8")
    os.utime(c.code / "tools" / "other.py", (later, later))
    assert not ask.stale(main), "a file that is neither read nor the extractor's own changes nothing"
    (c.wt / "docs").mkdir()
    (c.wt / "docs" / "new.md").write_text("x", encoding="utf-8")
    os.utime(c.wt / "docs" / "new.md", (later, later))
    assert ask.stale(wt), "a file the paths glob names now counts"


def test_a_time_limit_also_stops_what_the_command_started(tmp_path):
    """A wrapper such as ``mise exec`` starts the real program, which must not outlive the limit."""
    marker = tmp_path / "survived"
    inner = f"import time, pathlib; time.sleep(1.5); pathlib.Path({str(marker)!r}).write_text('x')"
    outer = f"import subprocess, sys, time; subprocess.Popen([sys.executable, '-c', {inner!r}]); time.sleep(30)"
    started = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        run_limited([sys.executable, "-c", outer], "", tmp_path, dict(os.environ), 0.5)
    assert time.monotonic() - started < 5, "stopped at the limit, with no wait for the pipes"
    time.sleep(1.8)
    assert not marker.exists(), "the program the command started was stopped too"


def test_a_command_with_no_paths_still_runs(tmp_path):
    """It decides what it reads, so an empty list must not skip it silently."""
    path = script(tmp_path, GOOD)
    block_text = block("mine", str(path)).replace('paths = ["code:docs/*.md"]\n', "")
    assert "\npaths" not in block_text
    _, store = built(tmp_path, block_text)
    assert claims(store) == {"GOOD-1": "A ledger is kept."}

