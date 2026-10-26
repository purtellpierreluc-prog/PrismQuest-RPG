"""Desktop controls live outside the legacy game's renderer."""

import os

from nicegui import ui

from . import __version__


def render_desktop_settings(display, paths, save_store, flush_save):
    with ui.card().classes('mq-card w-full p-5'):
        ui.label('Desktop Display').classes('mq-inv-section-title')
        ui.label('The game fits the client window. Long item lists and reference panels scroll inside their own containers.').classes('mq-detail-text')
        button = ui.button('Toggle Fullscreen (F11)', on_click=display.toggle_fullscreen).classes('mq-btn-gold rounded-xl px-5 py-3')
        if not display.available:
            button.disable()
            ui.label('Native display controls are available in the desktop executable, not browser diagnostic mode.').classes('mq-detail-text')
        ui.label('Window size and fullscreen preference are remembered between launches.').classes('mq-detail-text')
        def motion_changed(event):
            display.set_reduce_motion(event.value)
            ui.run_javascript(f'document.documentElement.dataset.mqReducedMotion = {str(bool(event.value)).lower()!r}')
        ui.checkbox('Reduce decorative motion', value=display.preferences.reduce_motion, on_change=motion_changed)
        ui.label('Disables decorative pulses, shimmer, and reveal animations without changing combat timing. Your operating-system reduced-motion preference is also respected.').classes('mq-detail-text')
    with ui.card().classes('mq-card w-full p-5'):
        ui.label('Local Saves & Recovery').classes('mq-inv-section-title')
        ui.label('Automatic saves remain outside the install folder. Manual backups are kept separately from the ten rotating recovery copies.').classes('mq-detail-text')

        def backup():
            try:
                flush_save()
                target = save_store.create_manual_backup()
                ui.notify(f'Backup created: {target.name}', type='positive')
            except (OSError, ValueError, TypeError, RuntimeError):
                ui.notify('The backup could not be created. Your existing save was not removed; check the desktop log.', type='negative')
                import logging
                logging.getLogger(__name__).exception('Manual desktop save backup failed.')

        def open_saves():
            if os.name == 'nt':
                try:
                    os.startfile(str(paths.saves))
                except OSError:
                    ui.notify(f'Open this folder: {paths.saves}', type='warning')

        def diagnostics():
            from .diagnostics import write_diagnostics
            try:
                target = write_diagnostics(paths, save_store)
                ui.notify(f'Local diagnostic report created: {target.name}. No character or account data was included.', type='positive', timeout=10000)
            except OSError:
                ui.notify('Could not write diagnostics; check available disk space.', type='negative')

        with ui.row().classes('gap-2'):
            ui.button('Create Manual Backup', on_click=backup).classes('mq-btn-gold rounded-xl px-5 py-3')
            ui.button('Open Save Folder', on_click=open_saves).classes('mq-btn-secondary rounded-xl px-5 py-3')
            ui.button('Export Local Diagnostics', on_click=diagnostics).classes('mq-btn-secondary rounded-xl px-5 py-3')
        ui.label(str(paths.saves)).classes('mq-detail-text break-all')
    with ui.card().classes('mq-card w-full p-4'):
        ui.label(f'PrismQuest Desktop {__version__}').classes('mq-panel-caption')
        ui.label('Offline development build. Steam achievements, Steam Cloud, and online multiplayer are not integrated yet.').classes('mq-detail-text')
