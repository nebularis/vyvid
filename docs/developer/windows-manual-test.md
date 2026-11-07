<!-- SPDX-License-Identifier: MIT -->

# Windows manual test of `vyd`

A person runs this by hand on a Windows machine with PowerShell and Git for Windows, against the install at tag `v0.2.14`. Every step has an identifier such as `W3.2`, one block to paste, what a pass looks like and what a failure would mean or what to capture. The results go into one file under one test folder, and a final section removes everything.

The PowerShell forms in this file have not been run on Windows, and none has been run in PowerShell at all. That includes every step added for v0.2.14, which are W3.10 to W3.12, W4.11, W4.12, W5.13, W5.14, W6.16 to W6.20 and W13.11 to W13.13. The `vyd` commands, their options and their expected output were run on macOS with a POSIX shell against the code at the tag, in a scratch folder with a scratch configuration. The changes of v0.2.15 to encodings, pipes and `trusted_repositories` under `core.autocrlf` were exercised on macOS with other code pages and with real pipes, and none of it has run on Windows or in PowerShell. Expect to correct a PowerShell form that does not behave as written, and record that as a NOTE with the fix, since a wrong script is a result too. The sections below say which expected outputs were seen on macOS and which come from reading the code.

## How the test is meant to run

- The machine can pull from GitHub over https and cannot push. Only public repositories are used. No step needs a private domain, and none is expected.
- A download that is refused, whether the embedding model, a package index or a Python interpreter, is a result to record with NOTE, never a failure of the run. Carry on with the sections that do not need it. Without the embedding model `vyd find` cannot rank by meaning and says so. `vyd read`, `vyd node`, `vyd exists`, `vyd reaches`, `vyd sparql`, `vyd misses`, `vyd gap`, `vyd close` and the symbol form of `vyd find` still answer, and so do the checks and the work board.
- `uv`, `mise` or a compiler may be absent. Each section says what it needs and what to do without it.
- Nothing is pushed. Nothing is written to `%USERPROFILE%\.claude` or `%USERPROFILE%\.copilot` before W14, which is optional and last.
- Run each block once, in order, in one PowerShell window. A block that appends to the scratch configuration makes a duplicate entry if it runs twice. To start a section again, delete the entry it added from `config.toml` first, or run W15.2 and begin again.
- Do not paste a block that was not meant for the window you are in. The blocks mix Windows PowerShell 5.1 and PowerShell 7 forms only where this file says so, and every other block is meant to run in both.

## Sections at a glance

The times are estimates, not measurements. The first run of W5 includes the model download, W5.14 adds two waits of about a minute, and W13 includes a clone of a large repository.

| Section | Covers | Needs | Estimated time |
|---|---|---|---|
| W0 | Helper functions, test folder, environment | PowerShell | 3 minutes |
| W1 | Windows, PowerShell, git, long paths, uv, mise, Python, code page | nothing | 5 minutes |
| W2 | Install at the tag with and without the symbols extra, the encoding of the name | W1, uv or Python 3.11 or later, package downloads | 10 minutes |
| W3 | Configuration, folders, path forms, byte order mark, line endings, bad configuration, editing it with commands | W2 | 15 minutes |
| W4 | Cloning public domains, audit, a new local domain, changing a domain's trust | W3, git, GitHub over https for the clones, a real console for W4.12 | 15 minutes |
| W5 | The index, queries, logs, rebuild, store lock, a code fence, the reason for a build without vectors | W4, the model download for ranking | 20 minutes |
| W6 | Trust, a repository trusted by the user's own configuration, symbolic links, worktrees, paths with spaces and non-ASCII characters | W5, a real console for the trust prompt | 30 minutes |
| W7 | Composed skills, `vyd check skills`, line endings | W5 | 10 minutes |
| W8 | The reminder hook and what install registers | W7 | 15 minutes |
| W9 | Work board, roadmap, presence, git hook | W5, git | 15 minutes |
| W10 | Identifier, citation, move and private documents checks | W5, W7 | 10 minutes |
| W11 | Source symbols | W2 with the extra, W5 | 5 minutes |
| W12 | `vyd install` into scratch folders | W5 | 10 minutes |
| W13 | LATTICE on the switch, the memory figure | W4, GitHub over https, optionally mise | 30 minutes or more |
| W14 | Optional, writes to the real client folders | W12 | 10 minutes |
| W15 | Return the results, clean up | W0 | 5 minutes |

Dependencies between sections:

- W0 and W2 are needed by every other section that runs `vyd`.
- W3.3 creates the scratch configuration that W4 to W14 append to. W3.10 to W3.12, W4.11 and W4.12 use scratch files of their own and leave it alone.
- W4.7 and W4.8 create the local domain `demo`, which W5 to W12 use. Those sections still work with no network.
- W5.2 creates the project `example-service`, which W5, W7, W8, W10, W11 and W12 use. W5.13 and W5.14 add to it.
- W9 and the private documents step of W10 create their own projects. W6.16 creates the repository that W6.17 to W6.20 use, and defines `WithOwn`, which needs the `demo` domain of W4.8.
- W13 reads the domains cloned in W4 and stops at W13.2 when the chosen branch holds no `vyvid.toml`. W13.11 and W13.12 need the bootstrap of W13.7.

## Where each expected output came from

- Seen on macOS at the tag, v0.2.14: the output of `vyd config`, `kb`, `domain`, `build`, `find`, `read`, `node`, `exists`, `reaches`, `sparql`, `misses`, `gap`, `close`, `install` with and without `--project`, `--target`, `--dry-run` and `--hooks`, `check skills`, `check identifiers`, `check citations`, `move check`, `docs record`, `board`, `work build`, `work roadmap`, `work check`, `work parse`, `work normalise`, `work rename`, `here`, `store prune`, `handoff` and `vyd-hook`.
- Reproduced on macOS by forcing output encodings with `PYTHONIOENCODING`, and with locales such as `zh_CN.GBK`: in v0.2.15 `vyd --version` prints `vyvid` and the version where the stream cannot hold the name, and the name where it can (W2.3). Before it the same command ended in a `UnicodeEncodeError`.
- Reproduced on macOS with the `core.autocrlf` setting forced on a clone: the grant of W6.20, which since v0.2.15 compares what git would store for the file with the blob at `HEAD`.
- Reproduced on macOS: the configuration read with a byte order mark and as UTF-16 in W3.5 to W3.7, the refusal of a byte order mark in a settings file in W12.6, and the CRLF clone checks of W7.7 and W10.5.
- Seen on macOS at v0.2.14 in a scratch home with the user's own configuration under it, with standard input from `/dev/null` where a pipe is meant and from a pseudo-terminal where a terminal is meant: `vyd domain add`, `remove` and `trust` (W3.10, W4.11, W4.12), `vyd project add`, `set`, `remove` and `scan` and `vyd family add` and `remove` (W3.11, W3.12), the refusals of a gated change from a pipe, the raise at a pseudo-terminal, `trusted_repositories` with its lapse on an uncommitted edit, its refusal for a fork whose `upstream` alone is listed and for a list in a `VYVID_CONFIG` file, and the clone made with `core.autocrlf=true` (W6.16 to W6.20), the reason an automatic build gives and its retry (W5.14, with a refusing proxy and the waits as written), the code fence reader (W5.13), the changed lines of W6.1, W5.3, W7.1 and W12.1, the prompts and refusals of `vyd trust` (W6.2 to W6.4), the reads of W13.6 against LATTICE's `main` with the five public domains cloned, and the figure of W13.11.
- Read from the code and not run anywhere: the terminal check of `vyd trust` on a Windows console, the trust sharing and lapse by hash (W6.5 to W6.7), the effect of `WIN_PD_OVERRIDE_LOCAL_APPDATA` (W6.16), the whole of `mise run check:low-memory` and its exit 3 (W13.12), what Windows reports for the memory figure (W13.11), the hook commands under PowerShell (W8.7), file locks (W5.12), the time limit of a command extractor (W6.15), symbolic links (W6.8), long paths (W6.13), the case of a path (W6.12), non-ASCII paths under the default encoding (W6.10), the Windows mode bits (W4.9) and the mise tasks of W13, apart from the reads named above. Nothing in the steps added for v0.2.14 has run in PowerShell. Their PowerShell forms were written from the commands that did run, so each is as likely to need a correction as the older ones.
- Run on Windows 11 with Python 3.14 by the test suite, after v0.2.17, unelevated and without Developer Mode: the effect of `WIN_PD_OVERRIDE_LOCAL_APPDATA` and `WIN_PD_OVERRIDE_APPDATA` (W6.16), the time limit of a command extractor, which now ends what the command started too (W6.15), the refusal of a gated change when standard input is the null device, which answers `isatty()` on Windows (W4.11, W4.12), the grant of W6.20 under `core.autocrlf`, a directory junction in a domain, which the audit reports as a link (W6.8), and the resume command of a recipe, which is quoted for PowerShell there. A symbolic link and a path longer than 260 characters were not, since the machine allowed neither. None of this was run by hand in PowerShell, so the steps still stand.

## Windows risks and where they are exercised

| Risk found in the code | Where in `src/vyvid` | Step |
|---|---|---|
| The name Вивід is printed only where the stream's encoding can hold it, and as `vyvid` elsewhere, and a character the stream cannot hold is written as an escape | `streams.py`, `cli.py` printing of `--version`, `--help` and the `context` header | W2.3, W2.4, W4.5 |
| A configuration saved with a byte order mark or as UTF-16 is read, and one in another encoding is a problem naming the file | `config.py` `read_toml_text` | W3.5 to W3.7 |
| A settings file with a byte order mark is refused with a message | `install.py` `merged_settings` | W12.6 |
| `subprocess` with `text=True` and no encoding decodes git output with the ANSI code page, so non-ASCII folder and file names can be misread | `resolve.py`, `config.py`, `identifiers.py`, `citations.py`, `kb.py`, `symbols/store.py`, `extractors/owl.py`, `work/core.py` | W6.9 to W6.11 |
| The Claude Code hook command is a POSIX shell line, the Copilot and Codex entries have PowerShell forms | `install.py` `hook_command`, `powershell_command`, `hook_files` | W8.5 to W8.8 |
| `os.getuid` does not exist, so the hook state folder is named `vyvid-hook-user` in the temporary folder | `remind.py` `state_dir` | W8.4 |
| A folder is made owner-only with `chmod`, which does little on Windows | `credentials.py` `private_dir`, `remind.py` `state_dir` | W5.8 |
| The executable bit of a file in a domain is the only sign of an executable, and Windows files carry none | `audit.py` | W4.9 |
| A symbolic link needs a privilege or Developer Mode, and a clone without link support makes a text file. A directory junction needs neither, and the audit reports it as a link | `config.py` `escapes`, `audit.py` | W6.8 |
| `shutil.rmtree` of the store on a rebuild, while another process holds it open | `build.py` | W5.12 |
| A time limit stops a command and its children through a process group, which Windows does not have, so there it ends the tree with `taskkill /T` from the system folder | `config.py` `run_limited` | W6.15 |
| Trust is recorded against the bytes of `vyvid.toml`, so CRLF conversion by `core.autocrlf` changes the hash | `config.py` `_digest`, `file_key` | W6.6, W6.7 |
| A trust record and a checkout store are keyed by the text of a path, which differs by case | `config.py` `file_key`, `build.py` `store_dir` | W6.12 |
| A path longer than 260 characters in a linked worktree | `resolve.py`, `build.py` | W6.13 |
| A move compared byte for byte with the working tree differs under CRLF | `moves.py` | W10.5 |
| A repository listed in `trusted_repositories` is granted only while what git would store for its `vyvid.toml` is the blob committed at `HEAD`, which `core.autocrlf` does not change | `config.py` `file_granted` | W6.20 |
| The user's own configuration is found through the platform's folders, so a test can move it only with `WIN_PD_OVERRIDE_LOCAL_APPDATA`, which `platformdirs` reads before it asks Windows | `config.py` `own_config`, `granted_repositories` | W6.16 |
| A configuration command writes a path with forward slashes and `~` for the home folder, and a snippet printed by `vyd domain new` holds the path as a TOML string with its backslashes escaped | `configure.py` `place`, `newdomain.py` | W3.10, W3.11, W4.7 |
| A raise of a domain's trust, or a change of a key that reaches what a client runs, needs standard input to be a terminal, which a console host and a pipe answer differently | `cli.py` `_person`, `configure.py` `run` | W4.11, W4.12, W3.11 |
| The automatic build and the retry of a store without vectors depend on the download failing the same way under Windows' proxy settings | `ask.py` `open_stack`, `stale` | W5.14 |
| The memory figure of Windows is 100 minus the system's memory load, which is not the figure macOS gives for the same load | `tools/testing/mem_check` in LATTICE | W13.11, W13.12 |
| Composed skills must equal their sources whatever the checkout's line endings | `skills.py` | W7.7 |
| Files `vyd` writes must use LF | `install.py`, `skills.py` | W7.4, W12.2 |
| A stored pointer or identifier path must use forward slashes | `registers.py`, `extract.py`, `identifiers.py` | W5.4, W10.1 |
| A git hook runs under Git for Windows' shell with `GIT_DIR` set, and a byte order mark in the hook breaks its first line | `work/core.py` | W9.8 to W9.10 |

## W0 Setup

Run W0.1 in a new PowerShell window and again in any window you open later. It is safe to run more than once. It creates the test folder, defines the helper functions, and sets four environment variables for this window only.

The helper writes a note of every step into `results.md` under the test folder, writes files as UTF-8 without a byte order mark, and sets the console output encoding to UTF-8 for the length of a captured step so that the name Вивід is read correctly. `-Plain` runs a step with `PYTHONUTF8` removed and the console encoding left as it came, which is the default behaviour the tester sees. `PYTHONUTF8=1` is the workaround under test in W2, and it is set for every other step so that one defect does not hide the next.

#### W0.1 Helper functions

```powershell
$ErrorActionPreference = 'Continue'
$global:T = Join-Path $env:TEMP 'vyd-wintest'
$global:Results = Join-Path $T 'results.md'
$global:Utf8 = New-Object System.Text.UTF8Encoding($false)
$global:Code = Join-Path $T 'work\example-service'
$global:BoardRepo = Join-Path $T 'work\boardy'
$global:Dom = Join-Path $T 'dom demo'
New-Item -ItemType Directory -Force -Path $T | Out-Null
$env:VYVID_CONFIG = Join-Path $T 'config.toml'
$env:VYVID_HOOK_STATE = Join-Path $T 'hook-state'
$env:PYTHONUTF8 = '1'
$env:GIT_TERMINAL_PROMPT = '0'
$OutputEncoding = $Utf8

function Write-Utf8 {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Text, [switch]$Crlf, [switch]$Bom)
    $t = $Text -replace "`r`n", "`n"
    if ($Crlf) { $t = $t -replace "`n", "`r`n" }
    $dir = Split-Path -Parent $Path
    if ($dir) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
    [IO.File]::WriteAllText($Path, $t, (New-Object System.Text.UTF8Encoding($Bom.IsPresent)))
}

function Add-Utf8 {
    param([Parameter(Mandatory)][string]$Path, [Parameter(Mandatory)][string]$Text)
    $t = $Text -replace "`r`n", "`n"
    [IO.File]::AppendAllText($Path, $t, (New-Object System.Text.UTF8Encoding($false)))
}

function WithConfig {
    param([string]$Path, [Parameter(Mandatory)][scriptblock]$Do)
    $keep = $env:VYVID_CONFIG
    $env:VYVID_CONFIG = $Path
    try { & $Do } finally { $env:VYVID_CONFIG = $keep }
}

function Step {
    param([Parameter(Mandatory)][string]$Id, [Parameter(Mandatory)][scriptblock]$Do, [switch]$Plain)
    $global:LastId = $Id
    $savedUtf8 = $env:PYTHONUTF8
    $savedEnc = $null
    if ($Plain) { Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue }
    else { try { $savedEnc = [Console]::OutputEncoding; [Console]::OutputEncoding = $Utf8 } catch { $savedEnc = $null } }
    $global:LASTEXITCODE = $null
    try { $out = @(& $Do 2>&1 | ForEach-Object { "$_" }) }
    catch { $out = @('EXCEPTION: ' + $_.Exception.Message) }
    $code = $global:LASTEXITCODE
    if ($Plain -and $savedUtf8) { $env:PYTHONUTF8 = $savedUtf8 }
    if ($savedEnc) { try { [Console]::OutputEncoding = $savedEnc } catch {} }
    if ($null -eq $code) { $code = 'none' }
    if ($out.Count -gt 80) {
        $out = @($out[0..59]) + @('... ' + ($out.Count - 80) + ' lines left out ...') + @($out[($out.Count - 20)..($out.Count - 1)])
    }
    $cmd = (($Do.ToString().Trim() -split "`n") | Select-Object -First 12) -join "`n"
    $block = "### $Id`n" + 'command:' + "`n" + $cmd + "`n" + "exit code of the last program: $code`n" + ($out -join "`n") + "`n"
    [IO.File]::AppendAllText($global:Results, $block, $global:Utf8)
    foreach ($line in $out) { Write-Host $line }
    Write-Host "[$Id, exit code of the last program: $code]"
}

function Mark {
    param([Parameter(Mandatory)][string]$Id, [Parameter(Mandatory)][ValidateSet('PASS', 'FAIL', 'NOTE')][string]$Result, [string]$Comment = '')
    $c = $Comment -replace '[\r\n|]', ' '
    [IO.File]::AppendAllText($global:Results, "MARK|$Id|$Result|$c`n", $global:Utf8)
}

function Show-Results {
    param([switch]$NoRedact)
    if (-not (Test-Path $global:Results)) { 'no results file yet'; return }
    $blocks = @{}; $marks = @{}; $id = $null
    foreach ($line in [IO.File]::ReadAllLines($global:Results)) {
        if ($line.StartsWith('MARK|')) { $p = $line.Split('|', 4); $marks[$p[1]] = @($p[2], $p[3]); continue }
        if ($line.StartsWith('### ')) { $id = $line.Substring(4); $blocks[$id] = New-Object System.Collections.ArrayList; continue }
        if ($id) { [void]$blocks[$id].Add($line) }
    }
    $natural = { [regex]::Replace($_, '\d+', { param($m) $m.Value.PadLeft(4, '0') }) }
    $pass = 0; $bad = @()
    foreach ($k in ($marks.Keys | Sort-Object $natural)) { if ($marks[$k][0] -eq 'PASS') { $pass++ } else { $bad += $k } }
    $unmarked = @($blocks.Keys | Where-Object { -not $marks.ContainsKey($_) } | Sort-Object $natural)
    $o = New-Object System.Collections.ArrayList
    [void]$o.Add("Marked PASS: $pass. Marked FAIL or NOTE: $($bad.Count). Run but not marked: $($unmarked.Count).")
    [void]$o.Add('')
    [void]$o.Add('| Step | Result | Comment |')
    [void]$o.Add('|---|---|---|')
    foreach ($k in $bad) { [void]$o.Add("| $k | $($marks[$k][0]) | $($marks[$k][1]) |") }
    if ($unmarked.Count) { [void]$o.Add(''); [void]$o.Add('Not marked: ' + ($unmarked -join ', ')) }
    foreach ($k in $bad) {
        [void]$o.Add(''); [void]$o.Add("### $k")
        if ($blocks.ContainsKey($k)) { foreach ($l in $blocks[$k]) { [void]$o.Add($l) } }
    }
    $text = $o -join "`n"
    if (-not $NoRedact) {
        $pairs = @(@($env:USERNAME, '<user>'), @($env:COMPUTERNAME, '<computer>'), @($env:USERDOMAIN, '<domain>'), @($env:LOGONSERVER, '<server>'), @($env:USERDNSDOMAIN, '<dns-domain>'))
        foreach ($pair in $pairs) { if ($pair[0] -and $pair[0].Length -gt 1) { $text = $text.Replace($pair[0], $pair[1]) } }
    }
    $text
}
```

**Pass.** No output, and no red text. Check that `Get-Command Step, Mark, Show-Results, WithConfig, Write-Utf8, Add-Utf8` lists six functions.

**Failure.** A parse error means the paste was altered, usually by an editor that wrapped a line or changed quotation marks. Paste from the raw file.

To mark a step, run `Mark W1.1 PASS`, or `Mark W1.1 FAIL 'what happened'`, or `Mark W1.1 NOTE 'something to tell us'`. A later mark for the same step replaces an earlier one. `Show-Results` prints the failures table and the output of every step not marked PASS.

#### W0.2 Check the helper

```powershell
Step W0.2 {
    'plain ascii'
    'name check: ' + [string]::Join('', [char[]](0x412, 0x438, 0x432, 0x456, 0x434))
    $PSVersionTable.PSVersion.ToString()
}
Mark W0.2 PASS
Get-Content $Results
```

**Pass.** Three lines of output, the name line ending in the five Cyrillic letters of the name. The last command prints the results file, which holds the block for W0.2 and one `MARK` line.

**Failure.** If the letters print as question marks or boxes, note the console font and the code page from W1.5. That is a display result and does not stop the run.

## W1 Prerequisites and versions

Needs nothing. These steps change nothing.

#### W1.1 Windows and PowerShell

```powershell
Step W1.1 {
    [Environment]::OSVersion.VersionString
    'PowerShell ' + $PSVersionTable.PSVersion + ' ' + $PSVersionTable.PSEdition
    '64-bit system: ' + [Environment]::Is64BitOperatingSystem
    'temp folder: ' + (Get-Item $env:TEMP).FullName
    'test folder: ' + $T + ' (' + $T.Length + ' characters)'
}
```

**Pass.** The versions print. Mark which of PowerShell 5.1 or 7 this window is, since the rest of the run depends on it.

**Capture.** If the temporary folder is printed in the short 8.3 form with a tilde, add a NOTE, since every later path then has two spellings.

#### W1.2 Git and line-ending settings

```powershell
Step W1.2 {
    git --version
    'core.autocrlf = ' + (git config --get core.autocrlf)
    'core.longpaths = ' + (git config --get core.longpaths)
    'core.symlinks = ' + (git config --get core.symlinks)
    'user.name set: ' + [bool](git config --get user.name)
    'user.email set: ' + [bool](git config --get user.email)
}
```

**Pass.** A git version of 2.28 or later and the settings printed. Empty values mean unset. Git for Windows normally sets `core.autocrlf` to `true`, and several later steps depend on that, so mark it in the comment. Every repository this file creates sets its own user name and email, so an unset global identity is fine.

**Failure.** `git` not found stops the run. An older git than 2.28 does not know `git init -b`, so note the version and replace `-b main` with a following `git branch -m main`.

#### W1.3 Long-path setting

```powershell
Step W1.3 {
    $v = Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem' -Name LongPathsEnabled -ErrorAction SilentlyContinue
    'LongPathsEnabled = ' + $v.LongPathsEnabled
}
```

**Pass.** `LongPathsEnabled = 1` or `0`. It decides how W6.13 should end, so mark the value.

#### W1.4 uv, mise, Python and other tools

```powershell
Step W1.4 {
    foreach ($c in 'uv', 'mise', 'python', 'py', 'pwsh', 'powershell', 'bash') {
        $g = Get-Command $c -ErrorAction SilentlyContinue
        if ($g) { "$c found at $($g.Source)" } else { "$c not found" }
    }
    foreach ($c in 'uv', 'mise', 'python') {
        if (Get-Command $c -ErrorAction SilentlyContinue) { "$c version: " + (& $c --version 2>&1) }
    }
}
```

**Pass.** The list prints. Without `uv`, W2.1 uses its fallback W2.1b, which needs Python 3.11 or later. Without `mise`, W13 runs only its `vyd` steps. Without `bash` on the path, W8.6 finds Git for Windows' own.

#### W1.5 Console code page

```powershell
Step W1.5 -Plain {
    chcp
    'console output: ' + [Console]::OutputEncoding.WebName
    'console input: ' + [Console]::InputEncoding.WebName
    'pipeline to programs: ' + $OutputEncoding.WebName
    'ANSI code page: ' + [Text.Encoding]::Default.WebName
}
```

**Pass.** Prints the active code page, usually 437 or 850 on a console left at its default, and 65001 if UTF-8 is enabled system wide. The ANSI code page, usually windows-1252, is what Python uses for redirected output when UTF-8 mode is off, and it is the one W2.3 depends on.

#### W1.6 Whether `vyd` was used here before

```powershell
Step W1.6 -Plain {
    $d = Join-Path $env:LOCALAPPDATA 'vyvid'
    'folder exists: ' + (Test-Path $d)
    if (Test-Path $d) { Get-ChildItem $d -Recurse -Directory | Select-Object -ExpandProperty FullName }
    'tool already installed: ' + [bool](Get-Command vyd -ErrorAction SilentlyContinue)
}
```

**Pass.** Prints whether `%LOCALAPPDATA%\vyvid` existed before this run and whether a `vyd` was already on the path. W15 uses the answer to decide what to remove. If a `vyd` is already installed, W2.1 replaces it, and `uv tool install` with the earlier version restores it.

## W2 Install

Needs W1, and either `uv` or Python 3.11 or later, and a package index that answers.

#### W2.1 Install at the tag without the symbols extra

```powershell
Step W2.1 {
    uv tool install --force "git+https://github.com/nebularis/vyvid.git@v0.2.14"
    uv tool dir --bin
    Get-Command vyd, vyd-hook | Format-Table Name, Source -AutoSize | Out-String
}
```

**Pass.** The last lines of the install read like `Installed 2 executables: vyd, vyd-hook`, followed by the tool bin folder and both commands resolved.

**Failure.** A refusal to download Python, a package or the git source is a result to record. Mark NOTE with the message and continue with W2.1b if the git source came but a package did not, or stop the run if nothing installs. `uv tool update-shell` or adding the printed bin folder to `PATH` for this window fixes a command that is installed and not found.

#### W2.1b Fallback with no uv

Run this only if `uv` is absent. It needs Python 3.11 or later.

```powershell
Step W2.1b {
    python -m venv "$T\venv"
    & "$T\venv\Scripts\python.exe" -m pip install "git+https://github.com/nebularis/vyvid.git@v0.2.14"
    $env:PATH = "$T\venv\Scripts;" + $env:PATH
    $global:Py = "$T\venv\Scripts\python.exe"
    Get-Command vyd, vyd-hook | Format-Table Name, Source -AutoSize | Out-String
}
```

**Pass.** Both commands resolve under the test folder. Everything later works the same, but the extra of W2.7 is installed with `& $Py -m pip install "vyvid[symbols] @ git+https://github.com/nebularis/vyvid.git@v0.2.14"`. The `PATH` change lasts for this window only, so repeat the `$env:PATH` and `$global:Py` lines in a new window.

#### W2.2 Version

```powershell
Step W2.2 { vyd --version; vyd-hook --help }
```

**Pass.** `Вивід (vyvid) 0.2.14` and the usage text of `vyd-hook`, exit code 0.

**Failure.** Another version means the tag was not installed. Capture `uv tool list`.

#### W2.3 The name under the default encoding, output redirected

`Step` captures output through a pipe, which is the case a script or an agent meets. With `PYTHONUTF8` removed, Python writes redirected output in the ANSI code page, which has no Cyrillic letters. Since v0.2.15 `vyd` keeps that encoding and prints the name as `vyvid` where the encoding cannot hold it.

```powershell
Step W2.3 -Plain { vyd --version }
```

**Pass or note.** Seen on macOS with a narrow output encoding forced, this prints `vyvid 0.2.15`, exit code 0, and `vyd --help` and `vyd context` print `vyvid` in place of the name. Where the code page can hold the name it prints `Вивід (vyvid) 0.2.15`. A traceback ending `UnicodeEncodeError` is a failure, so mark FAIL with the last lines. Say which code page W1.5 showed.

**Capture.** The output, and the ANSI code page from W1.5.

#### W2.4 The name on the console itself

This step runs `vyd` directly in the window with no capture and no `PYTHONUTF8`, which is what a person typing sees. Do not wrap it in `Step`.

```powershell
Remove-Item Env:PYTHONUTF8 -ErrorAction SilentlyContinue
vyd --version
$env:PYTHONUTF8 = '1'
```

**Pass.** The name prints, perhaps with some letters shown as boxes when the console font lacks them, or `vyvid` where the console's code page cannot hold it. A traceback is a failure. Run `Mark W2.4 PASS` or `Mark W2.4 FAIL 'comment'` yourself.

#### W2.5 The workaround

```powershell
Step W2.5 { $env:PYTHONUTF8; vyd --version; vyd --help }
```

**Pass.** `1`, then the name correctly, then the help text with all subcommands from `context` to `close`, exit code 0. This is the form every later step uses, so a failure here makes the rest unreliable.

**Capture.** If this fails, the whole output.

#### W2.6 Every subcommand answers `--help`

```powershell
Step W2.6 {
    foreach ($c in 'context', 'kb', 'docs', 'board', 'work', 'here', 'resolve', 'build', 'check', 'move', 'recipe', 'store', 'domain', 'project', 'family', 'handoff', 'install', 'config', 'trust', 'find', 'exists', 'node', 'read', 'reaches', 'sparql', 'misses', 'gap', 'close') {
        vyd $c --help *> $null
        '{0,-10} exit {1}' -f $c, $LASTEXITCODE
    }
    vyd-hook --help *> $null
    'vyd-hook   exit ' + $LASTEXITCODE
}
```

**Pass.** Twenty-nine lines, each `exit 0`.

#### W2.7 Install with the symbols extra

```powershell
Step W2.7 {
    uv tool install --force "vyvid[symbols] @ git+https://github.com/nebularis/vyvid.git@v0.2.14"
    $global:Py = Join-Path (uv tool dir) 'vyvid\Scripts\python.exe'
    & $Py -c "import tree_sitter, tree_sitter_python; print('grammars ok')"
    vyd --version
}
```

**Pass.** `grammars ok` and the version. W11 needs this.

**Failure.** A grammar wheel that does not exist for this Python, or a compiler asked for, is a result to record. W11 then shows what `vyd` says without the extra. If you used W2.1b, install the extra with the pip command given there, and set `$global:Py` to the venv's `python.exe`.

## W3 Configuration

Needs W2. These steps point `VYVID_CONFIG` at scratch files and put it back. `WithConfig` restores the variable, so do not edit it by hand.

#### W3.1 No configuration

```powershell
Step W3.1 { WithConfig $null { vyd config } }
```

**Pass.** Four lines like these, the first naming a path under `%LOCALAPPDATA%\vyvid\vyvid`.

```text
configuration: C:\Users\<user>\AppData\Local\vyvid\vyvid\config.toml (absent, so the general scope alone)
configuration trust: trusted
domains: none
projects: none
```

**Failure.** A traceback, or a path outside `%LOCALAPPDATA%`, goes into the comment. If a real configuration exists at that path, the output names domains and projects. That is not a failure, and nothing here changes it.

#### W3.2 Where the folders resolve

```powershell
Step W3.2 {
    & $Py -c "import platformdirs as p; print('config', p.user_config_path('vyvid')); print('data', p.user_data_path('vyvid')); print('state', p.user_state_path('vyvid')); print('cache', p.user_cache_path('vyvid'))"
}
```

**Pass.** Four lines, each under `%LOCALAPPDATA%\vyvid\vyvid`, the cache one ending in `Cache`. The configuration, the trust record in the state folder and the model cache would live there by default. The next step moves what it can into the test folder.

#### W3.3 The scratch configuration

```powershell
Step W3.3 {
    Write-Utf8 $env:VYVID_CONFIG @"
[framework]
kb = '$T\kb'
store = '$T\store'
glue = "stop"

[embedding]
cache = '$T\model'
"@
    vyd config
}
```

**Pass.** `configuration:` names the file under the test folder, `configuration trust: not trusted, so no glue or command extractor runs. A person runs vyd trust in a terminal`, `domains: none`, `projects: none`. A configuration at any other path than your own is untrusted by design.

The single quotes make TOML literal strings, so the backslashes need no doubling. In a double-quoted TOML string each backslash must be doubled, and a bare `\U` is an error.

#### W3.4 Path forms

Four domains are listed with folders that do not exist, each written a different way. This also checks that a listed domain with a missing folder is named and nothing is removed.

```powershell
Step W3.4 {
    $fwd = $T -replace '\\', '/'
    Write-Utf8 "$T\cfg-paths.toml" @"
[framework]
kb = '$T\kb'

[[domains]]
name = "p-back"
path = '$T\paths\back\d1'

[[domains]]
name = "p-fwd"
path = '$fwd/paths/fwd/d2'

[[domains]]
name = "p-tilde"
path = '~/vyd-wintest-absent/d3'

[[domains]]
name = "p-space"
path = '$T\paths\with space\d4'
"@
    WithConfig "$T\cfg-paths.toml" { vyd config }
}
```

**Pass.** Four `NOTE: domain ... has no folder here, at <path>, so it gives nothing on this machine` lines. Each path is absolute with backslashes only, the `~` expanded to the user profile folder, and the space kept. Then `domains: p-back, p-fwd, p-tilde, p-space`.

**Failure.** A path with forward slashes left as written, a literal `~`, or a path cut at the space. Capture the four lines.

#### W3.5 A byte order mark

Windows PowerShell 5.1 writes one with `Set-Content -Encoding UTF8` and `Out-File -Encoding utf8`, and many editors do.

```powershell
Step W3.5 {
    $good = [IO.File]::ReadAllText($env:VYVID_CONFIG)
    Write-Utf8 "$T\cfg-bom.toml" $good -Bom
    'first bytes: ' + (([IO.File]::ReadAllBytes("$T\cfg-bom.toml")[0..2]) -join ' ')
    WithConfig "$T\cfg-bom.toml" { vyd config }
}
```

**Pass.** `first bytes: 239 187 191`, and `vyd config` reads the file and exits 0. This needs a build at or after the fix on `main`, so the tag `v0.2.14` fails here with a traceback ending `tomllib.TOMLDecodeError: Invalid statement (at line 1, column 1)`, which is the known failure at that tag.

#### W3.6 What `Set-Content -Encoding UTF8` writes in this PowerShell

```powershell
Step W3.6 {
    Get-Content -Raw $env:VYVID_CONFIG | Set-Content -Encoding UTF8 "$T\cfg-setcontent.toml"
    'PowerShell ' + $PSVersionTable.PSVersion
    'first bytes: ' + (([IO.File]::ReadAllBytes("$T\cfg-setcontent.toml")[0..2]) -join ' ')
    WithConfig "$T\cfg-setcontent.toml" { vyd config }
}
```

**Pass.** In PowerShell 7 the first bytes are not `239 187 191` and `vyd config` reads the file. In Windows PowerShell 5.1 they are, and `vyd config` still reads the file, as in W3.5. Mark which you saw.

#### W3.7 UTF-16

`Out-File` and `>` write UTF-16 in Windows PowerShell 5.1.

```powershell
Step W3.7 {
    [IO.File]::WriteAllText("$T\cfg-utf16.toml", [IO.File]::ReadAllText($env:VYVID_CONFIG), [Text.Encoding]::Unicode)
    'first bytes: ' + (([IO.File]::ReadAllBytes("$T\cfg-utf16.toml")[0..1]) -join ' ')
    WithConfig "$T\cfg-utf16.toml" { vyd config }
}
```

**Pass.** `first bytes: 255 254`, and `vyd config` reads the file and exits 0, with the same condition on the build as W3.5.

#### W3.8 CRLF line endings

```powershell
Step W3.8 {
    Write-Utf8 "$T\cfg-crlf.toml" ([IO.File]::ReadAllText($env:VYVID_CONFIG)) -Crlf
    'carriage returns: ' + ([IO.File]::ReadAllBytes("$T\cfg-crlf.toml") | Where-Object { $_ -eq 13 }).Count
    WithConfig "$T\cfg-crlf.toml" { vyd config }
}
```

**Pass.** A non-zero count of carriage returns, and the same four lines as W3.3 apart from the path.

#### W3.9 A bad configuration is refused with its problems

```powershell
Step W3.9 {
    Write-Utf8 "$T\cfg-bad.toml" @"
[[domains]]
name = "x"
trust = "bogus"
parents = ["nope"]
"@
    WithConfig "$T\cfg-bad.toml" { vyd config }
}
```

**Pass.** Exit code 2, the line `the configuration at <path> cannot be used:` and a list of problems that includes `domain 'x': trust is 'bogus', not one of own, reviewed, knowledge` and `domain 'x': parent 'nope' is no domain`.

#### W3.10 Add and remove a domain by command

`vyd domain add` and `vyd domain remove` edit a configuration through the real loader, which checks the result before anything is written, and they leave the rest of the file as it was. These steps use a second scratch file, `cfg-edit.toml`, so the configuration that W4 to W14 append to is untouched. The file has two comments, one on a line of its own and one at the end of a line, and both must survive every change.

```powershell
Step W3.10 {
    Write-Utf8 "$T\cfg-edit.toml" @"
# a comment of mine, which every change below must keep
[framework]
kb = '$T\kb'
store = '$T\store'
glue = "stop" # and one at the end of a line
"@
    WithConfig "$T\cfg-edit.toml" {
        function Tally { '[[domains]] tables: ' + @(Select-String -Path $env:VYVID_CONFIG -Pattern '^\[\[domains\]\]').Count + ', lines with a comment: ' + @(Select-String -Path $env:VYVID_CONFIG -Pattern '#').Count }
        vyd domain add extra --path "$T\dom extra" --dry-run
        Tally
        vyd domain add extra --path "$T\dom extra"
        Tally
        Select-String -Path $env:VYVID_CONFIG -Pattern '^path' | ForEach-Object { $_.Line }
        'backslashes in a path line: ' + @(Select-String -Path $env:VYVID_CONFIG -Pattern '^path.*\\').Count
        vyd config
        vyd domain add extra --path "$T\dom extra"
        'exit ' + $LASTEXITCODE
        vyd domain remove extra --dry-run
        vyd domain remove extra
        Tally
        vyd domain remove extra
        'exit ' + $LASTEXITCODE
    }
}
```

**Pass.** The dry run prints `would write <path>\cfg-edit.toml`, a diff that adds a `[[domains]]` table with `name = "extra"`, a `path` line and `trust = "knowledge"`, then `dry run, nothing written`, and the first `Tally` reads `[[domains]] tables: 0, lines with a comment: 2`. The real add prints `writing <path>`, the same diff, `wrote <path>` and `<folder> does not exist yet. Write it with: vyd domain new extra --path '<folder>'`, and the second `Tally` reads `[[domains]] tables: 1, lines with a comment: 2`. Seen on macOS, the path line reads `path = "~/vyd-wintest/dom extra"`.

The path line is the Windows finding. `vyd` writes a path with forward slashes, as `~/` followed by the part below the home folder where there is one and as an absolute path such as `C:/...` where there is not, so the line should read `path = "~/AppData/Local/Temp/vyd-wintest/dom extra"` or a `C:/` form, and `backslashes in a path line: 0`. A backslash there, or a `path` that TOML refuses, goes into the comment. The `kb` and `store` lines keep the backslashes they were written with, in single quotes.

`vyd config` then prints `NOTE: domain extra has no folder here, at <path>\dom extra, so it gives nothing on this machine` and `domains: extra`. The repeated add exits 1 with `vyd: nothing written, since <path> would not load cleanly:` and `vyd: domain 'extra': a domain needs a unique lower-case name`. The removal dry run prints a diff that deletes the table and `dry run, nothing written`. The removal prints `wrote <path>` and `left <folder> as it is. A remove never deletes a clone or a folder`, and its `Tally` reads `[[domains]] tables: 0, lines with a comment: 2`. The last remove exits 1 with `vyd: domain 'extra' is not configured`.

**Failure.** A lost comment, a backslash in a path line, or a traceback.

#### W3.11 Add and change a project by command

`vyd project add` reads the code folder and the remotes from a git checkout, so this step makes a small one with an `origin`. The address uses the reserved `example.invalid` name, so nothing is fetched. `project set` changes one plain key of a project, and the keys that reach what a client loads or runs, such as `hook_clients`, are refused unless a person is at a terminal. Standard input is a pipe in the refused call, so the refusal is what a script or an agent meets.

```powershell
Step W3.11 {
    $E = Join-Path $T 'work\edit-demo'
    New-Item -ItemType Directory -Force -Path "$E\docs" | Out-Null
    Write-Utf8 "$E\AGENTS.md" "# Agent contract`n`nAsk the index first.`n"
    Write-Utf8 "$E\docs\debt.md" @'
# Debt

**Unit type:** Register

| # | Debt | Spotted | Cost while it stays | Likely home | Bears on |
|---|---|---|---|---|---|
| DEBT-1 | **A bare read uses the console code page.** | today | a wrong name | a later slice | |
'@
    git -C $E init -q -b main
    git -C $E config user.email 'wintest@example.invalid'
    git -C $E config user.name 'wintest'
    git -C $E remote add origin https://example.invalid/team/edit-demo.git
    git -C $E add -A
    git -C $E commit -q -m 'initial'
    WithConfig "$T\cfg-edit.toml" {
        vyd domain add extra --path "$T\dom extra" | Out-Null
        vyd project add edit-demo --code $E --docs "$E\docs" --contract 'code:AGENTS.md' --domain extra --visibility public --dry-run
        '[[projects]] tables: ' + @(Select-String -Path $env:VYVID_CONFIG -Pattern '^\[\[projects\]\]').Count
        vyd project add edit-demo --code $E --docs "$E\docs" --contract 'code:AGENTS.md' --domain extra --visibility public | Out-Null
        Select-String -Path $env:VYVID_CONFIG -Pattern '^(code|docs|match) =' | ForEach-Object { $_.Line }
        vyd project set edit-demo skill_prefix ed- --dry-run
        vyd project set edit-demo skill_prefix ed-
        '' | vyd project set edit-demo hook_clients claude-code
        'exit ' + $LASTEXITCODE
        vyd project set edit-demo hook_clients claude-code --dry-run
        vyd config $E
    }
}
```

**Pass.** The dry run prints a `[[projects]]` table with `name = "edit-demo"`, `visibility = "public"`, a `code` line, `match = { remote = ["example.invalid/team/edit-demo"] }` (the checkout's `origin`, normalised), a `docs` line, `contract = "code:AGENTS.md"` and `domains = ["extra"]`, then `dry run, nothing written` and `[[projects]] tables: 0`. The `code` and `docs` lines of the real add follow the path rule of W3.10, so on macOS they read `code = "~/vyd-wintest/work/edit-demo"` and `docs = "~/vyd-wintest/work/edit-demo/docs"`, here with the Windows home-relative or `C:/` form and forward slashes. The `skill_prefix` dry run prints a diff adding `skill_prefix = "ed-"` and the real run prints `wrote <path>`.

The piped `hook_clients` call exits 1 with `vyd: hook_clients reaches what a client loads or runs. A person must run this command, in a terminal` and writes nothing. Its dry run prints a diff adding `hook_clients = ["claude-code"]` and `dry run, nothing written. hook_clients reaches what a client loads or runs, so a person must run it for real, in a terminal`. `vyd config $E` ends with `projects: edit-demo`.

**Failure.** A project that is written with the checkout's backslash path, or a `hook_clients` change written from the piped call.

#### W3.12 Scan a project's registers and change its families

`vyd project scan` reads the register tables in a project's documents and proposes a family for each, writing them only with `--apply`. `vyd family add` and `vyd family remove` change one family.

```powershell
Step W3.12 {
    WithConfig "$T\cfg-edit.toml" {
        vyd project scan edit-demo
        vyd project scan edit-demo --apply --dry-run
        vyd project scan edit-demo --apply
        vyd family remove edit-demo DEBT --dry-run
        vyd family remove edit-demo DEBT
        vyd family add edit-demo DEBT --defined 'docs:debt.md' --type debt --dry-run
        vyd family add edit-demo DEBT --defined 'docs:debt.md' --type debt
        vyd family add edit-demo DEBT --defined 'docs:debt.md' --type debt
        'exit ' + $LASTEXITCODE
        vyd project remove edit-demo --dry-run
        vyd project remove edit-demo
        'lines with a comment: ' + @(Select-String -Path $env:VYVID_CONFIG -Pattern '#').Count
    }
}
```

**Pass.** The scan prints `project edit-demo: scanned <path>\work\edit-demo\docs`, `Proposed, to read before it is written to <path>\cfg-edit.toml:`, the table `[projects.families]` with `DEBT = { defined = "docs:debt.md", type = "debt" }   # 1 row in debt.md`, and `Write them with: vyd project scan edit-demo --apply`. The `--apply --dry-run` form prints the same proposal, then a diff adding the `[projects.families]` table and `dry run, nothing written`. `--apply` prints `wrote <path>`. The family removal prints a diff deleting the table, and the real one adds `family 'DEBT' is removed. The register it was defined in is left as it is`. The family add writes the same table back, and its dry run prints the diff first. The repeated add exits 1 with `vyd: project 'edit-demo': family 'DEBT' exists. Remove it first with vyd family remove`. The project removal prints a diff deleting the project's tables and, when real, `project 'edit-demo' is removed from the configuration. Its index store and logs, its folders and its documents are left as they are`. The last line reads `lines with a comment: 2`, so both comments survived every change of W3.10 to W3.12.

**Failure.** A lost comment, a table left behind after a removal, or a `--dry-run` that wrote.

## W4 Domains

Needs W3.3 and git. The clones need GitHub over https. If they are refused, mark NOTE, skip W4.2 to W4.6, and go on, since W4.7 onwards need no network.

#### W4.1 Declare the six public domains

```powershell
Step W4.1 {
    $tpl = @'

[[domains]]
name = "NAME"
remote = "https://github.com/nebularis/vyvid-NAME.git"
trust = "knowledge"
git = { pull = "manual", commit = "manual", push = "manual" }
'@
    foreach ($n in 'tools', 'lifecycle', 'rdf-modelling', 'triple-stores', 'python', 'haskell') {
        Add-Utf8 $env:VYVID_CONFIG ($tpl.Replace('NAME', $n) + "`n")
    }
    vyd config
}
```

**Pass.** Six `NOTE: domain ... has no folder here` lines, each ending `vyd kb pull <name> fetches it`, and `domains: tools, lifecycle, rdf-modelling, triple-stores, python, haskell`.

The repositories are `nebularis/vyvid-tools`, `vyvid-lifecycle`, `vyvid-rdf-modelling`, `vyvid-triple-stores`, `vyvid-python` and `vyvid-haskell`. The owner of each was read from its git remote.

#### W4.2 Clone them

```powershell
Step W4.2 { vyd kb clone }
```

**Pass.** One line per domain, `<name>: cloned https://github.com/nebularis/vyvid-<name>.git`, exit code 0.

**Failure.** A refused download or a credential prompt shows as a failure line for that domain. Record which domains cloned. With `GIT_TERMINAL_PROMPT=0` set in W0.1, a prompt is an error and not a hang.

#### W4.3 Status and pull

```powershell
Step W4.3 { vyd kb status; vyd kb pull tools; vyd kb pull --due }
```

**Pass.** `kb status` prints, per domain, `clone of <url>, branch main, ahead 0 behind 0, clean, last pulled never` and the policy line `pull=manual commit=manual push=manual, trust knowledge`. `kb pull tools` prints `tools: Already up to date.` and `--due` prints nothing, since the policy is manual.

#### W4.4 Configuration after cloning

```powershell
Step W4.4 { vyd config }
```

**Pass.** No `has no folder here` note for a domain that cloned.

#### W4.5 Context outside any project

```powershell
Step W4.5 { vyd context "$T\kb" --no-pull }
```

**Pass.** A header `Вивід 0.2.14: the contract for <folder>`, then `1. general (public)`. No project is named, since none is configured yet. Try it again with `-Plain` to see the header fail when redirected.

```powershell
Step W4.5b -Plain { vyd context "$T\kb" --no-pull }
```

**Note.** The header carries the name, so under the default encoding it reads `vyvid` as in W2.3. A traceback is a failure.

#### W4.6 Audit a domain you did not write

```powershell
Step W4.6 { vyd domain audit "$T\kb\domains\tools" }
```

**Pass.** Either nothing or lines of the form `file:line kind text`, such as an `html-comment` for a licence line. Nothing from the domain runs. Exit code 0 with no findings and 1 with findings. A crash is a failure.

Run `vyd domain audit "$T\kb\domains\tools" --json` too, and check it prints a JSON array.

#### W4.7 Make a local domain

```powershell
Step W4.7 {
    vyd domain new demo --path $Dom
    Get-ChildItem $Dom -Recurse -File -Name | Where-Object { $_ -notlike '.git*' }
}
```

**Pass.** `wrote <folder>: domain.toml, facets.md, notes.md, skills/demo/SKILL.md`, a snippet to add to the configuration, and the listing of `domain.toml`, `facets.md`, `notes.md` and `skills\demo\SKILL.md`. The folder name has a space on purpose. The command also ran `git init` in the folder. The snippet writes the path as a TOML string with its backslashes escaped, so it parses and gives the path back, and the command names `vyd domain add` as the way to add the domain for you. W4.8 writes the entry by hand. Check that the snippet's `path` has doubled backslashes and mark NOTE if it does not, since this has not been run on Windows.

#### W4.8 Add it to the configuration

```powershell
Add-Utf8 $env:VYVID_CONFIG @"

[[domains]]
name = "demo"
path = '$Dom'
visibility = "public"
trust = "own"
"@
Step W4.8 { vyd config }
Mark W4.8 PASS
```

**Pass.** `domains:` ends with `demo` and there is no note for it. The domain is public and trusted as your own because you wrote it a minute ago. Mark it yourself after reading the output.

#### W4.9 An executable in a domain, and the mode bit

A POSIX file carries an executable bit and the audit reports it. A Windows file carries none, so the audit may not.

```powershell
Step W4.9 {
    Write-Utf8 "$Dom\run.sh" "#!/bin/sh`necho hi`n"
    git -C $Dom add run.sh
    git -C $Dom update-index --chmod=+x run.sh
    git -C $Dom ls-files --stage run.sh
    vyd domain audit $Dom
    git -C $Dom rm -f --cached run.sh | Out-Null
    Remove-Item "$Dom\run.sh"
}
```

**Expected on macOS.** The stage line starts `100755`, and the audit prints `run.sh:0 file-type .sh is not Markdown, TOML, Turtle, plain text or a licence` and `run.sh:0 executable has an executable bit`. On Windows the `file-type` line should appear and the `executable` line probably not. Mark NOTE with 'executable bit not reported' if so, since the audit then misses the one sign it uses, even though git records the mode.

#### W4.10 Record a change in a managed domain

```powershell
Step W4.10 {
    if (Test-Path "$T\kb\domains\tools\notes.md") {
        Add-Utf8 "$T\kb\domains\tools\notes.md" "`n"
        Push-Location "$T\kb\domains\tools"
        vyd kb record notes.md -m "scratch edit"
        git status --short
        git restore --staged notes.md
        git checkout -- notes.md
        Pop-Location
    } else { 'tools was not cloned, so this step is skipped' }
}
```

**Pass.** `tools: staged notes.md. Commit is manual, so nothing is committed`, then `M  notes.md` from git. The edit is undone at the end. Nothing is committed or pushed.

#### W4.11 Lower the trust of a domain, and be refused a raise

`vyd domain trust` changes the trust of a configured domain. Lowering it needs no one at a terminal. Raising it to `own`, or to `reviewed` at a commit, gives the domain's rules, skills and recipes to every project that uses it, so it needs a person at a terminal. This step uses a third scratch file with a domain that starts at `own`, and the raising calls have a pipe for input, which is what a script or an agent meets.

```powershell
Step W4.11 {
    vyd domain new extra --path "$T\dom extra" | Out-Null
    Write-Utf8 "$T\cfg-trust.toml" @"
[framework]
kb = '$T\kb'
store = '$T\store'

[[domains]]
name = "extra"
path = '$T\dom extra'
trust = "own"
"@
    WithConfig "$T\cfg-trust.toml" {
        vyd domain trust extra knowledge --dry-run
        vyd domain trust extra knowledge
        Select-String -Path $env:VYVID_CONFIG -Pattern '^trust' | ForEach-Object { $_.Line }
        vyd domain trust extra knowledge
        '' | vyd domain trust extra own
        'exit ' + $LASTEXITCODE
        '' | vyd domain trust extra own --dry-run
        '' | vyd domain trust extra reviewed
        'exit ' + $LASTEXITCODE
        '' | vyd domain trust extra reviewed --commit abc
        'exit ' + $LASTEXITCODE
        '' | vyd domain trust extra reviewed --commit 0123456789abcdef
        'exit ' + $LASTEXITCODE
    }
}
```

**Pass.** The dry run prints a diff that changes `trust = "own"` to `trust = "knowledge"` and `dry run, nothing written`. The real call prints `wrote <path>\cfg-trust.toml` and `domain extra now gives knowledge alone. A project already installed keeps the skills written for it until the next vyd install --project, which removes them`, and the next line reads `trust = "knowledge"`. The repeat prints `domain extra already has trust knowledge, so nothing is written` and exits 0. The raise to `own` from a pipe exits 1 with `vyd: trust own gives the domain's rules, skills and recipes to every project that uses it. A person must run this command, in a terminal`, and the dry run of the same raise prints a diff back to `trust = "own"` and ends `dry run, nothing written. trust own gives the domain's rules, skills and recipes to every project that uses it, so a person must run it for real, in a terminal`. `reviewed` with no `--commit` exits 1 with `vyd: trust reviewed needs --commit, the commit you read. Name it yourself, since it is the record of what you reviewed`. A short commit exits 1 with `vyd: --commit 'abc' is not a commit of 7 to 64 hexadecimal characters`. A well-formed commit from a pipe exits 1 with `vyd: trust reviewed at 0123456789abcdef gives the domain's rules, skills and recipes to every project that uses it. A person must run this command, in a terminal`. Nothing is written by a refusal.

**Failure.** A raise written from a pipe, or a traceback.

#### W4.12 Raise the trust at a real console

Run this directly in the console, not through `Step`, so that standard input is the terminal. It commits the new domain's files, so it has a commit to name, and it raises the trust first to `reviewed` at that commit and then to `own`.

```powershell
git -C "$T\dom extra" add -A
git -C "$T\dom extra" -c user.email='wintest@example.invalid' -c user.name='wintest' commit -q -m 'initial'
$h = git -C "$T\dom extra" rev-parse --short HEAD
WithConfig "$T\cfg-trust.toml" {
    vyd domain trust extra reviewed --commit $h
    vyd domain trust extra own
    Select-String -Path $env:VYVID_CONFIG -Pattern '^(trust|commit)' | ForEach-Object { $_.Line }
}
```

**Pass.** There is no prompt. Each call prints `writing <path>\cfg-trust.toml`, a diff, `wrote <path>\cfg-trust.toml` and a line about what the domain now gives. The first changes `trust = "knowledge"` to `trust = "reviewed"` and adds `commit = "<hash>"`, and ends `domain extra now gives what own does while its folder is at commit <hash>, and knowledge alone at any other.` followed by a hint to run `vyd install --project` and `vyd install --client`, and what to do after a pull. The second removes the `commit` line, sets `trust = "own"` and ends `domain extra now gives its rules, skills and recipes to every project that uses it, so its skills will compose.` followed by the same hint. The last line reads `trust = "own"`. Mark it yourself with `Mark W4.12 PASS` after reading the output.

**Failure.** `A person must run this command, in a terminal` from a real console goes into the comment with the host you used (Windows Terminal, the console host, an editor's terminal), as for W6.4.

## W5 The index

Needs W4.8. Everything here uses the scratch store and the scratch model cache. Whether `find` can rank depends on the model download in W5.3.

#### W5.1 Create the project repository

The project is a small repository with one register, a contract and a Python file. A register `rules.md` is also copied into the `demo` domain, with a family for it, so that W10.5 can check a move.

```powershell
Step W5.1 {
    New-Item -ItemType Directory -Force -Path "$Code\docs", "$Code\src" | Out-Null
    Write-Utf8 "$Code\AGENTS.md" "# Agent contract`n`nAsk the index first.`n"
    $rules = @"
# Rules

**Unit type:** Register

| ID | Name | Claim | Problem shape | Phase |
|---|---|---|---|---|
| RULE-1 | explicit encoding | **Read text with an explicit encoding.** | a bare read decodes with the console code page | development |
| RULE-2 | forward slashes | **Store a path with forward slashes.** | a backslash in a stored identifier | development |
"@
    Write-Utf8 "$Code\docs\rules.md" $rules
    Write-Utf8 "$Code\src\greet.py" @'
"""A module that greets."""


def greet(name: str) -> str:
    """Return a greeting for name."""
    return "hello " + name
'@
    Write-Utf8 "$Dom\rules.md" $rules
    $dt = [IO.File]::ReadAllText("$Dom\domain.toml")
    Write-Utf8 "$Dom\domain.toml" ($dt.Replace('[families]', "[families]`nRULE = { defined = `"rules.md`", type = `"standard`" }"))
    git -C $Code init -q -b main
    git -C $Code config user.email 'wintest@example.invalid'
    git -C $Code config user.name 'wintest'
    git -C $Code add -A
    git -C $Code commit -q -m 'initial'
    'commit ' + (git -C $Code rev-parse --short HEAD)
    Get-Content "$Dom\domain.toml" | Select-Object -First 12
}
```

**Pass.** A short commit id, possibly with `LF will be replaced by CRLF` warnings from git when `core.autocrlf` is true, and the first lines of `domain.toml` with the `RULE = ...` line under `[families]`.

#### W5.2 Bind the project in the scratch configuration

```powershell
$dl = @('demo')
foreach ($d in 'tools', 'lifecycle') { if (Test-Path "$T\kb\domains\$d\domain.toml") { $dl += $d } }
$domList = ($dl | ForEach-Object { '"' + $_ + '"' }) -join ', '
$sha = git -C $Code rev-parse --short HEAD
Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "example-service"
visibility = "public"
code = '$Code'
docs = "code:docs"
contract = ["code:AGENTS.md"]
domains = [$domList]
skill_prefix = "ex-"
skill_values = { ask = "vyd find" }
skill_targets = [".claude/skills", ".github/skills"]
hook_clients = ["claude-code", "copilot", "codex"]

[projects.families]
RULE = { defined = "docs:rules.md", type = "standard" }

[[projects.symbols]]
language = "python"
paths = ["code:src/**/*.py"]

[[projects.moves]]
family = "RULE"
to = "demo"
source = "code:docs/rules.md"
commit = "$sha"
"@
Step W5.2 { vyd config $Code }
```

**Pass.** `projects: example-service` and the domain list, with no note about a missing folder for a domain you cloned. A project declared in this file needs no `vyd trust`, which is why the later sections use it. W6 tests trust on a project declared by a `vyvid.toml`.

#### W5.3 Build the index

The first build downloads the embedding model into `%TEMP%\vyd-wintest\model`, a file on the order of a hundred megabytes. Wait for it.

```powershell
Step W5.3 { vyd build $Code }
```

**Pass.** A table of counts ending with `knowledge index built at <test folder>\store\store`, and counts such as `embedded` greater than zero. `NOTE:` lines about register columns are fine. One line reads `NOTE: 2 entries of 'example-service' moved to 'demo', which answers for them, so the copies in 'example-service' are not indexed`.

**If the download is refused.** The build still finishes, with `NOTE: no embeddings, so nothing can be ranked by meaning: could not fetch <address>: <reason>` and the same for symbols. Mark NOTE with the reason. Then `vyd find` prints `find cannot rank here: no vectors.npz in <store>. Run vyd build, which says why`, and the steps below say which of them still work. Do not retry the build more than once.

#### W5.4 Ask a question

```powershell
Step W5.4 { vyd find read text with an explicit encoding --no-log }
```

**Pass.** A table whose first row is `demo:RULE-1`, kind `Standard`, a score near 0.8, and the pointer `rules.md:7-7` with a forward slash. Without the model: the `cannot rank here` message, which is the expected result and not a failure.

**Failure.** A backslash in a pointer, or a pointer with a drive letter, goes into the comment.

#### W5.5 Filters

```powershell
Step W5.5 {
    vyd find explicit encoding --kind standard --phase development --limit 3 --no-log
    vyd find read text explicit encoding --kind note --limit 2 --no-log
    vyd find explicit encoding --exclude question --activity coding --limit 2 --no-log
}
```

**Pass.** The first prints `demo:RULE-1`. The second prints `tools:NOTE-10` when tools was cloned, flagged `U` for a domain you have not marked as trusted. The third prints a table or the line `no entry has the facets asked for`. Without the model, each prints the `cannot rank here` message.

#### W5.6 Read, node, exists, reaches and sparql

These work without the model.

```powershell
Step W5.6 {
    vyd read demo:RULE-1 --no-log
    vyd node demo:RULE-1
    vyd exists greet
    vyd reaches demo:RULE-1
    vyd sparql 'SELECT (COUNT(*) AS ?n) WHERE { GRAPH ?g { ?s ?p ?o } }'
}
```

**Pass.** `read` prints the entry's fields and a source line, `node` prints a table row and `1 row(s)`, `exists greet` prints `nothing found for: exists greet` and a line saying it was logged, `reaches` prints edges or `nothing found for: reaches demo:RULE-1`, and `sparql` prints a table with a count above zero and `1 row(s)`.

**Failure.** A traceback, or `node` finding nothing for a row that `find` listed.

#### W5.7 Misses, gaps and closing them

```powershell
Step W5.7 {
    vyd find zzzz qqqq unrelated words
    vyd misses --near
    vyd gap "a case the entry does not cover" demo:RULE-1 docs/rules.md:7
    vyd misses
    vyd close demo:RULE-1
}
```

**Pass.** The question prints a weak-match message (or `cannot rank here`). `misses --near` lists it in a table with a `last`, `times` and `question` column. `gap` prints `gap recorded in <store>\logs\example-service\asks.log` and a reminder to name it at the handoff. `close` prints `closed 1 gap(s) on demo:RULE-1, and removed N related log line(s)`.

#### W5.8 The logs folder and its permissions

```powershell
Step W5.8 {
    Get-ChildItem "$T\store\logs" -Recurse -File | Select-Object FullName, Length | Format-Table -AutoSize | Out-String
    icacls "$T\store\logs"
    icacls "$T\store"
}
```

**Pass.** A `logs\example-service` folder with `asks.log` and `misses.log`. `vyd` asks for owner-only folders with `chmod`, which does little on Windows, so expect the access list to be inherited from the temporary folder with other accounts or groups on it. Mark NOTE with 'folders not owner-only' if the list shows accounts besides yours, SYSTEM and Administrators.

#### W5.9 `--no-log` writes nothing

```powershell
Step W5.9 {
    function Lines { (Get-ChildItem "$T\store\logs" -Recurse -File | ForEach-Object { (Get-Content $_.FullName).Count } | Measure-Object -Sum).Sum }
    $a = Lines
    vyd find zzzz qqqq other unrelated words --no-log | Out-Null
    $b = Lines
    vyd find zzzz qqqq other unrelated words | Out-Null
    $c = Lines
    "lines before: $a, after a --no-log question: $b, after a logged question: $c"
}
```

**Pass.** The first two numbers are equal and the third is larger.

#### W5.10 A change in a source file rebuilds the index

The register `rules.md` of the project moved to the domain, so the edit is made in the domain's copy.

```powershell
Step W5.10 {
    Add-Utf8 "$Dom\rules.md" "| RULE-3 | late | **Add a row later.** | rows added | development |`n"
    vyd find add a row later --no-log
}
```

**Pass.** The line `knowledge index is missing or older than the files it reads, so building it`, then a table with `demo:RULE-3` first (with the model). Without the model, the build line, a line `vyd: no embeddings, so nothing can be ranked by meaning: could not fetch <address>: <reason>` on standard error, and the `cannot rank here` message.

#### W5.11 Embeddings still work after a rebuild, symbols included

```powershell
Step W5.11 { vyd find greeting for a name --kind symbol --no-log }
```

**Pass.** A row `example-service:greet.greet`, kind `function`, module `greet`, pointer `src/greet.py:4`, with `def greet(name: str) -> str` below. If W2.7 did not install the grammars, the message says the extra is missing and that is a pass for this install.

#### W5.12 A store held open during a rebuild (optional)

On Windows a folder with an open file cannot be deleted. `vyd build` removes the store folder and writes it again. This step holds the store open from another process and builds.

```powershell
Step W5.12 {
    $holder = Start-Process -PassThru -WindowStyle Hidden -FilePath $Py -ArgumentList '-c', "`"import pyoxigraph as ox, time; s = ox.Store.read_only(r'$T\store\store'); time.sleep(45)`""
    Start-Sleep -Seconds 4
    vyd build $Code
    'build exit code ' + $LASTEXITCODE
    Stop-Process -Id $holder.Id -Force
}
```

**Not run anywhere.** If `vyd build` fails with `PermissionError` or `[WinError 32]`, mark FAIL with 'store cannot be rebuilt while a reader holds it', and capture the last lines. If the build passes, mark PASS. Then run `vyd build $Code` once more to leave a good store.

#### W5.13 A heading after an inline code span

A line that starts with an inline code span of four backticks enclosing three used to read as the opening of a code fence, which hid every heading below it, so an anchor to one of them failed. From v0.2.14 a backtick fence's opening line holds no other backtick, and a fence closes only on the same mark, at least as long, with nothing after it. The fence line is built from character codes, so that this file holds no backtick run of its own. The register entry points at the heading `After`, and `vyd family add` declares the register as a family of `example-service`.

```powershell
Step W5.13 {
    $b3 = ([string][char]96) * 3
    $b4 = ([string][char]96) * 4
    Write-Utf8 "$Code\docs\fence.md" ("$b4 ${b3}turtle-example $b4 is illustrative text that opens no fence.`n`n## After`n`nThe section the pointer names.`n")
    Write-Utf8 "$Code\docs\fenced.md" @'
# Fenced

**Unit type:** Register

| ID | Name | Claim | Problem shape | Pointer |
|---|---|---|---|---|
| FENCE-1 | a section after an inline span | **Read a heading after an inline code span.** | an anchor to a heading after a line that starts with a code span | docs/fence.md#after |
'@
    Get-Content "$Code\docs\fence.md" -TotalCount 1
    vyd family add example-service FENCE --defined 'docs:fenced.md' --type standard
    vyd build $Code
    vyd read FENCE-1 --in $Code --no-log
}
```

**Pass.** The first line shows four backticks, then `` ```turtle-example ``, four backticks and the sentence. `vyd family add` prints a diff adding `FENCE = { defined = "docs:fenced.md", type = "standard" }` to `[projects.families]` and `wrote <path>\config.toml`, and the build ends with `knowledge index built at`. It prints no `NOTE` about `FENCE-1` or its pointer. `read` prints `FENCE-1  Standard  Open`, the claim, and below `== pointed-at docs/fence.md:3-5` the lines `## After`, an empty line and `The section the pointer names.`, with a forward slash in the pointer. A `NOTE` about the pointer or `nothing to read for: FENCE-1` is a failure. Seen on macOS, the build counts `Standard` as 5 where W5.3 counted 4.

#### W5.14 The automatic build says why it has no vectors, and retries (optional)

A question that finds the store missing or stale builds it first. From v0.2.14 that build prints, on standard error, the reason it made no embeddings, in a line that begins `vyd: no embeddings`. A store left without vectors is rebuilt by the next question only after a minute, so a failing download costs one build a minute and not one per question. A store built with `vyd build --no-embed` is left as it is. This step makes the model unreachable with a copy of the scratch configuration that has its own empty store and model folders and an address for `HTTPS_PROXY` that refuses connections. It takes about three minutes because of the two waits. Skip it with a NOTE if W5.3 could not download the model, since that already shows the refusal, and mark NOTE with 'model still reachable' if the first question below ranks.

```powershell
Step W5.14 {
    $off = [IO.File]::ReadAllText($env:VYVID_CONFIG).Replace("'$T\store'", "'$T\store-offline'").Replace("'$T\model'", "'$T\model-offline'")
    Write-Utf8 "$T\cfg-offline.toml" $off
    function Ask {
        $all = @(vyd find read text with an explicit encoding --no-log --in $Code 2>&1)
        'standard output: ' + @($all | Where-Object { $_ -isnot [Management.Automation.ErrorRecord] })[0]
        'standard error:'
        $all | Where-Object { $_ -is [Management.Automation.ErrorRecord] } | ForEach-Object { '  ' + $_ }
    }
    $keep = $env:HTTPS_PROXY
    $env:HTTPS_PROXY = 'http://127.0.0.1:9'
    try {
        WithConfig "$T\cfg-offline.toml" {
            '--- the first question'
            Ask
            '--- again at once'
            Ask
            Start-Sleep -Seconds 65
            '--- after 65 seconds'
            Ask
            vyd build $Code --no-embed | Select-Object -Last 2
            Start-Sleep -Seconds 65
            '--- after --no-embed and 65 seconds'
            Ask
        }
    } finally { $env:HTTPS_PROXY = $keep }
}
```

**Pass.** The first question prints `standard output: find cannot rank here: no vectors.npz in <test folder>\store-offline. Run vyd build, which says why`, and under `standard error:` two lines, `knowledge index is missing or older than the files it reads, so building it` and `vyd: no embeddings, so nothing can be ranked by meaning: could not fetch https://huggingface.co/...: <reason>`. The reason is the system's own text, so it differs from the `Connection refused` seen on macOS. The question at once after it prints the same standard output and nothing under `standard error:`. The question after 65 seconds prints the two lines again. The build prints `NOTE: no embeddings, because the build was told not to make them` and `knowledge index built at <test folder>\store-offline\store`, and the question after it and 65 more seconds prints nothing under `standard error:`. A reason that is not on standard error, or a rebuild at once, goes into the comment.

## W6 Project files, trust, links, worktrees and odd paths

Needs W5 and a real console for W6.3 and W6.4. The project here is declared by a `vyvid.toml` in its own repository, so it has to be trusted before it can write or run anything.

#### W6.1 A repository that declares its own project

```powershell
Step W6.1 {
    $RT = Join-Path $T 'work\repo-trust'
    New-Item -ItemType Directory -Force -Path "$RT\docs" | Out-Null
    Write-Utf8 "$RT\vyvid.toml" @"
[project]
name = "trust-demo"
visibility = "public"
docs = "code:docs"
contract = "code:AGENTS.md"
domains = ["demo"]
"@
    Write-Utf8 "$RT\AGENTS.md" "# Agent contract`n`nAsk the index first.`n"
    git -C $RT init -q -b main
    git -C $RT config user.email 'wintest@example.invalid'
    git -C $RT config user.name 'wintest'
    git -C $RT add -A
    git -C $RT commit -q -m 'initial'
    vyd config $RT
    vyd context $RT --no-pull
}
```

**Pass.** `project file: <path>\vyvid.toml` and a line `project trust-demo is declared in <path>\vyvid.toml, which is not trusted, so it gives knowledge alone and runs nothing. A person runs vyd trust in a terminal, in that repository, or lists the repository's origin in trusted_repositories and commits the file`. `vyd context` lists `4. project trust-demo (public)` with `withheld: 1 rule file(s)` and the same reason.

#### W6.2 `vyd trust` refuses input that is not a terminal

```powershell
Step W6.2 { 'yes' | vyd trust (Join-Path $T 'work\repo-trust') }
```

**Not run anywhere.** The code checks that standard input is a terminal before anything else. Expect `vyd: a person must run vyd trust, in a terminal` and exit code 1, with nothing recorded. If it records trust from a pipe, mark FAIL.

#### W6.3 Refuse at the prompt

Run this directly in the console, not through `Step`.

```powershell
vyd trust (Join-Path $T 'work\repo-trust')
```

**Pass.** It prints `<path>\vyvid.toml declares these, which an agent reads or which run with your privileges:` and lists the contract, then asks `Type yes to trust this file as it is now:`. Type `no`. It prints `not trusted` and exits 1. Then `vyd config` still shows the project as not trusted. Mark it yourself.

#### W6.4 Trust it

Run this directly in the console.

```powershell
vyd trust (Join-Path $T 'work\repo-trust')
```

**Pass.** Type `yes`. It prints `trusted <path>\vyvid.toml, until it changes`. A trust record is now written under `%LOCALAPPDATA%\vyvid\vyvid`, outside the test folder, which W15 lists.

**Failure.** A prompt that does not accept input, or `a person must run vyd trust, in a terminal` from a real console, goes into the comment with the host you used (Windows Terminal, the console host, an editor's terminal).

#### W6.5 The two trust lines

```powershell
Step W6.5 { vyd config (Join-Path $T 'work\repo-trust'); vyd context (Join-Path $T 'work\repo-trust') --no-pull }
```

**Pass.** `configuration trust: not trusted ...` for the scratch configuration, and a separate `project trust-demo is declared in <path>\vyvid.toml, which is trusted`. The context now lists the project's contract file, `AGENTS.md`, with no `withheld` line for it.

#### W6.6 A linked worktree shares the trust record

```powershell
Step W6.6 {
    $RT = Join-Path $T 'work\repo-trust'
    git -C $RT worktree add (Join-Path $T 'work\repo-trust-wt') -b trust-wt
    Get-Content -Raw "$RT\vyvid.toml" | ForEach-Object { 'bytes in main: ' + [Text.Encoding]::UTF8.GetByteCount($_) }
    Get-Content -Raw (Join-Path $T 'work\repo-trust-wt\vyvid.toml') | ForEach-Object { 'bytes in worktree: ' + [Text.Encoding]::UTF8.GetByteCount($_) }
    vyd config (Join-Path $T 'work\repo-trust-wt')
}
```

**Pass.** Linked worktrees of one repository share the record when their `vyvid.toml` bytes are the same, so the worktree's line reads `which is trusted`.

**Note.** With `core.autocrlf` true, the worktree's file is checked out with CRLF, and `Get-Content -Raw` does not show the difference. If the worktree line reads `not trusted`, the bytes differ, and the record is keyed by hash. Mark NOTE with 'trust not shared under autocrlf'. To confirm, run `[IO.File]::ReadAllBytes(...).Count` on both files.

#### W6.7 An edit lapses trust, and putting it back restores it

```powershell
Step W6.7 {
    $RT = Join-Path $T 'work\repo-trust'
    Add-Utf8 "$RT\vyvid.toml" "# edited`n"
    vyd config $RT
    git -C $RT checkout -- vyvid.toml
    vyd config $RT
}
```

**Pass.** The first `vyd config` says `not trusted`. After the checkout restores the committed file, the second says `trusted` again if the bytes match what was trusted, and `not trusted` if `core.autocrlf` converted them. Mark which, with the value of `core.autocrlf`.

#### W6.8 A file that is a link

Creating a symbolic link needs Developer Mode or an elevated window. If the creation is refused, mark NOTE with the message.

```powershell
Step W6.8 {
    $L = Join-Path $T 'work\repo-link'
    New-Item -ItemType Directory -Force -Path $L | Out-Null
    Write-Utf8 "$T\work\outside.md" "outside the repository`n"
    Write-Utf8 "$L\vyvid.toml" @"
[project]
name = "link-demo"
visibility = "public"
contract = "code:AGENTS.md"
"@
    git -C $L init -q -b main
    New-Item -ItemType SymbolicLink -Path "$L\AGENTS.md" -Target "$T\work\outside.md"
    vyd config $L
}
```

**Pass.** `set aside: the project declared in <path>\vyvid.toml` followed by `contract names 'code:AGENTS.md', which leaves the repository`. The project is set aside and its contract is never read.

**Failure.** The project is used and the outside file read. Also run `git -C $L config core.symlinks` and add it to the comment, since a clone without link support turns a link into a text file holding its target.

#### W6.9 A path with a space and one with non-ASCII characters

The names are built from character codes so that this file stays ASCII-safe to paste. The second folder is `проєкт-ü` and holds a note named `нотатка.md`.

```powershell
Step W6.9 {
    $uni = (-join [char[]](0x43F, 0x440, 0x43E, 0x454, 0x43A, 0x442)) + '-' + [char]0xFC
    $note = (-join [char[]](0x43D, 0x43E, 0x442, 0x430, 0x442, 0x43A, 0x430)) + '.md'
    $global:Sp = Join-Path $T 'work\proj with space'
    $global:Un = Join-Path $T ('work\' + $uni)
    foreach ($p in $Sp, $Un) {
        Write-Utf8 "$p\docs\rules.md" "# Rules`n`n**Unit type:** Register`n`n| ID | Name | Claim | Problem shape | Phase |`n|---|---|---|---|---|`n| RULE-1 | one | **A rule.** | a shape | development |`n"
        Write-Utf8 "$p\docs\$note" "See RULE-1 in a note.`n"
        Write-Utf8 "$p\README.md" "# Readme`n"
        git -C $p init -q -b main
        git -C $p config user.email 'wintest@example.invalid'
        git -C $p config user.name 'wintest'
        git -C $p add -A
        git -C $p commit -q -m 'initial'
    }
    Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "spaced"
visibility = "public"
code = '$Sp'
docs = "code:docs"
domains = ["demo"]
[projects.families]
RULE = { defined = "docs:rules.md", type = "standard" }

[[projects]]
name = "unicode-path"
visibility = "public"
code = '$Un'
docs = "code:docs"
domains = ["demo"]
[projects.families]
RULE = { defined = "docs:rules.md", type = "standard" }
"@
    git -C $Un ls-files
    vyd config $Sp
}
```

**Pass.** The listing shows the three tracked files, the note name possibly quoted with octal escapes if `core.quotePath` is on. `vyd config` ends with `projects: example-service, spaced, unicode-path`. The config file is read as UTF-8, so a non-ASCII `code` path must parse.

#### W6.10 Both paths with UTF-8 mode on

```powershell
Step W6.10 {
    foreach ($p in $Sp, $Un) {
        '== ' + $p
        vyd check identifiers $p
        vyd build $p
    }
}
```

**Pass.** Each `check identifiers` prints `identifier check passed: 1 identifiers mentioned in 3 files, 0 unresolved, 0 defined twice` or the same with other counts, and each build ends with `knowledge index built at`. Note the file counts.

#### W6.11 The same with the default encoding

```powershell
Step W6.11 -Plain {
    foreach ($p in $Sp, $Un) {
        '== ' + $p
        vyd check identifiers $p
    }
}
```

**Pass.** The same counts as W6.10 for each folder. Under the default encoding Python decodes git's output with the ANSI code page, so a non-ASCII folder or file name can come back misread, and the count of files or mentions drops, or a `FileNotFoundError` or garbled name appears. Mark FAIL with the two counts if they differ from W6.10, and capture the output. This is read from the code and has not been run.

#### W6.12 The same folder spelled with different case

```powershell
Step W6.12 {
    $up = $Code.ToUpper()
    vyd config $up
    vyd find explicit encoding --in $up --no-log
    'checkout stores: ' + [bool](Test-Path "$T\store\checkouts")
}
```

**Pass.** `projects:` still includes `example-service`, the same top row as W5.4, no rebuild message, and `checkout stores: False`. A different case is the same folder on Windows. A rebuild, a new folder under `store\checkouts`, or no project found means the path text is used as a key somewhere. Capture the output.

#### W6.13 A linked worktree at a path over 260 characters

```powershell
Step W6.13 {
    $long = Join-Path $T (('a' * 90) + '\' + ('b' * 90) + '\' + ('c' * 60) + '\wt')
    'path length: ' + $long.Length
    git -C $Code -c core.longpaths=true worktree add $long -b long-wt
    vyd config $long
    vyd find explicit encoding --in $long --no-log
}
```

**Pass.** With `LongPathsEnabled = 1` from W1.3, the worktree is created, `vyd config` shows the project, and `find` answers. Without it, a failure from git or Windows naming the path is expected. Mark NOTE with the W1.3 value either way. A failure inside `vyd` with long paths enabled is a FAIL.

#### W6.14 Prune the stores of removed worktrees

```powershell
Step W6.14 {
    git -C $Code worktree remove --force $long 2>&1
    git -C (Join-Path $T 'work\repo-trust') worktree remove --force (Join-Path $T 'work\repo-trust-wt')
    vyd store prune --dry-run
    vyd store prune
}
```

**Pass.** The dry run names each store whose worktree is gone and removes nothing, and `vyd store prune` removes them. `no checkout store is left behind` when there are none. If the long worktree could not be removed, run `cmd /c "rmdir /s /q \\?\$long"` first and note it.

#### W6.15 A command extractor that outlives its time limit (optional)

A command extractor is stopped at its time limit, and on POSIX its children go with it through a process group. On Windows only the direct child is stopped. This needs the scratch configuration trusted, which is a prompt, and it is the least certain step in this file.

```powershell
Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "slow-extractor"
visibility = "public"
code = '$Code'
docs = "code:docs"
domains = ["demo"]

[[projects.extractors]]
kind = "slow"
command = ["cmd", "/c", "ping -n 60 127.0.0.1 > nul"]
paths = ["docs:rules.md"]
seconds = 3
"@
```

Run `vyd trust $env:VYVID_CONFIG` directly in the console and type `yes`. The code checks the entry is allowed before running anything.

```powershell
Step W6.15 {
    vyd build $Code
    Start-Sleep -Seconds 5
    Get-Process -Name ping -ErrorAction SilentlyContinue | Select-Object Id, StartTime
}
```

**Expected from the code.** The build reports the extractor failing at the time limit and goes on. A `ping` process that is still running after the build means the grandchild was not stopped. Mark NOTE with 'grandchild survives the time limit' if so, then `Stop-Process -Name ping`. A second project bound to the same folder may be reported as a duplicate, in which case remove its entry from the configuration and note what the message said.

#### W6.16 A repository named in the user's own configuration is trusted

A checkout whose `origin` is listed in `[framework] trusted_repositories` in the user's own configuration has its `vyvid.toml` trusted without `vyd trust`, for a machine where no one is at a terminal. The list is read from the user's own configuration alone, which is found through the platform's folders. These steps move that folder into the test folder with `WIN_PD_OVERRIDE_LOCAL_APPDATA`, which `platformdirs` reads before it asks Windows, so the real configuration is not written. The variable is set only inside `WithOwn`. Define `WithOwn` once, and again in any new window.

```powershell
function WithOwn {
    param([Parameter(Mandatory)][scriptblock]$Do)
    $keep = $env:WIN_PD_OVERRIDE_LOCAL_APPDATA
    $env:WIN_PD_OVERRIDE_LOCAL_APPDATA = Join-Path $T 'localappdata'
    try { & $Do }
    finally {
        if ($null -eq $keep) { Remove-Item Env:WIN_PD_OVERRIDE_LOCAL_APPDATA -ErrorAction SilentlyContinue }
        else { $env:WIN_PD_OVERRIDE_LOCAL_APPDATA = $keep }
    }
}
```

The repository is a new one with `core.autocrlf` set to false, so its file is stored and checked out with the same bytes whatever the machine's setting. W6.20 covers the setting.

```powershell
Step W6.16 {
    $G = Join-Path $T 'work\repo-grant'
    New-Item -ItemType Directory -Force -Path $G | Out-Null
    Write-Utf8 "$G\vyvid.toml" @"
[project]
name = "grant-demo"
visibility = "public"
docs = "code:docs"
contract = "code:AGENTS.md"
domains = ["demo"]
"@
    Write-Utf8 "$G\AGENTS.md" "# Agent contract`n`nAsk the index first.`n"
    git -C $G init -q -b main
    git -C $G config user.email 'wintest@example.invalid'
    git -C $G config user.name 'wintest'
    git -C $G config core.autocrlf false
    git -C $G remote add origin https://example.invalid/team/grant-demo.git
    git -C $G add -A
    git -C $G commit -q -m 'initial'
    WithOwn {
        $first = @(WithConfig $null { vyd config })[0]
        $first
        $global:Own = ($first -replace '^configuration: ', '') -replace ' \(absent.*$', ''
        if (-not $global:Own.StartsWith($T)) { 'WIN_PD_OVERRIDE_LOCAL_APPDATA did not move the configuration, so nothing is written. Mark NOTE with the line above'; return }
        'before the list:'
        vyd config $G | Where-Object { $_ -like 'project grant-demo is declared*' }
        Write-Utf8 $global:Own "[framework]`ntrusted_repositories = [`"example.invalid/team/grant-demo`"]`n"
        'after the list:'
        vyd config $G | Where-Object { $_ -like 'project grant-demo is declared*' }
    }
}
```

**Pass.** The first line reads `configuration: <test folder>\localappdata\vyvid\vyvid\config.toml (absent, so the general scope alone)`, which shows the override worked. Before the list, the project line reads `project grant-demo is declared in <path>\vyvid.toml, which is not trusted, so it gives knowledge alone and runs nothing. A person runs vyd trust in a terminal, in that repository, or lists the repository's origin in trusted_repositories and commits the file`. After it, the line ends `which is trusted through trusted_repositories, as it is committed at HEAD`. Nothing is written to `%LOCALAPPDATA%`. On Windows the override is read from the `platformdirs` code and has not been run, so a line outside the test folder means the installed `platformdirs` does not read it, and the step then wrote nothing.

#### W6.17 An uncommitted edit lapses the grant, and committing restores it

```powershell
Step W6.17 {
    $G = Join-Path $T 'work\repo-grant'
    WithOwn {
        Add-Utf8 "$G\vyvid.toml" "# edited`n"
        'uncommitted edit:'
        vyd config $G | Where-Object { $_ -like 'project grant-demo is declared*' }
        git -C $G commit -q -a -m 'edit'
        'committed:'
        vyd config $G | Where-Object { $_ -like 'project grant-demo is declared*' }
    }
}
```

**Pass.** After the uncommitted edit the line reads `which is not trusted, so it gives knowledge alone and runs nothing. A person runs vyd trust in a terminal, in that repository, or lists the repository's origin in trusted_repositories and commits the file`, and after the commit it reads `which is trusted through trusted_repositories, as it is committed at HEAD`.

#### W6.18 A fork whose `upstream` alone is listed is not trusted

Only `origin` counts. A fork's `origin` is the fork and its `upstream` is the repository it came from, so a listed `upstream` grants nothing. The clone is made with `core.autocrlf` false, so only the remote names differ from W6.17.

```powershell
Step W6.18 {
    $G = Join-Path $T 'work\repo-grant'
    $F = Join-Path $T 'work\repo-fork'
    git clone -q -c core.autocrlf=false $G $F
    git -C $F remote rename origin upstream
    git -C $F remote set-url upstream https://example.invalid/team/grant-demo.git
    git -C $F remote add origin https://example.invalid/me/grant-demo.git
    git -C $F remote -v
    WithOwn { vyd config $F | Where-Object { $_ -like 'project grant-demo is declared*' } }
}
```

**Pass.** `git remote -v` shows `origin` at `https://example.invalid/me/grant-demo.git` and `upstream` at the listed address, and the project line reads `which is not trusted` with the same ending as in W6.17.

#### W6.19 A file named by `VYVID_CONFIG` does not grant

The list in a configuration that `VYVID_CONFIG` names is ignored, and `vyd config` says so. This step moves the user's own configuration away for its length and puts it back.

```powershell
Step W6.19 {
    $G = Join-Path $T 'work\repo-grant'
    $list = [IO.File]::ReadAllText($env:VYVID_CONFIG).Replace('glue = "stop"', 'glue = "stop"' + "`n" + 'trusted_repositories = ["example.invalid/team/grant-demo"]')
    Write-Utf8 "$T\cfg-list.toml" $list
    WithOwn {
        if (-not $global:Own -or -not (Test-Path $global:Own)) { 'W6.16 did not write the user''s own configuration, so this step has nothing to move'; return }
        Move-Item $global:Own "$T\own-config.keep"
        WithConfig "$T\cfg-list.toml" { vyd config $G | Where-Object { $_ -notlike 'configuration*' -and $_ -notlike 'domains:*' -and $_ -notlike 'projects:*' } }
        Move-Item "$T\own-config.keep" $global:Own
    }
}
```

**Pass.** Four lines. `trusted repositories: example.invalid/team/grant-demo`, then `NOTE: trusted_repositories is ignored here, since only the user's own configuration at <test folder>\localappdata\vyvid\vyvid\config.toml may grant it`, then `project file: <path>\vyvid.toml`, then the project line reading `which is not trusted` with the same ending as in W6.17.

#### W6.20 The grant under `core.autocrlf`

The grant holds only where what git would store for the file is the blob committed at `HEAD`. Git for Windows is often set to `core.autocrlf=true`, which checks a text file out with CRLF line endings. Since v0.2.15 `vyd` compares `git hash-object --path` of the file with `git rev-parse HEAD:vyvid.toml`, which applies the same conversion git does, so such a checkout is granted. This step clones the repository with the setting on and records what `vyd` says.

```powershell
Step W6.20 {
    $G = Join-Path $T 'work\repo-grant'
    $C = Join-Path $T 'work\repo-crlf'
    git clone -q -c core.autocrlf=true $G $C
    git -C $C remote set-url origin https://example.invalid/team/grant-demo.git
    'core.autocrlf in the clone: ' + (git -C $C config core.autocrlf)
    'bytes committed: ' + (git -C $C cat-file -s HEAD:vyvid.toml)
    'bytes checked out: ' + (Get-Item "$C\vyvid.toml").Length
    'carriage returns checked out: ' + ([IO.File]::ReadAllBytes("$C\vyvid.toml") | Where-Object { $_ -eq 13 }).Count
    git -C $C ls-files --eol vyvid.toml
    'git status: [' + ((git -C $C status --short) -join ' ') + ']'
    WithOwn { vyd config $C | Where-Object { $_ -like 'project grant-demo is declared*' } }
}
```

**Pass or note.** Seen on macOS with `core.autocrlf=true`, the committed size is 127 bytes and the checked-out size 134, with 7 carriage returns, `ls-files --eol` shows `i/lf    w/crlf`, `git status` is empty, and the project line reads `trusted through trusted_repositories`. If it reads `which is not trusted` here, mark FAIL with the values above and what `core.autocrlf` was in W1.2. An edit to the file must still lapse the grant, and so must one hidden with `git update-index --assume-unchanged`.

## W7 Skills

Needs W5. The project is `example-service`, bound in the scratch configuration, so no trust prompt is involved. The same commands for a project declared by `vyvid.toml` refuse until it is trusted, as W6 showed.

#### W7.1 Dry run

```powershell
Step W7.1 { vyd install --project --dry-run --in $Code }
```

**Pass.** Five lines `would write <path>` for `.claude\skills\ex-demo\SKILL.md`, `.github\skills\ex-demo\SKILL.md`, `.claude\settings.json`, `.codex\hooks.json` and `.github\hooks\vyvid.json`, exit code 0, and no file created. Knowledge domains give no skill, and a note says so for each, ending with the command a person runs to raise the domain's trust. The composed skills are named with the `ex-` prefix.

#### W7.2 Write them

```powershell
Step W7.2 { vyd install --project --in $Code; Get-ChildItem $Code -Recurse -File -Name | Where-Object { $_ -match 'skills|hooks|settings' } }
```

**Pass.** `wrote <path>` for the same five files, exit code 0, and the listing.

#### W7.3 Check

```powershell
Step W7.3 { vyd check skills $Code }
```

**Pass.** `skills check passed: 1 composed, 0 problem(s)`, exit code 0.

#### W7.4 The files use LF

```powershell
Step W7.4 {
    foreach ($f in '.claude\skills\ex-demo\SKILL.md', '.claude\settings.json', '.github\hooks\vyvid.json') {
        $b = [IO.File]::ReadAllBytes("$Code\$f")
        '{0}: {1} bytes, {2} carriage returns, first byte {3}' -f $f, $b.Length, ($b | Where-Object { $_ -eq 13 }).Count, $b[0]
    }
}
```

**Pass.** Zero carriage returns in each, and a first byte that is not 239 (a byte order mark). The first byte of the skill is 45, of the JSON files 123.

#### W7.5 Drift after a hand edit

```powershell
Step W7.5 {
    Add-Utf8 "$Code\.claude\skills\ex-demo\SKILL.md" "hand edit`n"
    vyd check skills $Code
}
```

**Pass.** Two `ERROR: ... SKILL.md differs from what its sources compose to. Run vyd install --project` lines, `skills check failed: 1 composed, 2 problem(s)`, exit code 1. Both skill targets are reported on macOS after editing only one, so report what you see.

#### W7.6 Repair, then exit code 2

```powershell
Step W7.6 {
    vyd install --project --in $Code
    vyd check skills $Code
    'repaired exit code ' + $LASTEXITCODE
    vyd check skills "$T\kb"
    'no project exit code ' + $LASTEXITCODE
}
```

**Pass.** The check passes with exit code 0 after the install rewrites its own file. The second check prints `vyd: no project claims <folder>, so there are no skills to check` and exits 2, which is the exit code for a check that did not run.

Commit the skills so the next step has something to clone.

```powershell
Step W7.6b { git -C $Code add -A; git -C $Code commit -q -m 'composed skills'; git -C $Code log --oneline }
```

#### W7.7 A clone with CRLF conversion

This is the likely real defect: a committed skill checked out with `core.autocrlf=true` has CRLF line endings, and the check must still pass.

```powershell
Step W7.7 {
    $C = Join-Path $T 'work\example-service-crlf'
    git -c core.autocrlf=true clone -q $Code $C
    $b = [IO.File]::ReadAllBytes("$C\.claude\skills\ex-demo\SKILL.md")
    'carriage returns in the clone: ' + ($b | Where-Object { $_ -eq 13 }).Count
    $cfg = [IO.File]::ReadAllText($env:VYVID_CONFIG)
    Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "crlf-clone"
visibility = "public"
code = '$C'
docs = "code:docs"
domains = ["demo"]
skill_prefix = "ex-"
skill_values = { ask = "vyd find" }
skill_targets = [".claude/skills", ".github/skills"]
"@
    vyd check skills $C
    'exit code ' + $LASTEXITCODE
}
```

**Expected on macOS.** A non-zero count of carriage returns in the clone, and `skills check passed: 1 composed, 0 problem(s)`, exit code 0, because the files are read with their line endings normalised. If it reports a skill as differing, mark FAIL with 'composed skill differs under CRLF', since every Windows contributor with `core.autocrlf` true would hit it.

Also convert the original in place and check again.

```powershell
Step W7.7b {
    $p = "$Code\.claude\skills\ex-demo\SKILL.md"
    Write-Utf8 $p ([IO.File]::ReadAllText($p)) -Crlf
    vyd check skills $Code
    git -C $Code checkout -- .claude/skills
}
```

**Pass.** The check passes with the file in CRLF, and the checkout restores it.

## W8 The reminder hook

Needs W7 for the registered files. `vyd-hook` reads one JSON call on standard input, keeps a small file per session in the folder named by `VYVID_HOOK_STATE`, and prints a reminder when a search runs before any question to the index. It never refuses, and any failure inside it prints `{}` and exits 0.

#### W8.1 A PowerShell search

```powershell
Step W8.1 {
    $j = '{"session_id":"w81","tool_name":"PowerShell","tool_input":{"command":"Select-String -Path *.md -Pattern foo"}}'
    $j | vyd-hook
}
```

**Pass.** One line of JSON starting `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "additionalContext": "Before making any decision, ALWAYS check if the index can answer first.` and ending with the sentence about misses. Exit code 0.

#### W8.2 A search, a question, and a search again

```powershell
Step W8.2 {
    $call = { param($s, $c) '{"session_id":"' + $s + '","tool_name":"PowerShell","tool_input":{"command":"' + $c + '"}}' }
    'search with findstr:'; (& $call 'w82' 'findstr /s foo *.md') | vyd-hook
    'question:'; (& $call 'w82' 'vyd find windows paths') | vyd-hook
    'search with Get-ChildItem after the question:'; (& $call 'w82' 'Get-ChildItem -Recurse') | vyd-hook
    'a copilot call:'; '{"sessionId":"w82c","toolName":"powershell","toolArgs":"{\"command\":\"gci -Recurse\"}"}' | vyd-hook --client copilot
    'state files:'; Get-ChildItem $env:VYVID_HOOK_STATE -Name
}
```

**Pass.** The `findstr` search prints the reminder. The question prints `{}`. The `Get-ChildItem` search after it prints `{}` too, since the hook stays quiet until fifteen further searches have passed. The Copilot call prints `{"additionalContext": "..."}` with no `hookSpecificOutput`. The state folder lists `w81`, `w82` and `w82c`.

#### W8.3 It never refuses

```powershell
Step W8.3 {
    foreach ($in in 'not json', '', '{"tool_name":"Read","tool_input":{}}', '{"tool_name":"PowerShell","tool_input":"nope"}', '[1,2]') {
        'input [' + $in + ']'
        $in | vyd-hook
        'exit ' + $LASTEXITCODE
    }
    'bad option:'; '' | vyd-hook --client nonsense
    'exit ' + $LASTEXITCODE
}
```

**Pass.** Every input prints `{}` and `exit 0`, including the bad option, which `argparse` rejects with a usage message on standard error before the hook prints `{}`. A traceback or a non-zero exit is a FAIL, since a client may then deny the tool.

#### W8.4 The state folder when none is set

`os.getuid` does not exist on Windows, so the folder is named from a fixed word.

```powershell
Step W8.4 {
    $keep = $env:VYVID_HOOK_STATE
    Remove-Item Env:VYVID_HOOK_STATE
    '{"session_id":"w84","tool_name":"PowerShell","tool_input":{"command":"Select-String foo *.md"}}' | vyd-hook | Out-Null
    Get-ChildItem ([IO.Path]::GetTempPath()) -Directory -Filter 'vyvid-hook-*' | Select-Object Name, FullName
    $env:VYVID_HOOK_STATE = $keep
}
```

**Pass.** A folder `vyvid-hook-user` in the temporary folder with the file `w84`. This is outside the test folder, and W15 removes it.

#### W8.5 What install registered

```powershell
Step W8.5 {
    Get-Content "$Code\.claude\settings.json"
    Get-Content "$Code\.github\hooks\vyvid.json"
    Get-Content "$Code\.codex\hooks.json"
}
```

**Pass.** Three JSON files. Claude Code has one `PreToolUse` entry, matcher `Bash|PowerShell|Grep|Glob`, whose command is `command -v vyd-hook >/dev/null 2>&1 && vyd-hook --client claude-code --ask 'vyd find' || echo '{}'`. Copilot has a `postToolUse` entry with a `bash` form like that and a `powershell` form, `if (Get-Command vyd-hook -ErrorAction SilentlyContinue) { vyd-hook --client copilot --ask 'vyd find' } else { '{}' }`. Codex has a `command` and a `commandWindows`.

**Note.** The Claude Code entry has no Windows form. Whether it works depends on the shell Claude Code uses for hooks, which the next steps and W8.9 test.

#### W8.6 The registered Claude Code command in Git Bash

```powershell
Step W8.6 {
    $s = Get-Content -Raw "$Code\.claude\settings.json" | ConvertFrom-Json
    $cmd = $s.hooks.PreToolUse[0].hooks[0].command
    $bash = Join-Path (Split-Path (Split-Path (Get-Command git).Source)) 'bin\bash.exe'
    if (-not (Test-Path $bash)) { $g = Get-Command bash -ErrorAction SilentlyContinue; if ($g) { $bash = $g.Source } }
    'bash: ' + $bash + ' exists: ' + (Test-Path $bash)
    '{"session_id":"w86","tool_name":"Bash","tool_input":{"command":"grep -r foo ."}}' | & $bash -c $cmd
    'exit ' + $LASTEXITCODE
}
```

**Pass.** The reminder JSON of W8.1 with `--client claude-code`, exit 0. That shows the command works in Git Bash and that `vyd-hook` is found on the path it inherits.

**Failure.** `{}` for a search means `command -v vyd-hook` found nothing, so the hook is silently inactive. Capture `& $bash -c 'echo $PATH'` after removing anything private from it.

#### W8.7 The same command under PowerShell

Claude Code can run a hook command with PowerShell. This shows what the POSIX line does there.

```powershell
Step W8.7 {
    $s = Get-Content -Raw "$Code\.claude\settings.json" | ConvertFrom-Json
    $cmd = $s.hooks.PreToolUse[0].hooks[0].command
    $j = '{"session_id":"w87","tool_name":"PowerShell","tool_input":{"command":"Select-String foo *.md"}}'
    foreach ($exe in 'powershell.exe', 'pwsh.exe') {
        if (Get-Command $exe -ErrorAction SilentlyContinue) { "== $exe"; $j | & $exe -NoProfile -Command $cmd; 'exit ' + $LASTEXITCODE }
    }
}
```

**Not run anywhere.** Expected from the syntax. Windows PowerShell 5.1 fails to parse `&&` and `/dev/null`. PowerShell 7 parses it, fails at `command` and `/dev/null`, and prints `{}` from the fallback branch, so the hook does nothing. Either way no reminder reaches the agent. Mark NOTE with the output and 'the Claude Code hook command has no PowerShell form'. A reminder here would be a PASS.

#### W8.8 The Copilot PowerShell form and its bash form

```powershell
Step W8.8 {
    $c = Get-Content -Raw "$Code\.github\hooks\vyvid.json" | ConvertFrom-Json
    $ps = $c.hooks.postToolUse[0].powershell
    $sh = $c.hooks.postToolUse[0].bash
    $j = '{"sessionId":"w88","toolName":"powershell","toolArgs":"{\"command\":\"gci -Recurse\"}"}'
    '== powershell form in powershell.exe'; $j | & powershell.exe -NoProfile -Command $ps; 'exit ' + $LASTEXITCODE
    $bash = Join-Path (Split-Path (Split-Path (Get-Command git).Source)) 'bin\bash.exe'
    if (Test-Path $bash) { '== bash form in Git Bash'; $j.Replace('w88', 'w88b') | & $bash -c $sh; 'exit ' + $LASTEXITCODE }
}
```

**Pass.** Each prints `{"additionalContext": "Before making any decision ...`. The `commandWindows` of `.codex\hooks.json` is the same PowerShell text with `--client codex` and has not been run.

#### W8.9 A real Claude Code session (optional)

Needs Claude Code. Start it from this same window so it inherits `VYVID_HOOK_STATE`, in the project folder.

```powershell
Set-Location $Code
claude
```

Trust the folder when asked, so project hooks load. Run `/hooks` and look for the entry for `Bash|PowerShell|Grep|Glob`. Then ask `Search the repository for the word greet with PowerShell Select-String, then tell me whether you received any reminder about the index and quote it.`

**Pass.** The agent quotes the reminder, and `Get-ChildItem $env:VYVID_HOOK_STATE -Name` shows a new file named for the session. **Failure.** No reminder and no new file means the command was not run or `vyd-hook` was not found. Capture what `/hooks` shows and any hook error Claude prints, and compare with W8.6 and W8.7.

#### W8.10 A real Copilot session in VS Code (optional)

Needs VS Code with Copilot agent mode and hooks enabled. Open `$Code` as a folder, trust it, start an agent session and ask the same question. The Copilot reminder follows the search rather than preceding it. A pass is the agent quoting the reminder after its search. Record the VS Code and extension versions.

## W9 The work board

Needs W5 and git. The board reads status records at the tip of every local and remote branch. A bare repository in the test folder plays the remote, so nothing leaves the machine. All output that names a worktree path shows the test folder, which you may need to redact.

#### W9.1 A repository with a status record, a plan, an index and a roadmap

```powershell
Step W9.1 {
    $Remote = Join-Path $T 'remote.git'
    git init -q --bare -b main $Remote
    New-Item -ItemType Directory -Force -Path "$BoardRepo\docs\status", "$BoardRepo\docs\plans" | Out-Null
    Write-Utf8 "$BoardRepo\docs\status\unit-a.md" @"
# Status: unit-a

**Status:** built 2026-11-03

## Board

| Slice | Deliverable | State | Blocked on |
|---|---|---|---|
| UA-1 | first thing | built 2026-11-03, building 2026-11-02 | |
| UA-2 | second thing | planned | UA-1 |
"@
    Write-Utf8 "$BoardRepo\docs\plans\unit-a.md" "# Plan: unit-a`n`n**Unit type:** Unit`n"
    Write-Utf8 "$BoardRepo\docs\INDEX.md" @'
# Index

<!-- BEGIN GENERATED work-board. Written by `vyd work build` from the status records. Edit a status record, never this region. -->
<!-- END GENERATED work-board -->
'@
    Write-Utf8 "$BoardRepo\docs\ROADMAP.md" "# Roadmap`n"
    git -C $BoardRepo init -q -b main
    git -C $BoardRepo config user.email 'wintest@example.invalid'
    git -C $BoardRepo config user.name 'wintest'
    git -C $BoardRepo remote add origin $Remote
    git -C $BoardRepo add -A
    git -C $BoardRepo commit -q -m 'initial'
    git -C $BoardRepo push -q origin main
    git -C $BoardRepo log --oneline
}
Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "boardy"
visibility = "public"
code = '$BoardRepo'
docs = "code:docs"
domains = ["demo"]
slice_pattern = '[A-Z]{2}-\d+[a-z]?'

[projects.work]
index = "docs:INDEX.md"
roadmap = "docs:ROADMAP.md"
"@
```

**Pass.** One commit listed. A push to a path remote with a drive letter must work, and a failure goes in the comment.

#### W9.2 Build and check the index region

```powershell
Step W9.2 {
    vyd config $BoardRepo
    vyd work check --in $BoardRepo
    'stale check exit ' + $LASTEXITCODE
    vyd work build --in $BoardRepo
    vyd work build --check --in $BoardRepo
    'build check exit ' + $LASTEXITCODE
    vyd work check --in $BoardRepo
    'check exit ' + $LASTEXITCODE
}
```

**Pass.** `vyd config` ends with a `work:` line naming the status, plans, index and roadmap paths, the ladder and the trunk. The first `work check` prints `docs/INDEX.md: the work-board region is stale against the status records. Run vyd work build` and exit 1. After `work build` both checks print nothing and exit 0. The path in the message uses a forward slash.

#### W9.3 Commit the region and read the board

```powershell
Step W9.3 {
    git -C $BoardRepo add -A
    git -C $BoardRepo commit -q -m 'board'
    git -C $BoardRepo push -q origin main
    vyd board $BoardRepo
}
```

**Pass.** `# Work board, 1 branches`, then `## Units`, `## Work` and `## Branches` tables. With every row unchanged from the trunk, the tables are empty, which is how `board` hides what does not differ. `vyd board $BoardRepo --all` lists `UA-1` and `UA-2`.

#### W9.4 A pushed branch and a local-only branch

The local-only branch name must not appear in the roadmap, because the roadmap is committed and reads only what a remote knows.

```powershell
Step W9.4 {
    $f = "$BoardRepo\docs\status\unit-a.md"
    git -C $BoardRepo checkout -q -b feature/pushed-one
    Write-Utf8 $f ([IO.File]::ReadAllText($f).Replace('| second thing | planned |', '| second thing | building 2026-11-05 |'))
    git -C $BoardRepo commit -q -am 'start ua-2'
    git -C $BoardRepo push -q -u origin feature/pushed-one
    git -C $BoardRepo checkout -q -b local-only-branch
    vyd board $BoardRepo --fetch
    vyd work roadmap --fetch --in $BoardRepo
    'roadmap check exit ' + (& { vyd work roadmap --check --in $BoardRepo | Out-Null; $LASTEXITCODE })
    'mentions of the local-only branch: ' + @(Select-String -Path "$BoardRepo\docs\ROADMAP.md" -Pattern 'local-only-branch').Count
    'mentions of the pushed branch: ' + @(Select-String -Path "$BoardRepo\docs\ROADMAP.md" -Pattern 'feature/pushed-one').Count
    git -C $BoardRepo checkout -q -- docs/ROADMAP.md
    git -C $BoardRepo checkout -q main
}
```

**Pass.** `vyd board --fetch` lists both branches, the local-only one with `local only` in its `Upstream` column. The roadmap run exits 0 and `--check` after it exits 0. The count for the local-only branch is 0 and for the pushed branch 2 or more, in a `Moved on` column. The branch-name count for the local-only branch above 0 is a FAIL, because it would be committed.

#### W9.5 Presence

```powershell
Step W9.5 {
    $env:VYD_SESSION_ID = 'wintest-1'
    $env:VYD_CLIENT = 'manual'
    vyd here --in $BoardRepo
    vyd here --in $BoardRepo --role build --on UA-2
    vyd here --in $BoardRepo
    Get-ChildItem "$BoardRepo\.git\vyd" -Recurse -File -Name
    vyd here --in $BoardRepo --leave
    Remove-Item Env:VYD_SESSION_ID, Env:VYD_CLIENT
}
```

**Pass.** The first call prints `nobody here. Run vyd here --role build|review|read --model <model> before your first edit.` The second and third print a table with a `you` row for session `wintest-1`, role `build`, on `UA-2`. A file for the session appears under the repository's git folder. `--leave` prints `left`. If `CLAUDE_CODE_SESSION_ID` or `AGENT_SESSION_ID` is set in this window it takes precedence over `VYD_SESSION_ID`, and the session shown is that one.

#### W9.6 Parse, rename and normalise report without writing

```powershell
Step W9.6 {
    git -C $BoardRepo status --short
    vyd work parse "$BoardRepo\docs\status\unit-a.md"
    vyd work rename --in $BoardRepo
    vyd work normalise --in $BoardRepo
    git -C $BoardRepo status --short
}
```

**Pass.** `work parse` prints a table of the slices. `rename` prints `crosswalk: 0 ids over 0 units this run`, `mentions: 0 files would change` and a validation packs line. `normalise` prints `records and plans: N would change`. The two `git status` outputs are identical, and empty on a clean checkout, because neither command writes without `--apply`.

#### W9.7 Adopt reports too

```powershell
Step W9.7 { vyd work adopt --in $BoardRepo; git -C $BoardRepo status --short }
```

**Pass.** A report and no change in `git status`.

#### W9.8 A git hook that runs `vyd work check --staged`

The hook is written without a byte order mark and with LF, since a byte order mark or a carriage return in the first line stops `sh` finding the interpreter. Git for Windows runs hooks with its own `sh`, which needs `vyd` on the path it inherits.

```powershell
Step W9.8 {
    Write-Utf8 "$BoardRepo\.git\hooks\pre-commit" "#!/bin/sh`nexec vyd work check --staged`n"
    $b = [IO.File]::ReadAllBytes("$BoardRepo\.git\hooks\pre-commit")
    'first bytes: ' + ($b[0..2] -join ' ')
    $f = "$BoardRepo\docs\status\unit-a.md"
    Write-Utf8 $f ([IO.File]::ReadAllText($f).Replace('**Status:** built 2026-11-03', '**Status:** verified 2026-11-05'))
    git -C $BoardRepo add docs/status/unit-a.md
    git -C $BoardRepo commit -m 'should be refused'
    'commit exit ' + $LASTEXITCODE
    'commits on main: ' + (git -C $BoardRepo rev-list --count HEAD)
}
```

**Pass.** First bytes `35 33 47` (`#!/`). The commit is refused with `docs/status/unit-a.md: the Status line reads 'verified 2026-11-05', its board rolls up to 'built 2026-11-03'. Run vyd work normalise --apply`, probably a second line about the stale region of `docs/INDEX.md`, and exit 1. The count of commits has not changed.

**Failure.** The commit succeeds, which means the hook did not run. Or `vyd: command not found` or an `env: sh\r` error appears. Capture the hook's output and `git -C $BoardRepo config core.hooksPath`.

#### W9.9 A partial commit with an unstaged bad record

```powershell
Step W9.9 {
    git -C $BoardRepo restore --staged docs/status/unit-a.md
    Write-Utf8 "$BoardRepo\other.txt" "other`n"
    git -C $BoardRepo add other.txt
    git -C $BoardRepo commit -m 'partial'
    'commit exit ' + $LASTEXITCODE
    git -C $BoardRepo status --short
    git -C $BoardRepo restore docs/status/unit-a.md
}
```

**Pass.** The commit succeeds, exit 0, because `--staged` only looks at staged status records, and `git status` still shows the unstaged edit before it is restored.

#### W9.10 A commit from a linked worktree

In a linked worktree git sets `GIT_DIR` to a folder under the main repository for the hook. The check must find the right repository.

```powershell
Step W9.10 {
    $W = Join-Path $T 'work\boardy-wt'
    git -C $BoardRepo worktree add $W -b wt-b
    Write-Utf8 "$W\other2.txt" "other two`n"
    git -C $W add other2.txt
    git -C $W commit -m 'from the worktree'
    'commit exit ' + $LASTEXITCODE
    git -C $W log --oneline -1
}
```

**Pass.** The commit succeeds and the log shows it. A message from `vyd` about a missing project, or a failure to find the status records, is a FAIL. Capture the whole output.

## W10 Other checks

Needs W5 and W7.6b. Path handling is the point of these.

#### W10.1 Identifiers

```powershell
Step W10.1 {
    vyd check identifiers $Code
    Add-Utf8 "$Code\docs\mention.md" "See RULE-1 and RULE-99.`n"
    git -C $Code add docs/mention.md
    vyd check identifiers $Code
    'exit ' + $LASTEXITCODE
    vyd check identifiers $Code --all
    vyd check identifiers $Code --json
}
```

**Pass.** The first run prints `identifier check passed: N identifiers mentioned in M files, 0 unresolved, 0 defined twice`. The second prints `ERROR: RULE-99 (RULE) is mentioned but never defined: docs/mention.md:1` with a forward slash, then `identifier check failed: ...` and exit 1. `--all` adds the variants and stale exceptions. `--json` prints an object whose `unresolved` entry has `"path": "docs/mention.md"`. A backslash in a path of the message or the JSON is a FAIL. The file must be added to git to be read, since only tracked Markdown is checked.

#### W10.2 Citations in a public project

```powershell
Step W10.2 {
    vyd check citations --staged --in $Code
    Write-Utf8 "$T\msg.txt" "A message that cites nothing.`n"
    vyd check citations --message "$T\msg.txt" --in $Code
    git -C $Code rm -q -f --cached docs/mention.md
    Remove-Item "$Code\docs\mention.md"
}
```

**Pass.** Each prints `N line(s) checked, and none cites an entry of a private scope`, exit 0.

#### W10.3 Private documents outside the code repository

```powershell
Step W10.3 {
    $PC = Join-Path $T 'work\pcode'
    $PD = Join-Path $T 'work\pdocs'
    foreach ($p in $PC, $PD) {
        New-Item -ItemType Directory -Force -Path $p | Out-Null
        git -C $p init -q -b main
        git -C $p config user.email 'wintest@example.invalid'
        git -C $p config user.name 'wintest'
    }
    Write-Utf8 "$PC\README.md" "# Code`n"
    Write-Utf8 "$PD\notes.md" "# Notes`n"
    Write-Utf8 "$PD\priv.md" "# Private register`n`n**Unit type:** Register`n`n| ID | Tool | Claim | Problem shape | Evidence | Activity | Technology | Specialises | Overrides |`n|---|---|---|---|---|---|---|---|---|`n| PV-1 | tool | A private claim. | a shape | evidence | | | | |`n"
    git -C $PC add -A; git -C $PC commit -q -m 'initial'
    git -C $PD add -A; git -C $PD commit -q -m 'initial'
    Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "private-docs"
code = '$PC'
docs = '$PD'
domains = ["demo"]
git = { docs = { commit = "manual", push = "manual" } }

[projects.families]
PV = { defined = "docs:priv.md", type = "note" }
"@
    Add-Utf8 "$PD\notes.md" "more`n"
    vyd docs record "$PD\notes.md" -m "update notes" --in $PC
    'exit ' + $LASTEXITCODE
    git -C $PD status --short
    Write-Utf8 "$PC\cite.md" "Cites PV-1 here`n"
    git -C $PC add cite.md
    vyd check citations --staged --in $PC
    'exit ' + $LASTEXITCODE
    git -C $PC rm -q -f --cached cite.md
    Remove-Item "$PC\cite.md"
}
```

**Pass.** `docs record` prints `private-docs: staged notes.md. Commit is manual, so nothing is committed`, exit 0, and git shows `M  notes.md` in the documents repository. The citation check prints `cite.md:1: cites private-docs:PV-1, which is private` and exits 1. `docs record` needs an absolute path or one relative to the working folder, and a path outside the documents folder is refused with `is outside the documents folder`.

#### W10.4 The project is the documents' owner

```powershell
Step W10.4 { vyd config $PC }
```

**Pass.** `projects:` includes `private-docs`. The `docs` folder is outside `code`, so its entries are labelled private.

#### W10.5 A move with a removed copy

The `example-service` entry moved the family `RULE` to `demo`. `copy_removed = true` says the project has removed its copy.

```powershell
Step W10.5 {
    vyd move check $Code
    $cfg = [IO.File]::ReadAllText($env:VYVID_CONFIG)
    $m = [regex]::Match($cfg, 'commit = "([0-9a-f]+)"')
    Write-Utf8 $env:VYVID_CONFIG ($cfg.Replace($m.Value, $m.Value + "`ncopy_removed = true"))
    vyd move check $Code
    vyd move check $Code --ref HEAD
    vyd move check $Code --json
}
```

**Pass.** The first run prints `nothing differs`. After the change the second prints `RULE - copy-removed`. With `--ref HEAD` it prints `RULE - copy-removed` when the working file is byte-identical to the file at the ref, and `nothing differs` when it is not, which is the case with `core.autocrlf` true, since the working file has CRLF and the blob has LF. Mark NOTE with which line you saw and the value of `core.autocrlf`. Both exit 0.

#### W10.6 Resolve an identifier through a move

```powershell
Step W10.6 { vyd resolve RULE-1 --in $Code }
```

**Pass.** `demo:RULE-1` on standard output, and a line on standard error saying `example-service:RULE-1 moved to demo:RULE-1 (family RULE, from <path>\docs\rules.md at <commit>)`.

## W11 Source symbols

Needs the extra from W2.7 and the project from W5.

#### W11.1 Ask for a symbol and read it

```powershell
Step W11.1 {
    vyd find greeting for a name --kind symbol --no-log
    vyd read example-service:greet.greet
}
```

**Pass.** A row `example-service:greet.greet`, kind `function`, module `greet`, `src/greet.py:4`, and a source excerpt for `read` with a header `== src/greet.py:4-6` and the lines of the function. Forward slashes in the pointer.

#### W11.2 What `vyd` says without the extra (only if W2.7 failed)

The message says the symbols need the extra and `vyd` goes on. Capture it.

#### W11.3 Handoff to a compiler index

```powershell
Step W11.3 {
    vyd handoff greet --in $Code
    'exit ' + $LASTEXITCODE
    foreach ($c in 'hiedb', 'sqlite3', 'ghc') { $g = Get-Command $c -ErrorAction SilentlyContinue; if ($g) { "$c found at $($g.Source)" } else { "$c not found" } }
}
```

**Pass.** With no code index registered, `no code index is registered here. A project registers one in a [[project.code_index]] table of its vyvid.toml, with a kind, a database and, to say how it is built, built_by.` and exit 1. The `.hie` tools are optional and skipped when absent, so there is no step that builds one. If `hiedb` is present and you have a Haskell project, note it and skip.

## W12 `vyd install` into scratch folders

Needs W5. Every step names `--target`, so nothing is written to the real client folders. `--target` needs `--client`. Without the model nothing here changes.

#### W12.1 Dry run to a target

```powershell
Step W12.1 { vyd install --client claude-code --target "$T\tgt-claude" --dry-run }
```

**Pass.** One `no skill for domain <name>, whose trust is knowledge, which gives knowledge alone. If you wrote it, a person runs: vyd domain trust <name> own. If someone else did, read it and run: vyd domain trust <name> reviewed --commit <hash>` line per cloned public domain, then three `would write` lines for `skills\vyvid-core-domain-review\SKILL.md`, `rules\vyvid.md` and `agents\vyvid-domain-reviewer.md`. Exit 0, and the target folder is not created.

#### W12.2 Write them, check the bytes, run again

```powershell
Step W12.2 {
    vyd install --client claude-code --target "$T\tgt-claude"
    foreach ($f in Get-ChildItem "$T\tgt-claude" -Recurse -File) {
        $b = [IO.File]::ReadAllBytes($f.FullName)
        '{0}: {1} carriage returns, first byte {2}' -f $f.FullName.Substring($T.Length), ($b | Where-Object { $_ -eq 13 }).Count, $b[0]
    }
    vyd install --client claude-code --target "$T\tgt-claude"
    'second run exit ' + $LASTEXITCODE
}
```

**Pass.** Three files, no carriage returns, and the first bytes 45 for the skill and the agent file and 60 for the rule file, which starts with `<!--`. Neither starts with 239. The second run writes them again and exits 0.

#### W12.3 A file that was not generated is left alone

```powershell
Step W12.3 {
    Write-Utf8 "$T\tgt-claude\rules\vyvid.md" "my own rule`n"
    vyd install --client claude-code --target "$T\tgt-claude"
    'exit ' + $LASTEXITCODE
    Get-Content "$T\tgt-claude\rules\vyvid.md"
}
```

**Pass.** `left <path>, which exists and was not generated by vyvid install`, exit 1, and the file still reads `my own rule`.

#### W12.4 Copilot with `--hooks` writes no hook

```powershell
Step W12.4 {
    vyd install --client copilot --hooks --target "$T\tgt-copilot"
    'exit ' + $LASTEXITCODE
    'settings.json written: ' + (Test-Path "$T\tgt-copilot\settings.json")
    Get-ChildItem "$T\tgt-copilot" -Recurse -File -Name
}
```

**Pass.** The core skill is written, and the line `vyd: copilot documents no user-level hook file, so no hook was written. Run vyd install --project to register the hook in a project's checkout` is printed. The exit code is 1 and `settings.json written: False`. The listing holds only `skills\vyvid-core-domain-review\SKILL.md`. At v0.2.14 this is the specified behaviour.

#### W12.5 Claude Code with `--hooks` writes the settings file

```powershell
Step W12.5 {
    vyd install --client claude-code --hooks --target "$T\tgt-hooks"
    'exit ' + $LASTEXITCODE
    $b = [IO.File]::ReadAllBytes("$T\tgt-hooks\settings.json")
    'first byte ' + $b[0] + ', carriage returns ' + ($b | Where-Object { $_ -eq 13 }).Count
    (Get-Content -Raw "$T\tgt-hooks\settings.json" | ConvertFrom-Json).hooks.PreToolUse[0].matcher
}
```

**Pass.** A `wrote <path>\settings.json` line, exit 0, first byte 123, no carriage returns and the matcher `Bash|PowerShell|Grep|Glob`.

#### W12.6 A settings file with a byte order mark

```powershell
Step W12.6 {
    New-Item -ItemType Directory -Force -Path "$T\tgt-bom" | Out-Null
    [IO.File]::WriteAllText("$T\tgt-bom\settings.json", '{"hooks":{}}', (New-Object System.Text.UTF8Encoding($true)))
    vyd install --client claude-code --hooks --target "$T\tgt-bom"
    'exit ' + $LASTEXITCODE
}
```

**Expected on macOS.** The core files are written, then `vyd: the hook was not registered, since <path>\settings.json could not be read: Unexpected UTF-8 BOM (decode using utf-8-sig): line 1 column 1 (char 0)` and exit 1. A refusal with a message is acceptable, but a user whose own settings file was saved with a byte order mark meets it, so mark NOTE with 'settings file with byte order mark is refused'.

#### W12.7 A target inside a project is refused

```powershell
Step W12.7 { vyd install --client claude-code --target "$Code\x"; 'exit ' + $LASTEXITCODE }
```

**Pass.** `vyd: <path> is inside the folder of project example-service, and install writes nothing there`, exit 2, and nothing created.

#### W12.8 A listed domain with no folder removes nothing

A stale generated skill is planted. With a domain missing, install keeps it. With every domain present, it names it for removal.

```powershell
Step W12.8 {
    $marker = '<!-- Generated by vyvid install. Do not edit, change the domain instead. -->'
    Write-Utf8 "$T\tgt-stale\skills\vyvid-domain-old\SKILL.md" "---`nname: old`n---`n$marker`n`n# old`n"
    Write-Utf8 "$T\cfg-gone.toml" "[framework]`nkb = '$T\kb'`n`n[[domains]]`nname = `"gone`"`npath = '$T\absent\gone'`n"
    '== with a missing domain'
    WithConfig "$T\cfg-gone.toml" { vyd install --client claude-code --target "$T\tgt-stale" --dry-run }
    '== with every domain present'
    vyd install --client claude-code --target "$T\tgt-stale" --dry-run
}
```

**Pass.** The first run prints `NOTE: domain gone has no folder here, at <path>, so it gives nothing on this machine. Clone it there, or take its entry out of this machine's configuration`, the three `would write` lines and no `would remove`. The second prints the three `would write` lines and `would remove <path>\skills\vyvid-domain-old\SKILL.md`. Neither removes anything because both are dry runs.

## W13 LATTICE on the switch

Needs W4 and GitHub over https, and `mise` for the `mise run` steps. The repository is large, so the clone takes a while. Nothing is pushed, and the full `mise run check` is optional.

LATTICE's move to `vyd` has merged, so its `main` declares a project in a `vyvid.toml`. `$Branch` is `main`, and another branch can be tried by changing it. If `vyvid.toml` is absent on the chosen branch, the repository does not declare a project there, and this section stops at W13.2. The five domains that file names are public and are among the six W4 cloned. The private domains named in that repository's documents are not expected to resolve here.

#### W13.1 Clone

```powershell
$Branch = 'main'
Step W13.1 {
    git clone --branch $Branch https://github.com/nebularis/lattice.git "$T\lattice"
    git -C "$T\lattice" log --oneline -3
}
```

**Pass.** The clone finishes, with possible `LF will be replaced by CRLF` messages and, on a path-length problem, errors naming a file. Record a failure to check out a long path with the `core.longpaths` value from W1.2.

#### W13.2 Does the branch declare a project

```powershell
Step W13.2 {
    'vyvid.toml present: ' + (Test-Path "$T\lattice\vyvid.toml")
    if (Test-Path "$T\lattice\vyvid.toml") { Get-Content "$T\lattice\vyvid.toml" | Select-Object -First 25 }
}
```

**Pass.** `vyvid.toml present: True` and its first lines. On `False`, mark NOTE with the branch and stop here.

#### W13.3 Bind it in the scratch configuration

```powershell
Add-Utf8 $env:VYVID_CONFIG @"

[[projects]]
name = "lattice"
visibility = "public"
code = '$T\lattice'
match = { remote = "github.com/nebularis/lattice" }
"@
Step W13.3 { vyd config "$T\lattice" }
```

**Pass.** `projects:` includes `lattice`, and `project file: <path>\vyvid.toml` appears. The file declares the rest. Domains the file names and the scratch configuration lacks are left out, each with a `NOTE: domain ... is named by vyvid.toml and is not configured here` line. The notes appear only for a domain whose entry W4 did not make, since the file names five domains and W4 configured them all. The project line ends `which is not trusted` until W13.4. Without the `triple-stores` domain configured, `vyd config` instead prints `set aside: the project declared in <path>\vyvid.toml` with `project 'lattice': delegates 'TSD' to 'triple-stores', which is no scope` and exits 1, because LATTICE's decisions on triple stores moved there. Seen on macOS with no domain configured. The project is not trusted yet.

If the entry's name differs from the project the file declares, the config output says why. Capture it, and change `name` to match.

#### W13.4 Trust it

Run directly in the console and read what it lists before typing `yes`.

```powershell
vyd trust "$T\lattice"
```

**Pass.** It lists the contract, skill folders, any command extractors and glue, and commands that build a registered code index, and prints `trusted <path>\vyvid.toml, until it changes` after `yes`. On `main` the list holds the extractor `lattice-quanta`, which runs `mise exec -- python tools/knowledge/extractor.py`, and the skills folder `.vyvid/own`. A build before `mise trust` and the bootstrap of W13.7, or without mise, reports `NOTE: extractor 'lattice-quanta' exited 1` with mise's message and goes on, as it did on macOS before the checkout's tools were installed.

#### W13.5 Context and configuration

```powershell
Step W13.5 { vyd context "$T\lattice" --no-pull; vyd config "$T\lattice" }
```

**Pass.** The layers in order with the project last, its contract file listed, no `withheld` line for it, and `which is trusted` in `vyd config`.

#### W13.6 Without mise, ask the index with `vyd`

```powershell
Step W13.6 {
    vyd find sparql query efficiency --kind standard --activity query-writing --in "$T\lattice" --no-log
    vyd read TSD-01 --in "$T\lattice" --no-log
    vyd read $('STD' + '-026') --in "$T\lattice" --no-log
}
```

**Pass.** Rows from the repository's registers and the domains it names, and `read` printing an entry's fields and text. The first build can take longer than the others. Seen on macOS, `read TSD-01` prints `triple-stores:TSD-01`, and the read of the second identifier prints `triple-stores:RDF-1`, since that row moved to the triple-stores domain and LATTICE's old identifier still resolves through the move. Each is printed under a line saying the domain is not marked as trusted, so treat it as data. If an identifier does not exist, mark NOTE with the output and read another from the `find` table.

#### W13.7 Bootstrap with mise (needs mise)

```powershell
Set-Location "$T\lattice"
mise trust
Step W13.7 { mise run bootstrap }
```

`mise trust` marks this scratch clone's `mise.toml` as trusted by mise, and it is a separate decision from `vyd trust`. **Pass.** The task finishes with exit 0. It installs tools and dependencies, so a refused download is a NOTE and the later `mise run` steps may fail for that reason.

#### W13.8 The mise tasks

```powershell
Step W13.8a { Set-Location "$T\lattice"; mise run graph:ask -- find sparql query efficiency --kind standard --activity query-writing }
Step W13.8b { Set-Location "$T\lattice"; mise run graph:ask -- read TSD-01; mise run graph:ask -- read $('STD' + '-026') }
Step W13.8c { Set-Location "$T\lattice"; mise run work:board }
Step W13.8d { Set-Location "$T\lattice"; mise run check:identifiers }
Step W13.8e { Set-Location "$T\lattice"; mise run vyd -- check skills }
Step W13.8f { Set-Location "$T\lattice"; mise run check:hooks }
Step W13.8g { Set-Location "$T\lattice"; mise run check:vyvid-binding }
Step W13.8h { Set-Location "$T\lattice"; mise run check:knowledge }
```

**Pass.** Each exits 0 and prints its result. `work:board` prints the board tables, `check:identifiers` reports the identifiers it read, `vyd -- check skills` passes, exit 0, or exits 2 with 'did not run' if a domain the project uses is missing, which is expected only if a clone of W4 was refused, since the project's domains are all public. Record the exact exit code and message of each. A task that does not exist on the chosen branch is a NOTE, not a failure.

**Failure.** A path in a message printed with a backslash where the repository's own tasks print forward slashes, a `UnicodeEncodeError`, or a failure to start `vyd` from the wrapper. Capture the first 60 and last 20 lines, which the helper keeps.

#### W13.9 The wrapper without `vyd` on the path

The wrapper should skip with a note when `vyd` is not installed.

```powershell
Step W13.9 {
    Set-Location "$T\lattice"
    $keep = $env:PATH
    $bin = (uv tool dir --bin).Trim()
    $env:PATH = (($env:PATH -split ';') | Where-Object { $_ -and ($_.TrimEnd('\') -ne $bin.TrimEnd('\')) }) -join ';'
    'vyd on path: ' + [bool](Get-Command vyd -ErrorAction SilentlyContinue)
    mise run vyd -- check skills
    'exit ' + $LASTEXITCODE
    mise run check:vyvid-binding
    'exit ' + $LASTEXITCODE
    mise run graph:ask -- find sparql query efficiency
    'exit ' + $LASTEXITCODE
    $env:PATH = $keep
}
```

**Pass.** `vyd on path: False`, then each wrapper prints a note that `vyd` is not installed, or a skip, and exits 0 where the task is meant to skip. Record each message. If `vyd` is still found, it is installed in another folder on the path, so record where `Get-Command vyd` says. If you used W2.1b, replace `uv tool dir --bin` with `"$T\venv\Scripts"`.

#### W13.10 The full check (optional)

The full `mise run check` is long and need not be run. It is worth running once, because failures of it on Windows are results.

```powershell
Step W13.10 { Set-Location "$T\lattice"; mise run check }
```

Do not push anything. Mark each failing task with its name and the first error. **Pass** is exit 0.

#### W13.11 The memory figure the check asks about (needs W13.7)

LATTICE's memory standard (`lattice:STD-321`) asks the maintainer before a whole check starts on a machine with less than 35% of its memory available. That figure was chosen on macOS. The figure Windows reports counts less as available under the same load, so it is expected to read lower here. The result the maintainer wants is whether 35% would ask too often on this machine, so run the step once with the machine idle and again under the load you usually work with.

```powershell
Step W13.11 {
    Set-Location "$T\lattice"
    mise exec -- python -c "import mem_check; print(mem_check.available_percent())"
}
```

**Pass.** A whole number from 0 to 100. On Windows the code reads 100 minus the system's memory load, so the number should be close to 100 minus Task Manager's memory in use as a share of the total (Performance, Memory). That is read from the code and has not been run. Compare it by eye and record it as this machine's reading with `Mark W13.11 NOTE 'reading N, Task Manager in use M%, idle or under load'`. `None` means the system's figure could not be read, which is a result to record. Seen on macOS, the step printed `40` with the machine in ordinary use.

#### W13.12 The slower check for a busy machine (optional, needs W13.7)

`mise run check:low-memory` runs `mise run check` one task at a time with two test workers, prints the memory available once a minute, and stops the run if less than 1 GiB stays available. It is slower than W13.10, which runs the same tasks together, and it was not timed, so start it only when the machine can be left for a long while. The step prints at most the last 20 lines.

```powershell
Step W13.12 { Set-Location "$T\lattice"; mise run check:low-memory; 'exit ' + $LASTEXITCODE }
```

**Pass.** Exit 0 and a last line reading `mem_check.guard: the lowest available was N GiB`. Record that line with `Mark W13.12 NOTE '...'`, since the lowest figure is what the maintainer wants to compare with the 1 GiB floor. Exit 3 with `mem_check.guard: N GiB available, under 1.0 GiB, so the run was stopped` means the guard stopped the run, which is neither a pass nor a failure, so mark NOTE with the line and the figure. Any other exit code is a task that failed, and is recorded like W13.10. The wrapper's last line was seen on macOS with a four-second command, and the whole task was not run.

#### W13.13 A question ranks

```powershell
Step W13.13 { Set-Location "$T\lattice"; mise run graph:ask -- find why does a SPARQL constraint run slowly --no-log }
```

**Pass.** Exit 0 and a table whose first column is `score`, with rows in descending score order and a line of claim text under each. No identifier is expected. Without the model, `find cannot rank here: no vectors.npz in <store>. Run vyd build, which says why`, which is the expected result and not a failure.

## W14 Optional, writes to the real client folders

Needs W12 to have passed. Skip this section unless you want to know that the real folders work. Each step says exactly what it writes and how to undo it. The scratch configuration is still in force, so only the core files are written, since the scratch configuration has no private domain and no `user_skills`.

Back up first, and record what exists.

```powershell
Step W14.0 {
    foreach ($d in '.claude', '.copilot') {
        $p = Join-Path $env:USERPROFILE $d
        "$d exists: " + (Test-Path $p)
    }
    $s = Join-Path $env:USERPROFILE '.claude\settings.json'
    if (Test-Path $s) { Copy-Item $s "$T\claude-settings.backup.json"; 'settings.json copied to the test folder' }
}
```

#### W14.1 Dry run into the real folders

```powershell
Step W14.1 { vyd install --dry-run; 'exit ' + $LASTEXITCODE }
```

**Pass.** For each client whose folder exists, `would write` lines for the real paths. If neither exists, `vyd: no client's folder is here, so nothing was written. Name one with --client: claude-code, copilot` and exit 1. No file changes.

#### W14.2 Write the core files for one client

```powershell
Step W14.2 { vyd install --client claude-code }
```

This writes three files, creating `%USERPROFILE%\.claude` and the subfolders if absent. They are `skills\vyvid-core-domain-review\SKILL.md`, `rules\vyvid.md` and `agents\vyvid-domain-reviewer.md`, each opening with `<!-- Generated by vyvid install. Do not edit, change the domain instead. -->` or a front matter followed by it. A file that exists and does not carry the marker is left alone and reported.

**Undo.**

```powershell
$c = Join-Path $env:USERPROFILE '.claude'
Remove-Item "$c\skills\vyvid-core-domain-review", "$c\rules\vyvid.md", "$c\agents\vyvid-domain-reviewer.md" -Recurse -WhatIf
```

Run again without `-WhatIf` once the list is right. Remove the `.claude` folder itself only if `W14.0` said it did not exist before and `Get-ChildItem $c` is empty.

#### W14.3 Register the hook in the real settings file

```powershell
Step W14.3 { vyd install --client claude-code --hooks }
```

This rewrites `%USERPROFILE%\.claude\settings.json`, keeping every other key, with a `hooks.PreToolUse` entry whose command contains `vyd-hook`, in two-space indented JSON. Comments or unusual formatting in the file are lost. **Undo** by copying `$T\claude-settings.backup.json` back over it, or, if none existed, by deleting the file when it holds only that entry.

#### W14.4 Copilot

```powershell
Step W14.4 { vyd install --client copilot }
```

This writes `%USERPROFILE%\.copilot\skills\vyvid-core-domain-review\SKILL.md` only. **Undo** by removing that folder, and `.copilot` if it did not exist before and is now empty.

#### W14.5 Every client at once

```powershell
Step W14.5 { vyd install }
```

This does the same as W14.2 and W14.4 for each client whose folder exists, and writes nothing otherwise. Run `vyd config` afterward. A line that the installed files are out of date means they differ from what the current configuration would write.

## W15 Return the results and clean up

#### W15.1 Get the results back

The machine cannot push, so the results have to be copied by hand. First mark any step you ran and did not mark. Then print the summary.

```powershell
Show-Results
```

This prints how many steps passed, a table of every step marked FAIL or NOTE, and under it the output of each of those steps and of every step run but not marked. Names found in `USERNAME`, `COMPUTERNAME`, `USERDOMAIN`, `LOGONSERVER` and `USERDNSDOMAIN` are replaced by placeholders, which catches the common cases and not all of them.

Read it before you send it. Output can hold user names in paths, computer names, network or domain names, addresses, folder names from your own projects, and the names of private repositories in `git remote -v` or `mise` output. Replace each with a placeholder. `Show-Results -NoRedact` shows the text unchanged. To copy it, run `Show-Results | Set-Clipboard`, then paste it where you send results. Send the table and the failing steps' output, not the whole results file.

If a step failed in a way the table does not explain, send the full block for that step with `Get-Content $Results`, trimmed to that step.

#### W15.2 Clean up

First stop anything left running and remove linked worktrees, since they register themselves in their repositories.

```powershell
Get-Process -Name ping -ErrorAction SilentlyContinue | Stop-Process -Force
foreach ($r in $Code, $BoardRepo, (Join-Path $T 'work\repo-trust')) { if (Test-Path $r) { git -C $r worktree prune } }
Set-Location $env:USERPROFILE
```

Remove the test folder. Long paths need the extended prefix.

```powershell
Remove-Item -LiteralPath $T -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $T) { cmd /c "rmdir /s /q \\?\$T" }
'test folder still present: ' + (Test-Path $T)
```

Remove the hook state folder of W8.4, which is outside the test folder.

```powershell
Remove-Item -LiteralPath (Join-Path ([IO.Path]::GetTempPath()) 'vyvid-hook-user') -Recurse -Force -ErrorAction SilentlyContinue
```

Remove the tool if you want it gone.

```powershell
uv tool uninstall vyvid
```

If you used the fallback, the venv was in the test folder and is already gone. To restore a `vyd` that was installed before, install it again.

Clear the environment variables of this window by closing it, or run `Remove-Item Env:VYVID_CONFIG, Env:VYVID_HOOK_STATE, Env:PYTHONUTF8, Env:GIT_TERMINAL_PROMPT`. `WithOwn` and W5.14 restore `WIN_PD_OVERRIDE_LOCAL_APPDATA` and `HTTPS_PROXY` themselves, so if a step was interrupted, check `Get-ChildItem Env:WIN_PD_OVERRIDE_LOCAL_APPDATA, Env:HTTPS_PROXY` and remove what the test set.

#### What is left outside the test folder

| Where | What | Removal |
|---|---|---|
| `%LOCALAPPDATA%\vyvid\vyvid` | The trust record written by `vyd trust` in W6.4, W6.15 and W13.4, and anything else `vyd` keeps by default. W1.6 says whether the folder existed before | Delete the folder only if W1.6 said it did not exist. Otherwise leave it, since it holds trust you gave before |
| uv's tool environment and its two shims | The installed `vyd` and `vyd-hook` | `uv tool uninstall vyvid` |
| uv's cache | Downloaded wheels and clones | `uv cache clean`, if you want the space back |
| `%TEMP%\vyvid-hook-user` | The hook state without a state variable (W8.4) | Removed above |
| mise's trust record for the LATTICE clone | The decision of W13.7 | `mise trust --untrust "$T\lattice\mise.toml"` before deleting the folder, if mise offers it, otherwise ignore it |
| `%USERPROFILE%\.claude`, `%USERPROFILE%\.copilot` | Only if you ran W14 | The undo steps of W14 |
| The git config of the test repositories | Local to each, removed with the folder | none |
| Your global git config and your environment | Not changed by this file | none |
