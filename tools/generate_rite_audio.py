"""Original sustained rite cues; earlier versioned audio remains immutable."""

import array
import json
from pathlib import Path

from generate_audio import add, chime, write_wav

ROOT = Path(__file__).resolve().parents[1]
RATE = 22050


def generate():
    folder = ROOT/'steam_client/static/audio/v3'
    folder.mkdir(parents=True, exist_ok=True)
    sounds = {
        'rite_listen':chime([(110,0,.45),(146.83,.45,.35),(220,1.05,.30),(293.66,1.8,.18),(311.13,2.25,.1)],2.9,.12),
        'rite_unseal':chime([(220,0,.28),(293.66,.25,.35),(440,.65,.28),(587.33,1.05,.15)],1.6,.12),
        'rite_ascend':chime([(146.83,0,.6),(293.66,.35,.5),(349.23,.65,.44),(440,1.1,.48),(523.25,1.55,.4),(698.46,2.05,.28),(880,2.8,.20),(1046.5,3.45,.13)],6.8,.17),
        'rite_complete':chime([(146.83,0,.6),(220,.4,.42),(293.66,.75,.50),(369.99,1.1,.46),(440,1.55,.40),(554.37,2,.35),(659.25,2.5,.28),(880,3.1,.22),(1174.66,4.15,.13)],8.2,.17),
    }
    manifest = {'version':3,'origin':'Original procedural PrismQuest synthesis; no external recordings or samples.','files':{}}
    for name, samples in sounds.items():
        manifest['files'][name] = write_wav(folder/f'{name}.wav',samples)
    (folder/'manifest.json').write_text(json.dumps(manifest,sort_keys=True,indent=2),encoding='utf-8')
    preview = array.array('f',[0])*(15*RATE)
    add(preview,sounds['rite_listen'],0,.8)
    add(preview,sounds['rite_unseal'],round(3.2*RATE),.8)
    add(preview,sounds['rite_ascend'],round(5.2*RATE),.8)
    write_wav(folder.parent/'prismatic-rite-preview.wav',preview)
    print(json.dumps({name:round(info['peak'],4) for name,info in manifest['files'].items()}))


if __name__ == '__main__':
    generate()
