<#
    Build the Windows desktop bundle. Output lands in out/DeathliteGame/ beside
    this script (gitignored). The web build's equivalent is ../web/build.sh.

    Usage, from anywhere:
        powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1
        powershell -ExecutionPolicy Bypass -File dist\desktop\build.ps1 -Zip

    -Zip also produces out/DeathliteGame-<version>.zip, which is the thing
    you actually hand to someone: they unzip it anywhere and run the exe.
#>
[CmdletBinding()]
param(
    [switch]$Zip,          # also package out/ as a versioned ZIP
    [switch]$KeepWork,     # keep the intermediate work dir for debugging
    [switch]$Console       # diagnostic build with a console -> out-console/
)

$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path      # dist/desktop
$root = Split-Path -Parent (Split-Path -Parent $here)        # repo root
$spec = Join-Path $here "DeathliteGame.spec"

# Build from .venv, never the system Python. That venv holds only pygame and the
# build tools -- the system Python has numpy, which would otherwise be a
# candidate for the bundle. (It also has pytest; the suite runs there, not here.)
$py = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    throw "No .venv at $py -- create it and 'pip install pygame pyinstaller' first."
}

# PyInstaller's default work directory is '<repo>/build/', which the pygbag web
# build owns (build/web, build/web-cache). Keep the intermediates here instead.
$work = Join-Path $here "work"

# A -Console build goes to its own output folder so it can never be mistaken
# for, or overwrite, the real one. The spec reads DLG_CONSOLE at build time; a windowed
# build has no stdout at all, so this is the only way to read the startup log
# (which save path it resolved, whether vsync was refused, missing assets).
if ($Console) {
    $dist = Join-Path $here "out-console"
    $env:DLG_CONSOLE = "1"
} else {
    $dist = Join-Path $here "out"
}

Write-Host "python : $py"
Write-Host "spec   : $spec"
Write-Host "dist   : $dist"
if ($Console) { Write-Host "mode   : CONSOLE (diagnostic)" }
Write-Host ""

try {
    & $py -m PyInstaller --noconfirm --clean --workpath $work --distpath $dist $spec
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed with exit code $LASTEXITCODE" }
} finally {
    Remove-Item Env:\DLG_CONSOLE -ErrorAction SilentlyContinue
}

if (-not $KeepWork) {
    if (Test-Path $work) { Remove-Item -Recurse -Force $work }
}

$out = Join-Path $dist "DeathliteGame"
$exe = Join-Path $out "DeathliteGame.exe"
if (-not (Test-Path $exe)) { throw "Build reported success but $exe is missing." }

$bytes = (Get-ChildItem -Recurse -File $out | Measure-Object -Property Length -Sum).Sum
$files = (Get-ChildItem -Recurse -File $out | Measure-Object).Count
Write-Host ""
Write-Host ("built  : {0}" -f $out)
Write-Host ("size   : {0:N1} MB across {1:N0} files" -f ($bytes / 1MB), $files)

if ($Zip -and -not $Console) {
    # Read the version straight from config.py so the ZIP name cannot drift.
    $cfg = Get-Content (Join-Path $root "game\config.py") -Raw
    $m = [regex]::Match($cfg, 'VERSION:\s*str\s*=\s*"([^"]+)"')
    if ($m.Success) { $ver = $m.Groups[1].Value } else { $ver = "unknown" }

    $zipPath = Join-Path $dist ("DeathliteGame-{0}.zip" -f $ver)
    if (Test-Path $zipPath) { Remove-Item -Force $zipPath }

    # .NET's zipper rather than Compress-Archive: the cmdlet walks the tree
    # opening every file itself and fails the whole archive if anything else has
    # one open -- which an antivirus scanning a freshly written _internal\ will.
    # Seen exactly that on `base_library.zip` the first time this ran. This path
    # is also several times faster on a few hundred files.
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $out, $zipPath, [System.IO.Compression.CompressionLevel]::Optimal, $true)

    $zipMb = (Get-Item $zipPath).Length / 1MB
    Write-Host ("zipped : {0} ({1:N1} MB)" -f $zipPath, $zipMb)
}
