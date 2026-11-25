# Installer for tutor-any-lecture on Windows.
# It installs the command-line tool with uv (or, without uv, into a private venv),
# records the tool's full path in <config dir>\cli-path, copies this skill folder
# to your agents and runs `tutor-any-lecture doctor --json`.
# It never downloads a script to run it; uv or pip fetch the package itself.
# Works in Windows PowerShell 5.1 and PowerShell 7.
#
# Usage:
#   powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 [options]
#
#   -DryRun          print the plan as PLAN: lines and change nothing
#   -Yes             never ask for confirmation
#   -WithAsr         also install speech recognition (the package's asr extra),
#                    needed only for audio or video without captions
#   -CliOnly         install the command and record its path, but copy no skill
#                    folder (cannot be combined with -Agents)
#   -Agents LIST     comma-separated list of claude, codex, agents, any letter case
#                    (default: each of them whose home folder exists)
#   -From PATH|URL   what to install, passed unchanged to uv or pip
#                    (default: this checkout, else the GitHub repository at the
#                    release tag v<VERSION>, VERSION being the file in the skill
#                    folder, else its default branch for a development VERSION)
#
# Exit codes: 0 ready, 1 failed or cancelled, 2 bad option, 3 needs action.
[CmdletBinding(PositionalBinding = $false)]
param(
    [switch]$DryRun,
    [switch]$Yes,
    [switch]$WithAsr,
    [switch]$CliOnly,
    [string[]]$Agents,
    [string]$From,
    # Anything else lands here and is refused below with exit code 2.
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Rest
)
$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/hypersupersheep/tutor-any-lecture'
$GitHubSource = 'git+' + $RepoUrl

# [Console]::Out writes in the console's code page (OEM by default), which would
# turn a CJK path into '?'. Output is UTF-8 (no BOM) from the first line on, and
# Exit-Installer, the only way out of this script, puts the earlier state back:
# under .\install.ps1 this process is the caller's session.
$script:SavedOutputEncoding = $null
$script:SavedOut = $null
try {
    $script:SavedOutputEncoding = [Console]::OutputEncoding
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [Console]::OutputEncoding = $utf8
    # A redirected [Console]::Out made before this line keeps its old encoding, so
    # it is replaced by a UTF-8 writer on the same stream for the length of the run.
    if ([Console]::IsOutputRedirected -and ([Console]::Out.Encoding.CodePage -ne 65001)) {
        $writer = New-Object System.IO.StreamWriter -ArgumentList @([Console]::OpenStandardOutput(), $utf8)
        $writer.AutoFlush = $true
        $script:SavedOut = [Console]::Out
        [Console]::SetOut($writer)
    }
} catch { }

function Exit-Installer([int]$Code) {
    if ($null -ne $script:SavedOut) {
        try {
            [Console]::Out.Flush()
            [Console]::SetOut($script:SavedOut)
        } catch { }
    }
    if ($null -ne $script:SavedOutputEncoding) {
        try { [Console]::OutputEncoding = $script:SavedOutputEncoding } catch { }
    }
    exit $Code
}

function Say([string]$Message) {
    [Console]::Out.WriteLine($Message)
}

function Fail([string]$Message, [int]$Code) {
    [Console]::Error.WriteLine($Message)
    Exit-Installer $Code
}

# Run a native command with each argument passed separately; stop with exit 1
# when it fails. Native commands never stop a script on their own, so the exit
# code is checked here.
function Invoke-Native([string]$What, [string]$Exe, [string[]]$Arguments) {
    $ErrorActionPreference = 'Continue'
    & $Exe @Arguments | Out-Host
    if ($LASTEXITCODE -ne 0) {
        Fail "install.ps1: $What failed (exit code $LASTEXITCODE)." 1
    }
}

# ---- options ---------------------------------------------------------------
if ($Rest -and $Rest.Count -gt 0) {
    Fail ('install.ps1: unknown option: ' + ($Rest -join ' ') + ' (see the comments at the top of install.ps1).') 2
}
if ($CliOnly -and $PSBoundParameters.ContainsKey('Agents')) {
    Fail 'install.ps1: -CliOnly copies no skill folder, so it cannot be combined with -Agents.' 2
}

# ---- locate this script ----------------------------------------------------
# $PSScriptRoot is this script's folder as an absolute path, whatever the
# caller's current folder. The caller's current folder is never changed.
$D = $PSScriptRoot
$SkillSrc = [System.IO.Path]::GetFullPath((Join-Path $D '..'))

# ---- what to install -------------------------------------------------------
# The skill folder's VERSION names the release tag of the GitHub fallback.
$Version = ''
$VersionFile = Join-Path $SkillSrc 'VERSION'
if (Test-Path -LiteralPath $VersionFile -PathType Leaf) {
    $Version = ([System.IO.File]::ReadAllText($VersionFile, (New-Object System.Text.UTF8Encoding($false)))).Trim()
}
# True when the file is a pyproject.toml whose [project] table holds
# name = "tutor-any-lecture". It is read as UTF-8; each line is compared with its
# spaces, tabs and a trailing CR removed, and the table ends at the next '['.
function Test-NamesThisProject([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $false
    }
    try {
        $text = [System.IO.File]::ReadAllText($Path, (New-Object System.Text.UTF8Encoding($false)))
    } catch {
        return $false
    }
    $inProject = $false
    foreach ($raw in $text.Split("`n")) {
        $line = $raw
        if ($line.EndsWith("`r")) {
            $line = $line.Substring(0, $line.Length - 1)
        }
        $line = $line.Replace(' ', '').Replace("`t", '')
        if ($line -ceq '[project]') {
            $inProject = $true
        } elseif ($line.StartsWith('[')) {
            $inProject = $false
        } elseif ($inProject -and (($line -ceq 'name="tutor-any-lecture"') -or ($line -ceq "name='tutor-any-lecture'"))) {
            return $true
        }
    }
    return $false
}

# $SourceKind says where $From came from: from (-From), checkout, tag (a release
# id in VERSION), dev (a development id, never tagged) or none (no release id).
# A number is 0 or has no leading zero, and letter case counts (-cmatch).
$Num = '(0|[1-9][0-9]*)'
$TaggedPattern = '^' + $Num + '\.' + $Num + '\.' + $Num + '(-rc\.' + $Num + ')?$'
$DevPattern = '^' + $Num + '\.' + $Num + '\.' + $Num + '-dev\.' + $Num + '$'
$SourceKind = 'from'
if ($PSBoundParameters.ContainsKey('From')) {
    if ([string]::IsNullOrEmpty($From)) {
        Fail 'install.ps1: -From needs a path or URL.' 2
    }
} elseif (Test-NamesThisProject (Join-Path $D '../../../pyproject.toml')) {
    $From = [System.IO.Path]::GetFullPath((Join-Path $D '../../..'))
    $SourceKind = 'checkout'
} elseif ($Version -cmatch $TaggedPattern) {
    $From = $GitHubSource + '@v' + $Version
    $SourceKind = 'tag'
} elseif ($Version -cmatch $DevPattern) {
    $From = $GitHubSource
    $SourceKind = 'dev'
} else {
    $From = $GitHubSource
    $SourceKind = 'none'
}

$GitExe = ''
if ($From -like 'git+*') {
    $gitCommand = Get-Command 'git' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $gitCommand) {
        Fail "install.ps1: installing from $From needs git, which was not found; get it with 'winget install Git.Git', or pass -From <a checkout or an unpacked download>." 3
    }
    $GitExe = $gitCommand.Path
}

# The file:// URL of an absolute path (C:\..., \\server\share\... or /...), each
# segment percent-encoded as UTF-8 so spaces and CJK names survive.
function ConvertTo-FileUrl([string]$Path) {
    $p = $Path.Replace('\', '/')
    if ($p.StartsWith('//')) {
        $p = $p.Substring(2)
    } elseif (-not $p.StartsWith('/')) {
        $p = '/' + $p
    }
    $parts = @()
    foreach ($segment in $p.Split('/')) {
        if ($segment -match '^[A-Za-z]:$') {
            $parts += $segment
        } else {
            $parts += [System.Uri]::EscapeDataString($segment)
        }
    }
    return 'file://' + ($parts -join '/')
}

# $InstallSpec is what uv or pip installs: the source itself, or with -WithAsr the
# requirement "tutor-any-lecture[asr] @ <the source as a URL>".
$InstallSpec = $From
if ($WithAsr) {
    $SourceUrl = $From
    if (($From -notmatch '^[A-Za-z][A-Za-z0-9+.-]+://') -and (Test-Path -LiteralPath $From)) {
        $SourceUrl = ConvertTo-FileUrl ((Resolve-Path -LiteralPath $From).ProviderPath)
    }
    $InstallSpec = 'tutor-any-lecture[asr] @ ' + $SourceUrl
}

if ([string]::IsNullOrEmpty($env:USERPROFILE)) {
    Fail 'install.ps1: USERPROFILE is not set.' 1
}
$HomeDir = $env:USERPROFILE

# ---- agents ----------------------------------------------------------------
# -Agents is a string array; each element is split on ',' so that both
# `-Agents claude,codex` typed in PowerShell and the single string that
# `pwsh -File` passes work.
# With -CliOnly the list stays empty.
$AgentNames = New-Object System.Collections.Generic.List[string]
if ($CliOnly) {
    # no skill folder is copied
} elseif ($PSBoundParameters.ContainsKey('Agents')) {
    foreach ($element in $Agents) {
        foreach ($part in ([string]$element).Split(',')) {
            $name = $part.Trim().ToLowerInvariant()
            if (@('claude', 'codex', 'agents') -notcontains $name) {
                Fail "install.ps1: unknown agent name '$name' (use claude, codex or agents)." 2
            }
            if (-not $AgentNames.Contains($name)) {
                $AgentNames.Add($name)
            }
        }
    }
} else {
    foreach ($name in @('claude', 'codex', 'agents')) {
        if (Test-Path -LiteralPath ($HomeDir + '\.' + $name) -PathType Container) {
            $AgentNames.Add($name)
        }
    }
}

# ---- install method --------------------------------------------------------
function Test-Python([string]$Exe, [string[]]$Prefix) {
    if (-not (Get-Command $Exe -CommandType Application -ErrorAction SilentlyContinue)) {
        return $false
    }
    $ErrorActionPreference = 'Continue'
    $probe = 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'
    & $Exe @Prefix -c $probe *> $null
    return ($LASTEXITCODE -eq 0)
}

$Method = ''
$PyExe = ''
$PyPrefix = @()
if (Get-Command 'uv' -CommandType Application -ErrorAction SilentlyContinue) {
    $Method = 'uv'
} elseif (Test-Python 'py' @('-3')) {
    $Method = 'venv'
    $PyExe = 'py'
    $PyPrefix = @('-3')
} elseif (Test-Python 'python' @()) {
    $Method = 'venv'
    $PyExe = 'python'
    $PyPrefix = @()
}
if ($Method -eq '') {
    [Console]::Error.WriteLine('tutor-any-lecture needs uv or Python 3.10 or newer, and found neither on PATH.')
    [Console]::Error.WriteLine('Install uv with one of these commands:')
    [Console]::Error.WriteLine('  winget install astral-sh.uv')
    [Console]::Error.WriteLine('  pipx install uv')
    [Console]::Error.WriteLine('  brew install uv   (macOS)')
    [Console]::Error.WriteLine('or follow https://docs.astral.sh/uv/getting-started/installation/')
    [Console]::Error.WriteLine('Then run this installer again.')
    # The Microsoft Store alias is a 'python' that only opens the Store.
    $alias = Get-Command 'python' -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($alias) {
        $aliasPath = [string]$alias.Path
        if (($aliasPath -like '*\Microsoft\WindowsApps\*') -or ($aliasPath -like '*/Microsoft/WindowsApps/*')) {
            [Console]::Error.WriteLine("Note: the 'python' on PATH ($aliasPath) is the Microsoft Store alias, not Python; install Python 3.10 or newer with 'winget install Python.Python.3.12', or turn the alias off under Settings, Apps, Advanced app settings, App execution aliases.")
        }
    }
    Exit-Installer 3
}

# ---- the release tag -------------------------------------------------------
# Put an environment variable back to a saved value; $null removes it.
# ($Value has no type, so $null stays $null instead of becoming ''.)
function Restore-EnvVar([string]$Name, $Value) {
    if ($null -eq $Value) {
        Remove-Item -LiteralPath ('Env:' + $Name) -ErrorAction SilentlyContinue
    } else {
        Set-Item -LiteralPath ('Env:' + $Name) -Value $Value
    }
}

# A release tag that cannot be fetched ends the script here, in the dry run too,
# before any plan line. GitHub answers 401 for a missing repository, and Git
# Credential Manager would then open a sign-in window: the empty credential.helper
# drops every configured helper, and the two variables turn off git's terminal
# prompt and any Credential Manager prompt. They are set in this process, which is
# the caller's session under .\install.ps1, so each one's earlier value is put back
# (or the variable removed) as soon as git returns.
function Test-ReleaseTag {
    if ($SourceKind -ne 'tag') {
        return
    }
    $ErrorActionPreference = 'Continue'
    $savedPrompt = [Environment]::GetEnvironmentVariable('GIT_TERMINAL_PROMPT')
    $savedGcm = [Environment]::GetEnvironmentVariable('GCM_INTERACTIVE')
    $code = 1
    try {
        $env:GIT_TERMINAL_PROMPT = '0'
        $env:GCM_INTERACTIVE = 'never'
        & $GitExe -c 'credential.helper=' ls-remote --exit-code --tags $RepoUrl ('refs/tags/v' + $Version) *> $null
        $code = $LASTEXITCODE
    } finally {
        Restore-EnvVar 'GIT_TERMINAL_PROMPT' $savedPrompt
        Restore-EnvVar 'GCM_INTERACTIVE' $savedGcm
    }
    if ($code -ne 0) {
        Fail ('install.ps1: the release tag v' + $Version + ' could not be fetched from ' + $RepoUrl + ' (it is missing, or GitHub cannot be reached); check the network and run this installer again, or pass -From <a checkout or an unpacked download>.') 3
    }
}
Test-ReleaseTag

# ---- paths (joined from the environment, never resolved) -------------------
$AppData = $env:APPDATA
if ([string]::IsNullOrEmpty($AppData)) {
    $AppData = $HomeDir + '\AppData\Roaming'
}
$LocalAppData = $env:LOCALAPPDATA
if ([string]::IsNullOrEmpty($LocalAppData)) {
    $LocalAppData = $HomeDir + '\AppData\Local'
}
$CfgDir = $AppData + '\tutor-any-lecture'
$CliPathFile = $CfgDir + '\cli-path'
$Venv = $LocalAppData + '\tutor-any-lecture\venv'
$VenvPy = $Venv + '\Scripts\python.exe'
$VenvCli = $Venv + '\Scripts\tutor-any-lecture.exe'
$script:Cli = ''

# ---- steps: each takes 'plan' (print a PLAN: line) or 'run' (do it) ---------
# The dry run, the confirmation prompt and the real run all go through these
# functions, so the printed plan and the real run cannot drift apart.

# Where a skill copy installs from when that is the default branch: the plan's
# first line, and the real run's first line.
function Show-SourceNote([string]$Mode) {
    if ($SourceKind -eq 'dev') {
        if ($Mode -eq 'plan') {
            Say ('PLAN: install from the default branch (VERSION ' + $Version + ' is a development version, which is never tagged)')
        } else {
            Say ('Installing from the default branch: VERSION ' + $Version + ' is a development version, which is never tagged.')
        }
    } elseif ($SourceKind -eq 'none') {
        if ($Mode -eq 'plan') {
            Say 'PLAN: install from the default branch (the skill folder has no release id in VERSION)'
        } else {
            Say 'Installing from the default branch: the skill folder has no release id in VERSION.'
        }
    }
}

# The two optional flags, as the plan's next lines.
function Show-Options {
    if ($WithAsr) {
        Say 'PLAN: -WithAsr on (speech recognition is installed)'
    } else {
        Say 'PLAN: -WithAsr off (no speech recognition; add it for audio or video without captions)'
    }
    if ($CliOnly) {
        Say 'PLAN: -CliOnly on (the command only; no skill folder is copied)'
    } else {
        Say 'PLAN: -CliOnly off'
    }
}

# Steps 1 and 2: install the CLI with uv, or into a private venv. Both always
# rebuild, so a reinstall from an updated checkout never keeps the old build.
function Install-Cli([string]$Mode) {
    if ($Method -eq 'uv') {
        if ($Mode -eq 'plan') {
            Say ('PLAN: uv tool install --force --reinstall "' + $InstallSpec + '"')
            return
        }
        Invoke-Native "'uv tool install --force --reinstall $InstallSpec'" 'uv' @('tool', 'install', '--force', '--reinstall', $InstallSpec)
        $ErrorActionPreference = 'Continue'
        # uv prints UTF-8; read it as UTF-8 so a non-ASCII user folder survives.
        $saved = [Console]::OutputEncoding
        try {
            try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch { }
            $binOut = & uv tool dir --bin
            $code = $LASTEXITCODE
        } finally {
            try { [Console]::OutputEncoding = $saved } catch { }
        }
        if ($code -ne 0) {
            Fail "install.ps1: 'uv tool dir --bin' failed (exit code $code)." 1
        }
        $binDir = ([string](@($binOut) | Select-Object -Last 1)).Trim()
        $script:Cli = $binDir + '\tutor-any-lecture.exe'
    } else {
        if ($Mode -eq 'plan') {
            Say "PLAN: python -m venv $Venv"
            Say ('PLAN: ' + $VenvPy + ' -m pip install --upgrade --force-reinstall "' + $InstallSpec + '"')
            return
        }
        Invoke-Native "creating the venv at $Venv" $PyExe ($PyPrefix + @('-m', 'venv', $Venv))
        Invoke-Native "'pip install --upgrade --force-reinstall $InstallSpec'" $VenvPy @('-m', 'pip', 'install', '--upgrade', '--force-reinstall', $InstallSpec)
        $script:Cli = $VenvCli
    }
}

# Step 4: record the CLI's full path in <config dir>\cli-path (UTF-8, no BOM, LF).
function Write-CliPath([string]$Mode) {
    if ($Mode -eq 'plan') {
        Say "PLAN: write $CliPathFile"
        return
    }
    if (-not (Test-Path -LiteralPath $script:Cli -PathType Leaf)) {
        Fail "install.ps1: the command was not found at $($script:Cli) after the install." 1
    }
    try {
        [void][System.IO.Directory]::CreateDirectory($CfgDir)
        [System.IO.File]::WriteAllText($CliPathFile, $script:Cli + "`n", (New-Object System.Text.UTF8Encoding($false)))
    } catch {
        Fail "install.ps1: could not write $CliPathFile." 1
    }
    Say "Recorded $($script:Cli) in $CliPathFile"
}

# The physical path of a folder: a symlink or junction is followed one level.
function Get-PhysicalPath([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    $resolved = $item.FullName
    if ($item.LinkType -and $item.Target) {
        $linkTarget = [string](@($item.Target)[0])
        if (-not [System.IO.Path]::IsPathRooted($linkTarget)) {
            $linkTarget = Join-Path (Split-Path -Parent $item.FullName) $linkTarget
        }
        $resolved = [System.IO.Path]::GetFullPath($linkTarget)
    }
    return $resolved.TrimEnd('\', '/')
}

# True when the target exists and is the skill source folder (letter case ignored).
function Test-SameAsSource([string]$Target) {
    if (-not (Test-Path -LiteralPath $Target -PathType Container)) {
        return $false
    }
    try {
        $physical = Get-PhysicalPath $Target
    } catch {
        return $false
    }
    return ($physical -ieq $SkillSrc.TrimEnd('\', '/'))
}

# Step 5: copy the skill folder to each agent (nothing with -CliOnly).
function Copy-Skills([string]$Mode) {
    if ($CliOnly) {
        return
    }
    if ($AgentNames.Count -eq 0) {
        if ($Mode -eq 'plan') {
            Say 'PLAN: skip copying skills (no agent folder found; use -Agents claude,codex,agents)'
        } else {
            Say 'Note: no agent folder found (.claude, .codex, .agents in your user folder), so the skill was not copied; use -Agents claude,codex,agents to choose.'
        }
        return
    }
    foreach ($name in $AgentNames) {
        $skillsDir = $HomeDir + '\.' + $name + '\skills'
        $target = $skillsDir + '\tutor-any-lecture'
        if (Test-SameAsSource $target) {
            if ($Mode -eq 'plan') {
                Say "PLAN: skip $target (same folder as the skill source)"
            } else {
                Say "skip $target (same folder as the skill source)"
            }
            continue
        }
        if ($Mode -eq 'plan') {
            Say "PLAN: copy $SkillSrc to $target"
            continue
        }
        try {
            [void][System.IO.Directory]::CreateDirectory($skillsDir)
            # Only a path named exactly <agent home>\skills\tutor-any-lecture is
            # removed. A symlink or junction is removed as a link (a file symlink
            # as a file); what it points to is left alone.
            $old = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
            if ($old) {
                if ($old.LinkType -and $old.PSIsContainer) {
                    [System.IO.Directory]::Delete($target)
                } elseif ($old.LinkType) {
                    [System.IO.File]::Delete($target)
                } elseif ($old.PSIsContainer) {
                    Remove-Item -LiteralPath $target -Recurse -Force
                } else {
                    Remove-Item -LiteralPath $target -Force
                }
            }
            Copy-Item -LiteralPath $SkillSrc -Destination $target -Recurse -Force
        } catch {
            Fail "install.ps1: could not copy the skill to $target." 1
        }
        Say "Copied the skill to $target"
    }
}

# The line that runs a CLI's selftest, for pasting into PowerShell: the call
# operator and the path in single quotes, each single quote doubled (the curly
# ones too, which PowerShell also reads as single quotes).
function Get-SelftestCommand([string]$CliPath) {
    $quoted = $CliPath
    foreach ($q in @([string][char]0x27, [string][char]0x2018, [string][char]0x2019, [string][char]0x201A, [string][char]0x201B)) {
        $quoted = $quoted.Replace($q, $q + $q)
    }
    return "& '" + $quoted + "' selftest"
}

# Step 8: the last line, so the command can be reached even when it is not on PATH.
# The dry run never runs uv, so the plan names uv's bin folder in words.
function Show-SelftestCommand([string]$Mode) {
    if ($Mode -eq 'plan') {
        if ($Method -eq 'uv') {
            $planned = '<uv tool bin folder>\tutor-any-lecture.exe'
        } else {
            $planned = $VenvCli
        }
        Say ('PLAN: print the selftest command: ' + (Get-SelftestCommand $planned))
    } else {
        Say (Get-SelftestCommand $script:Cli)
    }
}

function Show-Plan {
    Show-SourceNote 'plan'
    Show-Options
    Install-Cli 'plan'
    Write-CliPath 'plan'
    Copy-Skills 'plan'
    Say 'PLAN: run tutor-any-lecture doctor --json'
    Show-SelftestCommand 'plan'
}

# ---- dry run ---------------------------------------------------------------
if ($DryRun) {
    Show-Plan
    Exit-Installer 0
}

# ---- confirmation (only with a terminal and without -Yes) ------------------
if ((-not $Yes) -and (-not [Console]::IsInputRedirected)) {
    Show-Plan
    [Console]::Out.Write('Proceed? [y/N] ')
    $answer = [Console]::In.ReadLine()
    if ($null -eq $answer) {
        $answer = ''
    }
    $answer = $answer.Trim().ToLowerInvariant()
    if (($answer -ne 'y') -and ($answer -ne 'yes')) {
        Say 'Nothing was changed.'
        Exit-Installer 1
    }
}

# ---- real run --------------------------------------------------------------
Show-SourceNote 'run'
Install-Cli 'run'
Write-CliPath 'run'
Copy-Skills 'run'
# Steps 6 and 7: run doctor by its full path; its JSON line is the second-to-last
# stdout line, and its exit code (0 ready, 3 not ready) is ours.
$ErrorActionPreference = 'Continue'
& $script:Cli doctor --json
$code = $LASTEXITCODE
# Step 8: the selftest command, whatever doctor said.
Show-SelftestCommand 'run'
Exit-Installer $code
