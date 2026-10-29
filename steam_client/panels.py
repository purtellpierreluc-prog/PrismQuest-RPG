"""Desktop controls live outside the legacy game's renderer."""

import json
import os

from nicegui import ui

from . import __version__


def render_audio_settings(audio, refresh):
    prefs = audio.preferences

    def changed(key, value):
        audio.set(key, value)
        ui.run_javascript('window.PrismAudio && window.PrismAudio.configure(' + json.dumps(audio.payload()) + ');')

    with ui.card().classes('mq-card pd-audio-panel w-full p-5'):
        with ui.row().classes('w-full items-center justify-between gap-4'):
            with ui.column().classes('gap-1'):
                ui.label('A Quiet Soundscape').classes('mq-inv-title')
                ui.label('Soft combat textures. Crystalline discoveries. Space to think.').classes('mq-detail-text')
            ui.checkbox('Mute all audio', value=prefs.muted, on_change=lambda e: changed('muted', e.value))
        with ui.element('div').classes('pd-audio-mix'):
            for key, title, description in [
                ('effects_volume', 'Sound Effects', 'Combat is sparse and softer than level-up and discovery chimes.'),
                ('music_volume', 'Background Music', 'A slowly moving, original ambient score. No busy percussion.')]:
                with ui.element('section').classes('pd-audio-channel'):
                    with ui.row().classes('w-full items-center justify-between'):
                        ui.label(title).classes('mq-inv-section-title')
                        value_label = ui.label(f'{getattr(prefs, key)}%').classes('pd-audio-value')

                    def volume_changed(event, field=key, label=value_label):
                        changed(field, event.value)
                        label.set_text(f'{audio.payload()[field]}%')

                    ui.slider(min=0, max=100, step=1, value=getattr(prefs, key), on_change=volume_changed).props(f'aria-label="{title} Volume"').classes('w-full')
                    ui.label(description).classes('mq-detail-text')
        with ui.element('div').classes('pd-audio-toggles'):
            for key, caption in [('music_enabled', 'Enable ambient music'), ('combat_enabled', 'Enable combat effects'),
                                 ('rewards_enabled', 'Enable reward chimes'), ('mute_unfocused', 'Mute when unfocused')]:
                ui.checkbox(caption, value=getattr(prefs, key), on_change=lambda e, field=key: changed(field, e.value))
        with ui.row().classes('gap-2 flex-wrap'):
            for name, caption in [('level', 'Test Level-up'), ('find_rare', 'Test Rare Find'), ('impact', 'Test Combat')]:
                ui.button(caption).classes('mq-btn-secondary').on('click', js_handler=f'() => window.PrismAudio && window.PrismAudio.preview({json.dumps(name)})')

            def reset():
                audio.reset()
                ui.run_javascript('window.PrismAudio && window.PrismAudio.configure(' + json.dumps(audio.payload()) + ');')
                refresh()

            ui.button('Restore Quiet Defaults', on_click=reset).classes('mq-btn-secondary')
        ui.html('<output id="pq-audio-status" role="status" aria-live="polite"></output>')
        ui.label('Plays locally after your first interaction. Settings are saved per desktop profile, not per character.').classes('pd-comparison-note')


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
