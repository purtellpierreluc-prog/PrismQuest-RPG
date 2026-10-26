from pathlib import Path
import sysconfig
from PyInstaller.utils.hooks import collect_all

root = Path(SPECPATH)
nicegui_data, nicegui_binaries, nicegui_hidden = collect_all('nicegui', include_py_files=False)
webview_data, webview_binaries, webview_hidden = collect_all('webview', include_py_files=False)
# Some Python distributions provide TLS policy resources alongside ssl.py.
tls_data = [(str(path), '.') for path in Path(sysconfig.get_path('stdlib')).glob('*.pem')]

a = Analysis(
    [str(root / 'launch_desktop.py')],
    pathex=[str(root)],
    binaries=nicegui_binaries + webview_binaries,
    datas=nicegui_data + webview_data + tls_data + [
        (str(root / 'PrismQuest_RPG_v1.01.py'), '.'),
        (str(root / 'Assets'), 'Assets'),
        (str(root / 'steam_client' / 'static'), 'steam_client/static'),
    ],
    hiddenimports=nicegui_hidden + webview_hidden + ['PIL.Image', 'uvicorn.logging', 'clr_loader', 'steam_client.panels'],
    excludes=['pytest', 'playwright', 'ruff', 'supabase', 'nicegui.testing'],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name='PrismQuest', debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, version=str(root / 'steam_client' / 'windows_version.txt'),
)
collect = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='PrismQuest')
