"""Verify deliberately frozen boss/reward/lobby fixtures, never normal saves."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scene',choices=['boss','swarm','reward','lobby','defeated'],required=True)
    args = parser.parse_args()
    if '.local-test' not in args.output.resolve().parts:
        raise SystemExit('Disposable test output only.')
    args.output.mkdir(parents=True,exist_ok=True)
    errors,external,checks = [],[],[]
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page = browser.new_page(viewport={'width':1280,'height':720})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def local(route):
            if urlsplit(route.request.url).hostname in {'localhost','127.0.0.1'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route('**/*',local)
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        page.get_by_role('button',name='Play',exact=True).click()
        page.get_by_role('button',name='Open SSF',exact=True).click()
        page.locator('.pl-workspace').wait_for()
        for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
            page.set_viewport_size({'width':w,'height':h})
            page.wait_for_timeout(180)
            assert page.evaluate('document.scrollingElement.scrollHeight<=innerHeight+1 && document.scrollingElement.scrollWidth<=innerWidth+1')
            if args.scene=='boss':
                expect(page.locator('.pl-monster')).to_have_count(1)
                expect(page.locator('.pl-boss-stats')).to_contain_text('Resistance')
                bounds = page.locator('#mq-meter-labyrinth-monster-hp').bounding_box()
                assert bounds and bounds['width']>0 and bounds['y']+bounds['height']<=h
            elif args.scene=='swarm':
                expect(page.locator('.pl-monster')).to_have_count(6)
                stage = page.locator('.pl-stage').bounding_box()
                for bounds in page.locator('.pl-monsters .mq-meter').evaluate_all('els=>els.map(e=>{const r=e.getBoundingClientRect();return {bottom:r.bottom,right:r.right,h:r.height}})'):
                    assert bounds['h']>0 and bounds['bottom']<=stage['y']+stage['height'] and bounds['right']<=stage['x']+stage['width']
            elif args.scene=='reward':
                expect(page.locator('.pl-prism-choice')).to_have_count(3)
                expect(page.locator('.pl-vote-clock')).to_contain_text('to choose')
            elif args.scene=='lobby':
                expect(page.get_by_role('button',name='Start Floor',exact=True)).to_be_visible()
            else:
                expect(page.get_by_role('button',name='Reform at the Prism Gate',exact=True)).to_be_visible()
            page.screenshot(path=str(args.output/f'{args.scene}-{w}.png'))
            checks.append({'width':w,'height':h})
        assert not errors and not external,(errors,external)
        report = {'passed':True,'scene':args.scene,'checks':checks,'errors':errors,'external':external}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__=='__main__':
    main()
