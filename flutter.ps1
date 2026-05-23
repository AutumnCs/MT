$flutterBin = "G:\dev\flutter\bin"
$flutterExe = Join-Path $flutterBin "flutter.bat"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$gradleHome = Join-Path $projectRoot ".gradle-home"
$tempRoot = Join-Path $projectRoot ".tmp"

if (-not (Test-Path $flutterExe)) {
    Write-Error "Flutter SDK not found at $flutterBin"
    exit 1
}

foreach ($dir in @($gradleHome, $tempRoot)) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

if ($env:Path -notlike "*$flutterBin*") {
    $env:Path = "$flutterBin;$env:Path"
}

$env:GRADLE_USER_HOME = $gradleHome
$env:TEMP = $tempRoot
$env:TMP = $tempRoot

if ($args.Count -eq 0) {
    & $flutterExe doctor
    exit $LASTEXITCODE
}

& $flutterExe @args
exit $LASTEXITCODE
