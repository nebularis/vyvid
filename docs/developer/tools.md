<!-- SPDX-License-Identifier: MIT -->

# Tool notes

**Unit type:** Register

How we run things in this repository, as notes of the Tools domain's type. A row names the domain's note it specialises, qualified with the domain, so the domain's row appears beneath ours. Without the domain configured the rows stand alone. Each row was checked against `mise.toml`.

| ID | Tool | Claim | Problem shape | Evidence | Activity | Technology | Specialises | Overrides |
|---|---|---|---|---|---|---|---|---|
| TOOL-1 | mise | **Run the tests with `mise run check:tests`, and every check, the tests with the writing, identifier and link checks, with `mise run check`.** | How do I run the tests and the checks here. | `check` depends on `check:tests`, `check:writing`, `check:identifiers` and `check:links` in `mise.toml`. `check:tests` runs pytest with the test extra. | | | | |
| TOOL-2 | mise | **Run the bake-off with `mise run bench:lattice -- --config <file>`. It is never part of `check`.** | How do I score find against the bake-off questions. | The task `bench:lattice` in `mise.toml` runs the bench script, and `check` does not depend on it. | | | | |
| TOOL-3 | mise | **Run any one-off command with `mise exec -- <command>`, such as `mise exec -- uv run vyd context`, so it uses the Python and uv that `mise.toml` pins.** | How do I run a command here without a bare interpreter. | `mise.toml` pins python 3.14.7 and uv 0.13.4. `mise exec -- which python` in this folder printed the mise-installed 3.14.7. | | | tools:NOTE-1 | |
| TOOL-4 | uv | **Install `vyd` from this working tree with `mise run install`, which runs `uv tool install --editable --force .`, so later edits run without a reinstall.** | How do I make the vyd command run my working copy. | The task `install` in `mise.toml` runs that command. | | | tools:NOTE-5 | |
