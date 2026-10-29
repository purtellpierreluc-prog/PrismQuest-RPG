"""Render original, restrained PrismQuest sounds. Standard library only.

No third-party recordings, samples or music are used. This is a development
tool; generation never runs during gameplay. Buffers are mastered below full
scale and packaged as mono PCM WAVs for efficient local decoding.
"""

import argparse
import array
import hashlib
import json
import math
import random
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAU = math.tau


def bell(frequency, seconds, rate=22050, gain=.2):
    samples = array.array('f')
    for index in range(round(seconds * rate)):
        t = index / rate
        attack = min(1, t / .012) ** 2
        release = min(1, (seconds-t) / .14)
        tone = sum(weight * math.sin(TAU * frequency * ratio * t) * math.exp(-t / decay)
                   for ratio, weight, decay in [(1, 1, .58), (2.01, .24, .27), (2.77, .065, .13)])
        samples.append(tone * attack * release * gain)
    return samples


def add(target, source, offset, gain=1, wrap=False):
    for index, value in enumerate(source):
        destination = offset + index
        if wrap:
            destination %= len(target)
        if 0 <= destination < len(target):
            target[destination] += value * gain


def chime(notes, length, gain=.25, rate=22050):
    output = array.array('f', [0]) * round(length * rate)
    for frequency, start, weight in notes:
        add(output, bell(frequency, min(1.7, length-start), rate, gain * weight), round(start*rate))
    dry = output[:]
    for delay, strength in [(.125, .13), (.245, .055)]:
        add(output, dry, round(delay * rate), strength)
    return output


def texture(kind, rate=22050):
    rng = random.Random({'impact': 319, 'spell': 811, 'critical': 613, 'encounter': 991}[kind])
    length = {'impact': .25, 'critical': .38, 'spell': .5, 'encounter': .65}[kind]
    output = array.array('f')
    low, bass = 0., 0.
    for index in range(round(length*rate)):
        t = index / rate
        noise = rng.uniform(-1, 1)
        low += .16 * (noise-low)
        bass += .025 * (noise-bass)
        if kind in {'impact', 'critical'}:
            body = math.sin(TAU * (125*t + 25*(1-math.exp(-25*t))))
            sound = bass*1.7 + low*.3 + body*.11
            envelope = min(1, t/.004) * math.exp(-t*24) * min(1, (length-t)/.04)
            output.append(sound * envelope * .9)
        else:
            airy = (low-bass)*.65 + math.sin(TAU * 293.665*t)*.018
            envelope = math.sin(math.pi*t/length)**2
            output.append(airy * envelope * (.6 if kind == 'spell' else .4))
    if kind == 'critical':
        add(output, bell(587.33, .32, rate, .08), round(.025*rate))
    return output


def ambient(rate=22050):
    duration = 48
    output = array.array('f', [0]) * (duration*rate)
    chords = [(146.832, 174.614, 220., 329.628), (116.541, 174.614, 220., 293.665),
              (174.614, 220., 261.626, 391.995), (130.813, 196., 261.626, 293.665)]
    for chord_index, notes in enumerate(chords):
        start = (chord_index*12 - 3)*rate
        for note_index, frequency in enumerate(notes):
            for index in range(18*rate):
                t = index/rate
                envelope = math.sin(math.pi*t/18)**2
                shimmer = 1 + .07*math.sin(TAU * .13*t + note_index)
                phase = TAU * frequency*t
                tone = math.sin(phase) + .12*math.sin(phase*2+.3) + .025*math.sin(phase*3)
                output[(start+index) % len(output)] += tone * envelope * shimmer * .022
        add(output, bell(notes[-1]*2, 3.5, rate, .018), (chord_index*12+3)*rate, wrap=True)
    return output


def undertone(rate=22050):
    duration = 8
    output = array.array('f')
    # Integer cycle counts keep the loop seam phase-continuous.
    for index in range(duration*rate):
        t = index/rate
        swell = .72 + .28*math.cos(TAU*t/duration)
        sound = sum(weight*math.sin(TAU*cycles*t/duration + phase)
                    for cycles, weight, phase in [(587,.07,0), (887,.025,.3), (1399,.012,.7), (1801,.006,1.1)])
        output.append(sound*swell)
    return output


def write_wav(path, samples, rate=22050, loop=False):
    mean = sum(samples)/len(samples)
    mastered = array.array('f', (value-mean for value in samples))
    if not loop:
        for index in range(len(mastered)):
            fade = min(1, index/(rate*.006), (len(mastered)-1-index)/(rate*.035))
            mastered[index] *= math.sin(fade*math.pi/2)**2
        # Remove residual DC without reintroducing a nonzero first/last sample.
        residual = sum(mastered)/len(mastered)
        correction = residual*len(mastered)*2/(len(mastered)-1)
        for index in range(len(mastered)):
            mastered[index] -= correction*math.sin(math.pi*index/(len(mastered)-1))**2
    pcm = array.array('h', [max(-32767, min(32767, round(value*32767))) for value in mastered])
    if sys.byteorder != 'little':
        pcm.byteswap()
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    peak = max(abs(value) for value in mastered)
    if peak >= .8:
        raise ValueError(f'Unmastered audio peak: {path.name} {peak}')
    return {'seconds': len(samples)/rate, 'sample_rate': rate, 'peak': peak,
            'rms': math.sqrt(sum(value**2 for value in mastered)/len(mastered)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def generate(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    sounds = {name: texture(name) for name in ['impact', 'spell', 'critical', 'encounter']}
    sounds['victory'] = chime([(440,0,.5), (587.33,.14,.65)], 1.1, .16)
    sounds['level'] = chime([(587.33,0,.8), (698.46,.14,.65), (880,.32,.6), (1174.66,.52,.5)], 2.3, .21)
    sounds['find_soft'] = chime([(587.33,0,.7)], 1.1, .17)
    sounds['find_rare'] = chime([(880,0,.75), (1174.66,.18,.55)], 1.8, .21)
    sounds['find_prismatic'] = chime([(587.33,0,.65), (880,.16,.6), (1174.66,.36,.55), (1318.51,.6,.35)], 2.7, .21)
    sounds['ambient'] = ambient()
    sounds['undertone'] = undertone()
    report = {'origin': 'Original procedural PrismQuest synthesis; no external recordings or samples.',
              'version': 1, 'files': {}}
    for name, samples in sounds.items():
        report['files'][name] = write_wav(directory / f'{name}.wav', samples, loop=name in {'ambient', 'undertone'})
    (directory / 'manifest.json').write_text(json.dumps(report, indent=2, sort_keys=True), encoding='utf-8')
    preview = array.array('f', [0]) * (12*22050)
    add(preview, sounds['ambient'][:len(preview)], 0, .3)
    add(preview, sounds['impact'], 2*22050, .25)
    add(preview, sounds['spell'], round(3.2*22050), .3)
    add(preview, sounds['level'], 5*22050, .5)
    add(preview, sounds['find_rare'], round(8.3*22050), .5)
    write_wav(directory.parent / 'soundscape-preview.wav', preview)
    print(json.dumps({name: {'seconds': row['seconds'], 'peak': round(row['peak'], 4)} for name, row in report['files'].items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', default=str(ROOT / 'steam_client/static/audio/v1'))
    generate(parser.parse_args().directory)
