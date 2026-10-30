"""Verify last-drop retention and refresh-safe, non-blocking Arena motion."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    errors, external = [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})

        def local(route):
            if urlsplit(route.request.url).hostname in {'localhost', '127.0.0.1'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()

        page.route('**/*', local)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        page.get_by_role('button', name='Play', exact=True).click()
        page.get_by_role('button', name='Open Core', exact=True).click()
        page.get_by_label('Character Name', exact=True).fill('Quiet Motion')
        page.get_by_role('button', name='Enter the ascent as Black Guard', exact=True).click()
        page.get_by_role('button', name='Go to Arena', exact=True).click()
        page.get_by_text('Congratulations. That first Arena victory paid out a guaranteed Rare item.', exact=True).wait_for(timeout=60000)
        page.get_by_role('button', name='Back to the Climb', exact=True).click()
        page.locator('.pd-result-title.victory').wait_for()
        page.wait_for_function('window.PrismEncounter.inspect().counts.victory === 1')
        first = page.evaluate('window.PrismEncounter.inspect()')
        assert first['counts']['arrival'] == 1
        page.wait_for_timeout(500)
        settled_scale = page.locator('.pd-enemy-art').evaluate('e=>new DOMMatrixReadOnly(getComputedStyle(e).transform).a')
        assert abs(settled_scale-.985) < .001
        find = page.get_by_role('button', name='Inspect last dropped item', exact=True)
        expect(find).to_be_enabled()
        find.hover()
        portal = page.locator('#pd-item-inspection')
        expect(portal).to_be_visible()
        loot = portal.inner_text()
        assert 'Rare' in loot and 'Read-only record' in loot
        page.mouse.move(650, 100)
        for w, h in [(1280, 720), (960, 600), (1920, 1080), (800, 500)]:
            page.set_viewport_size({'width': w, 'height': h})
            page.wait_for_timeout(200)
            expect(find).to_be_in_viewport()
            assert page.evaluate('document.scrollingElement.scrollHeight<=innerHeight && document.scrollingElement.scrollWidth<=innerWidth')
            page.screenshot(path=str(args.output / f'last-find-{w}.png'))
        page.set_viewport_size({'width': 1280, 'height': 720})
        page.wait_for_timeout(100)
        before_stage = page.locator('.pd-battle-theatre').bounding_box()
        assert page.evaluate('window.PrismEncounter.inspect().counts') == first['counts']
        sequence = page.evaluate('JSON.parse(document.querySelector(".mq-desktop").dataset.pqAudio).r')
        page.get_by_role('button', name='Fight', exact=True).click()
        expect(page.get_by_role('button', name='Fight', exact=True)).to_be_disabled()
        page.wait_for_function('window.PrismEncounter.inspect().counts.arrival === 2')
        after_stage = page.locator('.pd-battle-theatre').bounding_box()
        assert abs(before_stage['height']-after_stage['height']) <= 1, (before_stage, after_stage)
        expect(find).to_be_enabled()
        find.hover()
        expect(portal).to_be_visible()
        assert portal.inner_text() == loot, 'The next fight must not clear the last find.'
        page.evaluate('window.pdLastFindPortal = document.querySelector("#pd-item-inspection")')
        page.wait_for_timeout(1700)
        assert page.evaluate('window.pdLastFindPortal === document.querySelector("#pd-item-inspection")')
        expect(portal).to_be_visible()
        if page.evaluate('JSON.parse(document.querySelector(".mq-desktop").dataset.pqAudio).r') == sequence:
            assert portal.inner_text() == loot
        assert page.evaluate('window.PrismEncounter.inspect().counts.arrival') == 2
        page.screenshot(path=str(args.output / 'last-find-in-combat.png'))
        page.mouse.move(650, 100)
        page.wait_for_timeout(200)
        page.screenshot(path=str(args.output / 'species-atmosphere.png'))
        game_report = page.evaluate('window.PrismEncounter.inspect()')
        page.close()

        # Same-origin deterministic fixture: exercise presentation without
        # modifying actual heroes, combat rolls or saves.
        harness = browser.new_page()
        harness.route('**/*', local)
        harness.on('pageerror', lambda error: errors.append(str(error)))
        source = (ROOT / 'steam_client/static/encounters.js').read_text(encoding='utf-8')
        signal = {'p': 'fixture', 'e': 'A', 'phase': 'idle', 'reduced': False}
        stage = '<section class="pd-battle-theatre" data-pd-encounter=\'' + json.dumps(signal) + '\'><div class="pd-enemy-art">Art</div><div class="pd-hero-art">Hero</div><div class="pd-round">Round</div><div class="pd-result-title">Victory</div><div class="pd-encounter-trace">Trace</div></section>'
        markup = '<!doctype html><body>' + stage + '<script>' + source + '</script></body>'
        harness.route('**/encounter-harness', lambda route: route.fulfill(status=200, content_type='text/html', body=markup))
        harness.goto(f'http://127.0.0.1:{args.port}/encounter-harness', wait_until='load')

        def send(phase, encounter='A', profile='fixture'):
            data = {'p': profile, 'e': encounter, 'phase': phase, 'reduced': False}
            harness.evaluate('s=>{const e=document.querySelector(".pd-battle-theatre");e.dataset.pdEncounter=JSON.stringify(s);e.dataset.pdPhase=s.phase}', data)

        send('combat')
        harness.wait_for_function('PrismEncounter.inspect().counts.arrival === 1')
        for _ in range(4):
            harness.wait_for_timeout(60)
            harness.evaluate('()=>{const e=document.querySelector(".pd-battle-theatre");e.replaceWith(e.cloneNode(true));}')
        state = harness.evaluate('PrismEncounter.inspect()')
        assert state['counts']['arrival'] == 1 and state['elapsed'] > 180
        assert state['running'] <= 3
        harness.wait_for_timeout(500)
        assert harness.evaluate('PrismEncounter.inspect().running') == 0
        send('victory')
        harness.wait_for_function('PrismEncounter.inspect().counts.victory === 1')
        send('combat', 'B')
        harness.wait_for_function('PrismEncounter.inspect().counts.arrival === 2')
        assert harness.evaluate('PrismEncounter.inspect().phase') == 'combat'
        for _ in range(10):
            harness.evaluate('()=>{const e=document.querySelector(".pd-battle-theatre");e.replaceWith(e.cloneNode(true));}')
        assert harness.evaluate('PrismEncounter.inspect().counts.arrival') == 2
        harness.emulate_media(reduced_motion='reduce')
        send('defeat', 'B')
        send('combat', 'C')
        assert harness.evaluate('PrismEncounter.inspect().running') == 0
        assert harness.evaluate('PrismEncounter.inspect().counts.arrival') == 2
        harness.emulate_media(reduced_motion='no-preference')
        harness.evaluate('document.documentElement.dataset.mqReducedMotion="true"')
        send('idle', 'C')
        send('combat', 'D')
        assert harness.evaluate('PrismEncounter.inspect().counts.arrival') == 2
        harness.evaluate('document.documentElement.dataset.mqReducedMotion="false"')
        send('idle', 'D')
        send('combat', 'E')
        harness.wait_for_function('PrismEncounter.inspect().counts.arrival === 3')
        harness.evaluate('window.dispatchEvent(new Event("blur"))')
        assert harness.evaluate('PrismEncounter.inspect().running') == 0
        send('combat', 'E')
        assert harness.evaluate('PrismEncounter.inspect().counts.arrival') == 3
        send('combat', 'Z', 'other-profile')
        assert harness.evaluate('PrismEncounter.inspect().counts.arrival') == 3
        report = {'passed': True, 'last_find_retained_during_combat': True, 'game': game_report,
                  'fixture': harness.evaluate('PrismEncounter.inspect()'), 'page_errors': errors, 'external_requests': external}
        assert not errors and not external, report
        (args.output / 'encounter-smoke.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        browser.close()


if __name__ == '__main__':
    main()
