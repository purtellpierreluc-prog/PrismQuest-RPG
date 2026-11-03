"""Maze, compact copy and non-overlapping expedition UI on disposable saves only."""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from steam_client.labyrinth import DIRECTIONS, passages
from steam_client.save_schema import owned_items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    if '.local-test' not in args.profile.resolve().parts:
        raise SystemExit('Disposable profiles only.')
    args.output.mkdir(parents=True,exist_ok=True)
    errors,external,checks = [],[],[]
    def saved():
        return json.loads((args.profile/'saves/chronicles.json').read_text(encoding='utf-8'))['slots']
    def personal_items(slot):
        items = Counter(json.dumps(item,sort_keys=True) for _,item in owned_items(slot))
        # Issued companion gear is deliberately retired, not returned as a tradeable item.
        for companion in slot.get('labyrinth_roster_companions',[]):
            for name,item in companion.get('equipped',{}).items():
                if item is not None and companion.get('equipped_item_sources',{}).get(name,'companion')!='player':
                    items[json.dumps(item,sort_keys=True)] -= 1
        return +items
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page = browser.new_page(viewport={'width':1280,'height':720})
        page.on('pageerror',lambda error:errors.append(str(error)))
        def local(route):
            if urlsplit(route.request.url).hostname in {'127.0.0.1','localhost'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route('**/*',local)
        def button(name):
            return page.get_by_role('button',name=name,exact=True).first
        def check(scene):
            page.mouse.move(2,2)
            page.wait_for_timeout(180)
            metrics = page.evaluate('''() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})''')
            assert metrics['sw']<=metrics['w']+1 and metrics['sh']<=metrics['h']+1,(scene,metrics)
            if page.locator('.pl-layout').count():
                boxes = page.locator('.pl-company,.pl-stage,.pl-dock').evaluate_all('els=>els.map(e=>{const r=e.getBoundingClientRect();return {x:r.x,right:r.right,y:r.y,bottom:r.bottom,w:r.width,h:r.height}})')
                assert len(boxes)==3 and all(b['w']>0 and b['h']>0 and b['bottom']<=metrics['h']+1 for b in boxes),boxes
                assert boxes[0]['right']<=boxes[1]['x'] and boxes[1]['right']<=boxes[2]['x'],boxes
                if metrics['h']>=720 and metrics['w']>=1280:
                    assert page.locator('.pl-party-scroll').evaluate('e=>e.scrollHeight<=e.clientHeight+1'),'All five party members should fit without scrolling at 720p and up.'
            page.screenshot(path=str(args.output/f'{scene}-{metrics["w"]}.png'))
            checks.append({'scene':scene,**metrics})
        def sizes(scene):
            for width,height in [(1280,720),(960,600),(800,500),(1920,1080)]:
                page.set_viewport_size({'width':width,'height':height})
                check(scene)
            page.set_viewport_size({'width':1280,'height':720})
        def absent(strings):
            body = page.locator('.mq-desktop').inner_text()
            for value in strings:
                assert value.casefold() not in body.casefold(),value
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        button('Play').click()
        button('Open Core').click()
        page.locator('.pd-town-workspace').wait_for()
        absent(['The prism is within reach','Recover / Vault','Inspect / Equip','Find new equipment','Combine your finds','Offer / Risk / Discover','READY TO ENTER','Choose your road.'])
        sizes('town-clean')
        button('Arena').click()
        page.locator('.pd-arena-workspace').wait_for()
        absent(['AUTOMATIC COMBAT / YOUR BUILD MAKES THE DIFFERENCE','Your experience still counts.','Your next decision is yours. No automatic restart.','Automatic rounds. Deliberate preparation.','YOUR CHAMPION /','You and your opponent act automatically','Grave moss','High magic resist','LIVE ENCOUNTER'])
        sizes('arena-clean')
        button('Character & Stats').click()
        page.locator('.pd-character-workspace').wait_for()
        absent(['/ initiative, not attack rate','/ favors axes','Allocation affects future level-up resource growth. Choose deliberately.','Agile bruiser. Fast, evasive, and steady.','BUILD YOUR CHAMPION'])
        sizes('stats-clean')
        button('Chronicle Menu').click()
        page.get_by_text('Return to Chronicle Slots',exact=True).last.click()
        button('Open SSF').click()
        page.locator('.pl-workspace').wait_for()
        expect(page.locator('.pl-member')).to_have_count(5)
        expect(page.locator('.pl-maze')).to_be_visible()
        expect(page.get_by_text('Expedition Controls',exact=True)).to_have_count(0)
        sizes('maze-five')
        first_tank = page.locator('.pl-member .mq-lab-tank-btn').first
        original = first_tank.get_attribute('aria-pressed')
        first_tank.click()
        expect(page.locator('.pl-member .mq-lab-tank-btn').first).to_have_attribute('aria-pressed','false' if original=='true' else 'true')
        token = page.locator('.pl-gear-token button').first
        token.hover()
        expect(page.locator('#pd-item-inspection')).not_to_be_visible()
        page.keyboard.down('Control')
        expect(page.locator('#pd-item-inspection')).to_be_visible()
        page.keyboard.up('Control')
        button('Roster').click()
        page.locator('.pl-recruit').wait_for()
        sizes('company-management')
        button('Own Permanently / 1,000g').click()
        expect(page.locator('.pl-roster-card')).to_have_count(1)
        name = page.get_by_label('Companion name',exact=True)
        name.fill('The Quiet Lantern')
        page.wait_for_timeout(1800)
        expect(name).to_be_focused()
        expect(name).to_have_value('The Quiet Lantern')
        button('Save Name').click()
        page.wait_for_timeout(250)
        assert saved()[1]['labyrinth_roster_companions'][0]['custom_name']=='The Quiet Lantern'
        before_items = personal_items(saved()[1])
        weapon = page.locator('.pl-roster-slot').first
        weapon.locator('.q-select').click()
        page.get_by_role('option').first.click()
        weapon.get_by_role('button',name='Equip',exact=True).click()
        page.wait_for_timeout(250)
        after_items = personal_items(saved()[1])
        assert before_items==after_items,'Companion equipment must move exactly once, not copy or delete an item.'
        page.locator('.pl-roster-slot').first.get_by_role('button',name='Return',exact=True).click()
        page.wait_for_timeout(250)
        assert personal_items(saved()[1])==before_items,'Returning player equipment must also conserve it exactly.'
        sizes('owned-companion')
        button('Back to Maze').click()
        page.locator('.pl-maze').wait_for()
        button('Open Inventory').click()
        expect(button('Close')).to_be_visible()
        button('Close').click()
        page.locator('.pl-maze').wait_for()
        old = saved()[1]['desktop_labyrinth_run']['session']
        graph = passages(old)
        start = f'{old["current_x"]},{old["current_y"]}'
        target = graph[start][0]
        nx,ny = map(int,target.split(','))
        direction = next(d for d,(dx,dy) in DIRECTIONS.items() if (old['current_x']+dx,old['current_y']+dy)==(nx,ny))
        for d,(dx,dy) in DIRECTIONS.items():
            expect(button(f'Move {d}')).to_be_enabled() if f'{old["current_x"]+dx},{old["current_y"]+dy}' in graph[start] else expect(button(f'Move {d}')).to_be_disabled()
        before = page.locator('.pl-stage').bounding_box()
        button(f'Move {direction}').click()
        page.wait_for_timeout(400)
        current = saved()[1]['desktop_labyrinth_run']['session']
        assert (current['current_x'],current['current_y'])==(nx,ny)
        assert current['tile_states'][target]['visited']
        if current['status'] in {'encounter','boss'}:
            expect(page.locator('.pl-monster')).to_have_count(6)
            sizes('combat-six')
            assert abs(page.locator('.pl-stage').bounding_box()['height']-before['height'])<2
            expect(button('Roster')).to_be_disabled()
            page.wait_for_function('document.querySelector(".pl-maze") || document.querySelector(".pl-prism-choices")',timeout=120000)
        check('after-step')
        assert not errors and not external,{'errors':errors,'external':external}
        report = {'passed':True,'checks':checks,'errors':errors,'external':external,'maze_edges':sum(len(n) for n in graph.values())//2,'name_draft_stable':True,'party_controls_separate':True}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__=='__main__':
    main()
