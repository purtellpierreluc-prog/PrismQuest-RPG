import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DesktopPaths:
    resources: Path
    data: Path

    @classmethod
    def from_environment(cls):
        resources = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])).resolve()
        override = os.environ.get('PRISMQUEST_DATA_DIR')
        if override:
            data = Path(override).expanduser().resolve()
        elif sys.platform == 'win32':
            data = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'PrismQuest' / 'SteamEditionVisual'
        else:
            data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local' / 'share')) / 'prismquest-steam-visual'
        return cls(resources, data.resolve())

    def prepare(self):
        for directory in (self.data, self.cache, self.logs, self.browser, self.saves, self.backups):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def cache(self):
        return self.data / 'cache'

    @property
    def logs(self):
        return self.data / 'logs'

    @property
    def browser(self):
        return self.data / 'browser'

    @property
    def saves(self):
        return self.data / 'saves'

    @property
    def backups(self):
        return self.data / 'backups'

    @property
    def save_file(self):
        return self.saves / 'chronicles.json'
