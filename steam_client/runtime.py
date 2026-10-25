import argparse
import asyncio
import importlib.util
import logging
import os
import secrets
import sys
import traceback
from logging.handlers import RotatingFileHandler

from . import __version__
from .paths import DesktopPaths
from .storage import AtomicSaveStore, SingleInstance


def report_startup_error(error):
    detail = ''.join(traceback.format_exception(error))
    message = f'PrismQuest could not start.\n\n{error}\n\nYour existing save files have not been deleted.'
    try:
        paths = DesktopPaths.from_environment()
        paths.logs.mkdir(parents=True, exist_ok=True)
        report = paths.logs / 'startup-error.log'
        report.write_text(detail, encoding='utf-8')
        message += f'\n\nDetails: {report}'
    except OSError:
        pass
    if sys.stderr is not None:
        print(detail, file=sys.stderr)
    if sys.platform == 'win32' and '--browser' not in sys.argv and '--native-smoke' not in sys.argv:
        import ctypes
        ctypes.windll.user32.MessageBoxW(None, message, 'PrismQuest Startup', 0x10)


def load_game(paths):
    source = paths.resources / 'PrismQuest_RPG_v1.01.py'
    spec = importlib.util.spec_from_file_location('prismquest_game', source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def launch(argv=None):
    parser = argparse.ArgumentParser(description='PrismQuest standalone desktop prototype')
    parser.add_argument('--browser', action='store_true', help='Run the local UI without opening a native window.')
    parser.add_argument('--port', type=int, default=0, help='Local development port; 0 selects a free port.')
    parser.add_argument('--data-dir', help='Use a separate writable local profile directory.')
    parser.add_argument('--native-smoke', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--version', action='version', version=f'PrismQuest Steam Prototype {__version__}')
    args = parser.parse_args(argv)
    if args.data_dir:
        os.environ['PRISMQUEST_DATA_DIR'] = args.data_dir
    paths = DesktopPaths.from_environment()
    paths.prepare()
    os.environ['PRISMQUEST_DATA_DIR'] = str(paths.data)
    instance = SingleInstance(paths.data / 'desktop.lock').acquire()
    handler = None
    try:
        # Never inherit production cloud credentials into a local desktop save.
        os.environ['PRISMQUEST_DESKTOP'] = '1'
        os.environ['SUPABASE_URL'] = ''
        os.environ['SUPABASE_PUBLISHABLE_KEY'] = ''
        os.environ['NICEGUI_STORAGE_PATH'] = str(paths.data / 'ui')
        secret_file = paths.data / 'session.key'
        if not secret_file.exists():
            secret_file.write_text(secrets.token_urlsafe(48), encoding='ascii')
        handler = RotatingFileHandler(paths.logs / 'desktop.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s'))
        logging.getLogger().addHandler(handler)
        logging.getLogger().setLevel(logging.INFO)
        AtomicSaveStore(paths.save_file, paths.backups).load()
        game = load_game(paths)
        from nicegui import app, native, ui
        app.on_shutdown(game.flush_desktop_save)
        if not args.browser:
            app.native.start_args.update(gui='edgechromium', private_mode=False, storage_path=str(paths.browser))
            app.native.window_args.update(min_size=(960, 640), text_select=True)
            if args.native_smoke:
                app.native.window_args['hidden'] = True
                async def native_loaded():
                    await asyncio.sleep(2)
                    (paths.data / 'native-smoke.ok').write_text('Native WebView2 window loaded.', encoding='utf-8')
                    app.shutdown()
                app.native.on('loaded', native_loaded)
                async def native_timeout():
                    await asyncio.sleep(30)
                    app.shutdown()
                app.on_startup(lambda: asyncio.create_task(native_timeout()))
        ui.run(
            title=f'PrismQuest - Steam Prototype {__version__}',
            host='127.0.0.1', port=args.port or native.find_open_port(),
            native=not args.browser,
            window_size=None if args.browser else (1360, 900),
            show=False, reload=False, dark=True, reconnect_timeout=30.0,
            binding_refresh_interval=0.25,
            storage_secret=secret_file.read_text(encoding='ascii'),
        )
    finally:
        if handler is not None:
            logging.getLogger().removeHandler(handler)
            handler.close()
        instance.release()
