"""Check compact Ctrl-inspections and class-filtered local PQ records on a QA profile."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if '.local-test' not in args.output.resolve().parts:
        raise SystemExit('Disposable output only.')
    args.output.mkdir(parents=True,exist_ok=True)
    errors,external,checks=[],[],[]
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1280,'height':720})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def local(route):
            if urlsplit(route.request.url).hostname in {'127.0.0.1','localhost'}: route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route('**/*',local)
        def button(label): return page.get_by_role('button',name=label,exact=True).first
        def fit(scene):
            for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
                page.set_viewport_size({'width':w,'height':h})
                page.wait_for_timeout(180)
                assert page.evaluate('document.scrollingElement.scrollWidth<=innerWidth+1 && document.scrollingElement.scrollHeight<=innerHeight+1'),scene
                page.screenshot(path=str(args.output/f'{scene}-{w}.png'))
                checks.append({'scene':scene,'w':w,'h':h})
            page.set_viewport_size({'width':1280,'height':720})
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        button('Play').click()
        button('Open Core').click()
        page.locator('.pd-town-map img').wait_for()
        assert 'town_reimagined' in page.locator('.pd-town-map img').get_attribute('src').lower()
        fit('town-new-art')
        button('Arena').click()
        expect(page.locator('.pd-arena-insight')).to_have_count(2)
        assert not page.locator('.pd-combat-stats').count()
        assert 'BUILD DECISION' not in page.locator('.pd-arena-workspace').inner_text()
        assert 'Turn experience into power' not in page.locator('.pd-arena-workspace').inner_text()
        for icon in page.locator('.pd-arena-insight').all():
            bounds=icon.bounding_box()
            assert bounds['width']<=28 and bounds['height']<=28
        portal=page.locator('#pd-item-inspection')
        button('Inspect combat stats').hover()
        expect(portal).not_to_be_visible()
        page.keyboard.down('Control')
        expect(portal).to_contain_text('Combat Stats')
        expect(portal.locator('dd')).to_have_count(6)
        page.screenshot(path=str(args.output/'stats-hover.png'))
        button('Inspect proficiencies').hover()
        expect(portal).to_contain_text('Proficiencies')
        expect(portal.locator('.pd-insight-prof')).to_have_count(6)
        expect(portal).to_contain_text('Lv 7')
        assert 'Each level' not in portal.inner_text()
        page.screenshot(path=str(args.output/'proficiency-hover.png'))
        page.keyboard.up('Control')
        page.mouse.move(2,2)
        fit('arena-compact')
        page.locator('.pd-build-btn').click()
        page.locator('.pd-character-workspace').wait_for()
        assert not page.locator('.pd-proficiency-sheet').count()
        fit('stats-no-proficiency')
        button('Return to Arena').click()
        button('Fight').click()
        expect(button('Fight')).to_be_disabled()
        page.keyboard.down('Control')
        button('Inspect proficiencies').hover()
        expect(portal).to_be_visible()
        page.evaluate('window.inspectionBefore=document.querySelector("#pd-item-inspection")')
        page.wait_for_timeout(1800)
        expect(portal).to_be_visible()
        assert page.evaluate('window.inspectionBefore===document.querySelector("#pd-item-inspection")')
        page.keyboard.up('Control')
        expect(button('Fight')).to_be_enabled(timeout=120000)
        button('Chronicle Menu').click()
        page.get_by_text('Realm Ladder',exact=True).last.click()
        page.locator('.nl-class-filter').click()
        page.get_by_role('option',name='Black Guard',exact=True).click()
        expect(page.locator('.nl-row').first).to_contain_text('1m 30s')
        expect(page.locator('.nl-row')).to_have_count(1)
        fit('ladder-class')
        page.locator('.nl-class-filter').click()
        page.get_by_role('option',name='Shadow Mage',exact=True).click()
        expect(page.locator('.nl-row').first).to_contain_text('0m 30s')
        button('My Ascents').click()
        expect(page.locator('.nl-ascent')).to_have_count(1)
        expect(page.locator('.nl-ascent')).to_contain_text('Shadow Mage')
        assert not errors and not external,(errors,external)
        report={'passed':True,'checks':checks,'hover_stable_in_combat':True,'class_times_correct':True,'errors':errors,'external':external}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__=='__main__': main()
