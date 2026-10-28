"""Presentation-only identity for the Nocturne visual fork."""

import html

SCENE_NAMES = {
    'arena': 'The Arena', 'labyrinth': 'Labyrinth of Light',
    'marketplace': 'The Exchange', 'well': 'Well of Evil', 'inn': 'The Wayfarer\'s Inn',
    'transmute': 'The Crucible', 'inventory': 'The Armory', 'settings': 'Field Settings',
    'ladder': 'Chronicle Records', 'glossary': 'The Codex', 'stats': 'Character',
    'masterquest': 'Prismatic Quest', 'profile': 'Adventurer',
}

PRISM_MARK = '''<svg class="pq-prism-mark" viewBox="0 0 40 48" aria-hidden="true">
<path d="M20 2 37 15v18L20 46 3 33V15Z"/><path d="m20 2 9 22-9 22-9-22Z"/>
<path d="m3 15 17 9 17-9M3 33l17-9 17 9"/></svg>'''


def scene_heading(scene, player_class, level, mode):
    title = SCENE_NAMES.get(scene, str(scene).replace('_', ' ').title())
    return (f'<div class="pq-scene-identity">{PRISM_MARK}<div class="pq-scene-copy">'
            f'<div class="pq-eyebrow">{html.escape(str(mode))} CHRONICLE <span>/</span> '
            f'{html.escape(str(player_class))} <span>/</span> LV {int(level)}</div>'
            f'<div class="pq-scene-title">{html.escape(title)}</div></div></div>')
