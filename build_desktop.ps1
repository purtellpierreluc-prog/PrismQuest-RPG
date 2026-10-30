$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Create .venv and install requirements-dev.txt before building.'
    }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
    & $python -m ruff check steam_client launch_desktop.py tests/test_*.py tests/conftest.py tools
    if ($LASTEXITCODE -ne 0) { throw 'Desktop lint checks failed.' }
    $testRoot = Join-Path $PSScriptRoot ('.local-test\pytest-build-' + [guid]::NewGuid().ToString('N'))
    if (-not ([System.IO.Path]::GetFullPath($testRoot)).StartsWith($PSScriptRoot + [System.IO.Path]::DirectorySeparatorChar)) { throw 'Test path escaped the workspace.' }
    & $python -m pytest tests -q --basetemp $testRoot
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
    $outputExe = Join-Path $PSScriptRoot 'dist\PrismQuest\PrismQuest.exe'
    $runningBuild = Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -eq $outputExe }
    if ($runningBuild) {
        throw 'Close the running PrismQuest game normally before rebuilding. Its installed files have not been replaced.'
    }
    & $python -m PyInstaller --noconfirm PrismQuestDesktop.spec
    if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
    & $python tools/release_audit.py --directory dist/PrismQuest
    if ($LASTEXITCODE -ne 0) { throw 'Release inventory generation failed.' }
    & $python tools/build_manifest.py dist/PrismQuest
    if ($LASTEXITCODE -ne 0) { throw 'Build inventory generation failed.' }
    Write-Output 'Build ready: dist\PrismQuest\PrismQuest.exe'
} finally {
    Pop-Location
}
