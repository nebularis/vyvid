# SPDX-License-Identifier: MIT
"""``vyd domain new <name> [--registers <type>] [--path <folder>]``: a new domain folder, ready to fill.

It writes the manifest, a facet extension stub, an empty register of the given type and a skill stub that
names the domain's recipe, and runs ``git init`` where the folder is not in a repository. It changes nothing
in the user's configuration, since a domain's entry there is the user's own. It prints the lines to add.
"""

from __future__ import annotations

import subprocess
import tomllib
from importlib import resources
from pathlib import Path

from .config import NAME_RE, ConfigError, load
from .configure import _rhs

SPDX = "<!-- SPDX-License-Identifier: MIT -->"
RECIPE = "how-do-i"
# The columns of a register of a type. A type not listed gets the default.
HEADERS = {
    "note": ["ID", "Tool", "Claim", "Problem shape", "Evidence", "Activity", "Technology", "Specialises", "Overrides"],
}
DEFAULT_HEADER = ["ID", "Claim", "Problem shape", "Activity", "Technology"]
FACETS = f"""{SPDX}

# Facet register

**Unit type:** Register

The facet values this domain adds under the general schemes, one table per scheme.

## Activity

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|

## Technology

| ID | Label | Broader | Related | Group | Definition | Scope note | Ratified |
|---|---|---|---|---|---|---|---|
"""


def types() -> dict[str, str]:
    """The register types every installation has, by name."""
    return tomllib.loads(resources.files("vyvid").joinpath("data/register-types.toml").read_text(encoding="utf-8"))["types"]


def plural(word: str) -> str:
    return word[:-1] + "ies" if word.endswith("y") else word + "s"


def family(register: str) -> str:
    return register.replace("-", "").upper()


def manifest(name: str, register: str) -> str:
    file = f"{plural(register)}.md"
    return f"""# SPDX-License-Identifier: MIT
name = "{name}"
description = "Replace with when to use this domain"
visibility = "private"
rules = []

[families]
{family(register)} = {{ defined = "{file}", type = "{register}" }}

[[recipes]]
name = "{RECIPE}"
description = "When asking how to do something in {name}"
budget = 1200
steps = [
  {{ step = "find", words = "{{question}}", kind = "{register}", limit = 6 }},
  {{ step = "take", n = 4 }},
]
"""


def skill(name: str) -> str:
    return f"""---
name: {name}
description: Use when working on {name}. Say here which tasks should load this skill.
---
{SPDX}

# {name}

Run `vyd recipe run {RECIPE} "<question>"` in the folder of the work, and read the entries it returns. Write here whatever about {name} no entry holds.
"""


def register(register: str) -> str:
    header = HEADERS.get(register, DEFAULT_HEADER)
    return f"{SPDX}\n\n# {register.capitalize()} register\n\n**Unit type:** Register\n\n| {' | '.join(header)} |\n|{'---|' * len(header)}\n"


def in_repository(folder: Path) -> bool:
    return subprocess.run(["git", "-C", str(folder), "rev-parse", "--is-inside-work-tree"], capture_output=True).returncode == 0


def default_path(name: str) -> Path | None:
    """The knowledge base's ``domains/<name>``, or None where no knowledge base is configured."""
    try:
        kb = load().kb
    except ConfigError:
        return None
    return kb / "domains" / name if kb else None


def new(name: str, registers: str, path: Path | None) -> int:
    if not NAME_RE.match(name) or name == "general":
        print(f"vyd: '{name}' is not a domain name. Use lower-case letters, digits and dashes, starting with a letter, and not 'general'")
        return 2
    if registers not in types():
        print(f"vyd: '{registers}' is no register type. Choose one of {', '.join(sorted(types()))}")
        return 2
    folder = path or default_path(name)
    if folder is None:
        print("vyd: no knowledge base is configured, so there is no default folder. Give one with --path")
        return 2
    folder = folder.expanduser()
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        print(f"vyd: {folder} exists and is not empty, so nothing is written")
        return 2
    files = {"domain.toml": manifest(name, registers), "facets.md": FACETS, f"{plural(registers)}.md": register(registers), f"skills/{name}/SKILL.md": skill(name)}
    for relative, text in files.items():
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")
    if not in_repository(folder):
        subprocess.run(["git", "init", "-q", "-b", "main", str(folder)], check=True)
    print(f"wrote {folder}: {', '.join(files)}")
    print("Add this to your configuration, or have vyd add it with vyd domain add:\n")
    print(f'[[domains]]\nname = "{name}"' + ("" if folder == default_path(name) else f"\npath = {_rhs(str(folder.resolve()))}"))
    return 0
