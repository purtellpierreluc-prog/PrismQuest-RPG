"""Verify real local Web Audio, persistence, focus policy and event deduplication."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    errors, external = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})

        def local_only(route):
            if urlsplit(route.request.url).hostname in {'localhost', '127.0.0.1'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()

        page.route('**/*', local_only)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        inspect = '() => window.PrismAudio.inspect()'
        assert page.evaluate(inspect)['context'] == 'locked'
        assert page.evaluate(inspect)['decoded'] == 0
        page.get_by_role('button', name='Play', exact=True).click()
        page.wait_for_function('window.PrismAudio.inspect().decoded === 11 && window.PrismAudio.inspect().context === "running"')
        page.get_by_role('button', name='Open Core', exact=True).click()
        page.get_by_role('button', name='Settings', exact=True).click()
        page.locator('.pd-audio-panel').wait_for()
        assert page.evaluate(inspect)['played'] == {}, 'Opening a saved hero must not replay old rewards.'
        font = page.request.get(f'http://127.0.0.1:{args.port}/desktop-ui/audio/v1/ambient.wav')
        assert font.status == 200 and 'max-age=31536000' in font.headers.get('cache-control', '')
        page.get_by_role('button', name='Test Level-up', exact=True).click()
        page.wait_for_function('window.PrismAudio.inspect().played.level === 1')
        page.wait_for_timeout(350)
        page.get_by_role('button', name='Test Rare Find', exact=True).click()
        page.wait_for_function('window.PrismAudio.inspect().played.find_rare === 1')
        volume = page.get_by_role('slider', name='Sound Effects Volume', exact=True)
        control = volume.locator('.q-slider__track-container')
        control.focus()
        control.press('ArrowLeft')
        page.wait_for_function('window.PrismAudio.inspect().preferences.effects_volume === 34')
        volume.click(position={'x': 1, 'y': volume.bounding_box()['height']/2})
        page.wait_for_function('window.PrismAudio.inspect().preferences.effects_volume === 0')
        before = page.evaluate(inspect)['played']
        page.get_by_role('button', name='Test Rare Find', exact=True).click()
        page.wait_for_timeout(400)
        assert page.evaluate(inspect)['played'] == before
        mute = page.get_by_role('checkbox', name='Mute all audio', exact=True)
        mute.click()
        page.wait_for_function('window.PrismAudio.inspect().preferences.muted')
        page.wait_for_function('window.PrismAudio.inspect().context === "suspended"')
        page.wait_for_timeout(600)
        page.reload(wait_until='networkidle')
        page.locator('.pd-audio-panel').wait_for()
        assert page.evaluate(inspect)['preferences']['muted']
        assert page.evaluate(inspect)['preferences']['effects_volume'] == 0
        page.get_by_role('button', name='Restore Quiet Defaults', exact=True).click()
        page.wait_for_function('window.PrismAudio.inspect().preferences.effects_volume === 35 && !window.PrismAudio.inspect().preferences.muted')
        for width, height in [(1280, 720), (960, 600), (1920, 1080)]:
            page.set_viewport_size({'width': width, 'height': height})
            page.wait_for_timeout(250)
            metrics = page.evaluate('() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})')
            assert metrics['sw'] <= width and metrics['sh'] <= height
            page.screenshot(path=str(out / f'audio-settings-{width}.png'))
        ui_report = page.evaluate(inspect)
        assert not ui_report['failed']
        page.close()

        # A static same-origin harness tests repeated render signals without
        # changing any game state or colliding with natural combat/regen updates.
        harness = browser.new_page()
        harness.route('**/*', local_only)
        harness.on('pageerror', lambda error: errors.append(str(error)))
        source = (ROOT / 'steam_client/static/audio.js').read_text(encoding='utf-8')
        markup = '<!doctype html><body><button id="unlock">Enable</button><div class="mq-desktop"></div><script>' + source + '</script></body>'
        harness.route('**/audio-harness', lambda route: route.fulfill(status=200, content_type='text/html', body=markup))
        harness.goto(f'http://127.0.0.1:{args.port}/audio-harness')
        signal = {'p': 'fixture-a', 's': 'arena', 'a': False, 'l': 1, 'r': 0, 'q': 'Common',
                  'h': 100, 'm': 100, 'd': 0, 'c': False, 'k': 'impact', 'e': 0, 'o': 'idle'}

        def emit(**values):
            signal.update(values)
            harness.evaluate('value => document.querySelector(".mq-desktop").dataset.pqAudio = JSON.stringify(value)', signal)
            harness.wait_for_timeout(45)

        def counts():
            return harness.evaluate(inspect)['played']

        emit()
        emit(l=2, r=1, q='Rare')  # Delayed pre-gesture events must not be replayed.
        harness.locator('#unlock').click()
        harness.wait_for_function('window.PrismAudio.inspect().decoded === 11 && window.PrismAudio.inspect().context === "running"')
        assert counts() == {}
        emit(a=True, e=1)
        assert counts().get('encounter') == 1
        harness.wait_for_timeout(800)
        emit(h=90, m=70, d=1)
        assert counts().get('impact') == 1
        before = counts()
        for _ in range(8):
            harness.evaluate('() => { const root=document.querySelector(".mq-desktop"); root.replaceWith(root.cloneNode(true)); }')
        harness.wait_for_timeout(300)
        assert counts() == before
        harness.wait_for_timeout(800)
        emit(h=85, m=50, d=2, c=True)
        assert counts().get('critical') == 1
        emit(a=False, l=3, r=2, q='Rare', o='victory')
        harness.wait_for_function('window.PrismAudio.inspect().played.level === 1')
        harness.wait_for_function('window.PrismAudio.inspect().played.find_rare === 1')
        before = counts()
        for _ in range(8):
            emit()
        harness.wait_for_timeout(500)
        assert counts() == before
        emit(a=True, e=2)
        emit(a=False, r=3, q='Common')
        assert counts().get('find_rare') == 1 and counts().get('find_soft', 0) == 0
        emit(p='fixture-b', l=60, r=99, q='Legendary')
        assert counts().get('find_prismatic', 0) == 0
        harness.wait_for_timeout(300)
        emit(l=61, r=100, q='Rare')
        harness.evaluate('window.dispatchEvent(new Event("blur"))')
        harness.wait_for_function('window.PrismAudio.inspect().context === "suspended"')
        harness.wait_for_timeout(1200)
        before = counts()
        harness.evaluate('window.dispatchEvent(new Event("focus"))')
        harness.wait_for_function('window.PrismAudio.inspect().context === "running"')
        harness.wait_for_timeout(400)
        assert counts() == before and counts().get('find_rare') == 1
        emit(s='labyrinth', a=True, e='lab-a', k='spell')
        packet = {'members': [[100,100,30,30,False,None]], 'monsters': [[100,100,None,'Monster']]}
        harness.evaluate('value => window.PrismAudio.combatStep(value)', packet)
        harness.wait_for_timeout(800)
        packet['monsters'][0][0] = 70
        harness.evaluate('value => window.PrismAudio.combatStep(value)', packet)
        assert counts().get('spell') == 1
        before = counts()
        for _ in range(8):
            harness.evaluate('value => window.PrismAudio.combatStep(value)', packet)
        harness.wait_for_timeout(100)
        assert counts() == before
        harness.evaluate('window.PrismAudio.configure({rewards_enabled:false, combat_enabled:false})')
        harness.evaluate('window.PrismAudio.preview("level")')
        harness.wait_for_timeout(120)
        assert counts() == before
        harness.evaluate('window.PrismAudio.configure({rewards_enabled:true, combat_enabled:true})')
        report = {'ui': ui_report, 'harness': harness.evaluate(inspect), 'external_requests': external,
                  'page_errors': errors, 'limitations': 'Headless audio playback/graph tests; not a subjective listening or hardware-speaker test.'}
        assert report['harness']['voices'] <= 4 and report['harness']['loops'] <= 2
        assert not external and not errors, (external, errors)
        (out / 'audio-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)
        browser.close()


if __name__ == '__main__':
    main()
