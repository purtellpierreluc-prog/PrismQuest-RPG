"""Original, quiet chapter cues; no recordings, third-party samples or voices."""

import argparse
import array
import json
import math
from pathlib import Path

from generate_audio import add, chime, write_wav

ROOT = Path(__file__).resolve().parents[1]
RATE = 22050


def bed():
    seconds = 16
    output = array.array('f')
    for i in range(seconds*RATE):
        t = i/RATE
        swell = .7 + .3*math.cos(2*math.pi*t/seconds)
        tone = sum(weight*math.sin(2*math.pi*cycles*t/seconds+phase) for cycles,weight,phase in
                   [(1175,.025,0),(1760,.017,.4),(2349,.010,.8),(3520,.006,.3),(4978,.0015,1.2)])
        output.append(tone*swell)
    return output


def generate(directory):
    directory.mkdir(parents=True,exist_ok=True)
    sounds = {
        'story_threshold':chime([(146.83,0,.5),(220,.35,.3),(311.13,.9,.13),(293.66,1.5,.23)],4.4,.13),
        'story_judging':chime([(146.83,0,.6),(220,.25,.32),(311.13,.7,.10)],1.35,.09),
        'story_binding':chime([(293.66,0,.5),(440,.14,.45),(587.33,.4,.26)],1.9,.13),
        'story_fracture':chime([(220,0,.40),(174.61,.3,.35),(146.83,.65,.23)],3.4,.12),
        'story_ascend':chime([(146.83,0,.6),(349.23,.18,.5),(440,.42,.46),(523.25,.75,.4),(698.46,1.15,.27),(880,1.65,.17)],5.4,.18),
        'story_complete':chime([(146.83,0,.7),(293.66,.18,.6),(369.99,.45,.48),(440,.7,.4),(554.37,1,.35),(659.25,1.5,.27),(880,2,.18)],7,.18),
        'story_purchase':chime([(659.25,0,.45),(880,.11,.25)],1.25,.13),
        'prism_bed':bed(),
    }
    report = {'version':2,'origin':'Original procedural PrismQuest synthesis; no external recordings or samples.','files':{}}
    for name, samples in sounds.items():
        report['files'][name] = write_wav(directory/f'{name}.wav', samples, loop=name=='prism_bed')
    (directory/'manifest.json').write_text(json.dumps(report,indent=2,sort_keys=True),encoding='utf-8')
    preview = array.array('f',[0])*(16*RATE)
    add(preview,sounds['prism_bed'],0,.35)
    add(preview,sounds['story_threshold'],0,.8)
    add(preview,sounds['story_judging'],5*RATE,.8)
    add(preview,sounds['story_binding'],round(6.4*RATE),.8)
    add(preview,sounds['story_ascend'],9*RATE,.8)
    write_wav(directory.parent/'prismatic-sequence-preview.wav',preview)
    print(json.dumps({name:{'seconds':v['seconds'],'peak':round(v['peak'],4)} for name,v in report['files'].items()}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',type=Path,default=ROOT/'steam_client/static/audio/v2')
    generate(parser.parse_args().directory)
