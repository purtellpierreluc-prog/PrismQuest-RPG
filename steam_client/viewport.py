"""Desktop-only presentation assets; no changes to combat or save semantics."""

from nicegui import ui


def install_desktop_styles(paths):
    assets = paths.resources / 'steam_client' / 'static'
    ui.add_head_html('<style>' + (assets / 'desktop.css').read_text(encoding='utf-8') + '</style>', shared=True)
    ui.add_head_html('<script>' + (assets / 'desktop.js').read_text(encoding='utf-8') + '</script>', shared=True)
