"""Real Inn/Bazaar/Guild/Ladder playthrough, only against a disposable profile."""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from steam_client.save_schema import owned_items


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--resume',action='store_true')
    args = parser.parse_args()
    if '.local-test' not in args.profile.resolve().parts:
        raise SystemExit('Only disposable .local-test profiles may be used.')
    args.output.mkdir(parents=True,exist_ok=True)
    def slots():
        return json.loads((args.profile/'saves/chronicles.json').read_text(encoding='utf-8'))['slots']
    def owned():
        return Counter(json.dumps(item,sort_keys=True) for slot in slots() for _,item in owned_items(slot))
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page = browser.new_page(viewport={'width':1280,'height':720})
        errors,external,reports = [],[],[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def local(route):
            if urlsplit(route.request.url).hostname in {'127.0.0.1','localhost'}:
                route.continue_()
            else:
                external.append(route.request.url)
                route.abort()
        page.route('**/*',local)
        def button(name):
            return page.get_by_role('button',name=name,exact=True).first
        def check(name,selectors=()):
            page.mouse.move(4,4)
            page.wait_for_timeout(200)
            metrics = page.evaluate('''() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})''')
            assert metrics['sw']<=metrics['w']+1 and metrics['sh']<=metrics['h']+1,(name,metrics)
            for selector in selectors:
                for box in page.locator(selector).evaluate_all('els=>els.map(e=>{let r=e.getBoundingClientRect();return {bottom:r.bottom,right:r.right,h:r.height};})'):
                    assert box['h']>0 and box['bottom']<=metrics['h']+1 and box['right']<=metrics['w']+1,(name,selector,box,metrics)
            page.screenshot(path=str(args.output/f'{name}-{metrics["w"]}.png'))
            reports.append({'scene':name,**metrics})
        def sizes(name,selectors=()):
            for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
                page.set_viewport_size({'width':w,'height':h})
                check(name,selectors)
            page.set_viewport_size({'width':1280,'height':720})
        def town():
            button('Return to Town').click()
            page.locator('.pd-town-workspace').wait_for()
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        button('Play').click()
        button('Open Core').click()
        page.locator('.pd-town-workspace').wait_for()
        assert page.get_by_role('button',name='Concourse',exact=True).count() == 0
        initial = owned()
        if not args.resume:
            sizes('town',['.pd-town-footer','.pd-service-deck'])
            button('Inn').click()
            page.locator('.nh-workspace').wait_for()
            sizes('inn-before',['.nh-hearth','.nh-room','.nh-room-actions'])
            assert button('Take a room').evaluate('e=>getComputedStyle(e).backgroundImage') != button('Return to Arena').evaluate('e=>getComputedStyle(e).backgroundImage')
            old = slots()[0]
            cost = int(re.search(r'/ (\d+)g',button('Take a room').inner_text())[1])
            button('Take a room').click()
            expect(button('Confirm rest and reset chain')).to_be_visible()
            assert slots()[0]['player']['gold'] == old['player']['gold']
            sizes('inn-confirm',['.nh-room-actions'])
            button('Confirm rest and reset chain').click()
            expect(page.locator('.nh-receipt')).to_contain_text('RESTED / SAVED')
            assert slots()[0]['player']['gold'] == old['player']['gold']-cost
            assert slots()[0]['monster_chain_combo'] == 0
            assert slots()[0]['player']['hp'] > old['player']['hp']
            count = 1
            while button('Take a room').is_enabled() and count<4:
                button('Take a room').click()
                page.wait_for_timeout(250)
                count += 1
            expect(button('Take a room')).to_be_disabled()
            assert owned() == initial
            sizes('inn-recovered',['.nh-room-actions','.nh-safeguards'])
            button('Open Vault').click()
            dialog = page.locator('.q-dialog:visible')
            expect(dialog).to_contain_text('Inn Vault')
            check('inn-vault')
            dialog.get_by_role('button',name='Close',exact=True).click()
            expect(dialog).not_to_be_visible()
            town()
            button('Bazaar').click()
            page.locator('.nb-workspace').wait_for()
            sizes('bazaar-browse',['.nb-layout','.nb-filters'])
            button('Sell & Manage').click()
            expect(page.locator('.nb-item')).to_have_count(27)
            selected_border = page.get_by_role('button',name='Sell & Manage',exact=True).evaluate('e=>getComputedStyle(e).borderColor')
            assert selected_border != button('Browse').evaluate('e=>getComputedStyle(e).borderColor')
            shelf = page.locator('.nb-shelf')
            shelf.evaluate('e=>e.scrollTop=e.scrollHeight')
            page.wait_for_timeout(100)
            at_bottom = shelf.evaluate('e=>e.scrollTop')
            page.locator('.nb-item').last.click()
            expect(page.locator('.nb-item.selected')).to_have_count(1)
            assert abs(page.locator('.nb-shelf').evaluate('e=>e.scrollTop')-at_bottom)<2
            page.locator('.nb-item.selected').focus()
            page.keyboard.press('ArrowUp')
            assert page.locator('.nb-item').nth(25).evaluate('e=>e===document.activeElement')
            page.locator('.nb-shelf').evaluate('e=>e.scrollTop=0')
            page.locator('.nb-item').first.click()
            price = page.get_by_label('Price in gold',exact=True)
            price.fill('357')
            field_id = price.get_attribute('id')
            page.wait_for_timeout(400)
            assert price.get_attribute('id') == field_id
            expect(page.locator('.nb-item.selected')).to_have_count(1)
            sizes('bazaar-inspect',['.nb-inspection','.nb-decision'])
            button('Review Local Listing').click()
            gold = slots()[0]['player']['gold']
            button('Confirm Listing').click()
            expect(page.locator('.nt-notice')).to_contain_text('Local listing saved')
            assert len(slots()[0]['player']['inventory']) == 26 and owned() == initial
            assert slots()[0]['player']['gold'] == gold
            page.locator('.nb-item').filter(has_text='IN ESCROW').click()
            page.get_by_label('Price in gold',exact=True).fill('888')
            button('Change Price').click()
            button('Confirm Price').click()
            expect(page.locator('.nt-notice')).to_contain_text('New price saved')
            assert slots()[0]['town_services']['listings'][0]['price'] == 888
            page.locator('.nb-item').filter(has_text='IN ESCROW').click()
            button('Return to Pack').click()
            button('Confirm Return').click()
            expect(page.locator('.nt-notice')).to_contain_text('Listing returned to your pack')
            assert len(slots()[0]['player']['inventory']) == 27 and owned() == initial
            button('Ledger').click()
            expect(page.locator('.nb-ledger-row')).to_have_count(3)
            sizes('bazaar-ledger',['.nb-shelf','.nb-inspection'])
            town()
            button('Guild Hall').click()
            page.locator('.ng-workspace').wait_for()
            sizes('guild-before',['.ng-charter-form','.ng-charter-art'])
            name = page.get_by_label('Guild name',exact=True)
            name.fill('Quiet Lanterns')
            field_id = name.get_attribute('id')
            page.wait_for_timeout(2200)
            assert name.get_attribute('id') == field_id
            page.get_by_label('Charter motto',exact=True).fill('Keep the hearth lit.')
            before = slots()[0]['player']['gold']
            button('Review Charter').click()
            assert slots()[0]['player']['gold'] == before
            button('Seal Charter / 1,000g').click()
            page.locator('.ng-hall-layout').wait_for()
            assert slots()[0]['player']['gold'] == before-1000
            message = '<script>not executable</script> Keep a light for tomorrow.'
            body = page.get_by_label('Message to your guild',exact=True)
            body.fill(message)
            field_id = body.get_attribute('id')
            page.wait_for_timeout(2200)
            assert body.get_attribute('id') == field_id
            button('Post to Board').click()
            expect(page.locator('.ng-message-body')).to_have_text(message)
            assert page.locator('.ng-message-body script').count() == 0
            sizes('guild-founded',['.ng-board','.ng-roster','.ng-composer'])
            assert owned() == initial
            town()
        expected = sum(slots()[0]['town_service_spend'].values())
        button('Town Crier').click()
        expect(page.locator('.pd-crier-copy')).to_contain_text(f'{expected:,} gold')
        page.keyboard.press('Escape')
        if args.resume:
            button('Guild Hall').click()
            expect(page.locator('.ng-roster')).to_contain_text('Quiet Lanterns')
            expect(page.locator('.ng-message-body')).to_contain_text('Keep a light for tomorrow.')
            town()
            button('Bazaar').click()
            button('Ledger').click()
            expect(page.locator('.nb-ledger-row')).to_have_count(3)
            town()
        button('Realm Ladder').click()
        page.locator('.nl-workspace').wait_for()
        expect(page.locator('.nl-row')).to_have_count(1)
        assert 'not a Steam or global leaderboard' in page.locator('.nl-workspace').inner_text()
        sizes('ladder',['.nl-records','.nl-your-climb','.nl-filters','.nl-your-climb > .q-btn'])
        page.get_by_label('Chronicle mode',exact=True).click()
        page.get_by_role('option',name='All Local Chronicles',exact=True).click()
        expect(page.locator('.nl-row')).to_have_count(3)
        sizes('ladder-all',['.nl-table'])
        button('My Ascents').click()
        expect(page.locator('.nl-history')).to_contain_text('Your first ascension is ahead.')
        assert not errors and not external,(errors,external)
        report = {'passed':True,'cold_resume':args.resume,'coffers':expected,'ownership_preserved':owned() == initial,
                  'viewports':reports,'page_errors':errors,'external_requests':external}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))
        browser.close()


if __name__ == '__main__':
    main()
