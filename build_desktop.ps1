$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Create .venv and install requirements-dev.txt before building.'
    }
    & $python -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency validation failed.' }
    & $python -m ruff check steam_client launch_desktop.py tests/test_desktop.py tests/test_display.py tests/test_build.py tests/test_transport.py tests/conftest.py tools
    if ($LASTEXITCODE -ne 0) { throw 'Desktop lint checks failed.' }
    & $python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
    & $python -m PyInstaller --noconfirm PrismQuestDesktop.spec
    if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
    & $python tools/build_manifest.py dist/PrismQuest
    if ($LASTEXITCODE -ne 0) { throw 'Build inventory generation failed.' }
    Write-Output 'Build ready: dist\PrismQuest\PrismQuest.exe'
} finally {
    Pop-Location
}
