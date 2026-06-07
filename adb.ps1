param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$adbDir = "C:\Users\Charles\AppData\Local\Android\Sdk\platform-tools"
$adbExe = Join-Path $adbDir "adb.exe"

if (-not (Test-Path $adbExe)) {
    Write-Error "adb not found at $adbExe"
    exit 1
}

if ($env:Path -notlike "*$adbDir*") {
    $env:Path = "$adbDir;$env:Path"
}

& $adbExe @ArgsList
exit $LASTEXITCODE
