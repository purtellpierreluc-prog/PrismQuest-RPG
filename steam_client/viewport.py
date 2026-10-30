"""Desktop-only presentation assets; no changes to combat or save semantics."""

import json

from nicegui import app, ui


def install_desktop_styles(paths, audio_preferences=None):
    assets = paths.resources / 'steam_client' / 'static'
    app.add_static_files('/desktop-ui', assets, max_cache_age=31536000)
    ui.add_head_html('<script>document.documentElement.dataset.pqNocturne="true";</script>', shared=True)
    ui.add_head_html('<style>' + (assets / 'desktop.css').read_text(encoding='utf-8') + '</style>', shared=True)
    ui.add_body_html('<style>' + (assets / 'nocturne.css').read_text(encoding='utf-8') + '</style>', shared=True)
    ui.add_body_html('<style>' + (assets / 'experience.css').read_text(encoding='utf-8') + '</style>', shared=True)
    ui.add_head_html('<script>' + (assets / 'desktop.js').read_text(encoding='utf-8') + '</script>', shared=True)
    ui.add_head_html('<script>' + (assets / 'inspections.js').read_text(encoding='utf-8') + '</script>', shared=True)
    ui.add_head_html('<script>window.pqAudioInitial=' + json.dumps(audio_preferences or {}) + ';</script>', shared=True)
    ui.add_head_html('<script>' + (assets / 'audio.js').read_text(encoding='utf-8') + '</script>', shared=True)
