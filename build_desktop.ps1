$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        throw 'Create .venv and install requirements-dev.txt before building.'
    }
    & $python -m ruff check steam_client launch_desktop.py tests/test_desktop.py tests/conftest.py tools/desktop_browser_smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'Desktop lint checks failed.' }
    & $python -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { throw 'Regression tests failed.' }
    & $python -m PyInstaller --noconfirm PrismQuestDesktop.spec
    if ($LASTEXITCODE -ne 0) { throw 'Desktop packaging failed.' }
    Write-Output 'Build ready: dist\PrismQuest\PrismQuest.exe'
} finally {
    Pop-Location
}
