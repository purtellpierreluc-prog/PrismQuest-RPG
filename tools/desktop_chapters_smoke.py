"""Exercise actual purchases and prestige, using only disposable test profiles."""

import argparse
import copy
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright


def owned(slot):
    p=slot.get('player')
    items=list(p['inventory'])+[i for i in p['equipped'].values() if i] if p else list(slot.get('carryover_inventory',[]))
    items+=slot.get('vault_items',[])
    for family in slot.get('saved_item_sets',{}).values():
        items+=list(family.values())
    return Counter(json.dumps(i,sort_keys=True) for i in items)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,required=True)
    parser.add_argument('--profile',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',choices=['success','failure','blind'],default='blind')
    parser.add_argument('--skip-market',action='store_true')
    parser.add_argument('--reload-judging',action='store_true')
    parser.add_argument('--quick-reveal',action='store_true')
    parser.add_argument('--reduced-motion',action='store_true')
    args=parser.parse_args()
    if '.local-test' not in args.profile.resolve().parts:
        raise SystemExit('Only disposable .local-test profiles may be used.')
    args.output.mkdir(parents=True,exist_ok=True)
    def slots():
        return json.loads((args.profile/'saves/chronicles.json').read_text(encoding='utf-8'))['slots']
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1280,'height':720})
        if args.reduced_motion:
            page.emulate_media(reduced_motion='reduce')
        errors,external,reports=[],[],[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def route(request):
            if urlsplit(request.request.url).hostname in {'127.0.0.1','localhost'}:request.continue_()
            else:external.append(request.request.url);request.abort()
        page.route('**/*',route)
        def button(name):return page.get_by_role('button',name=name,exact=True).first
        def check(name,selectors=()):
            page.mouse.move(4,4)
            page.wait_for_timeout(200)
            metrics=page.evaluate('''() => ({w:innerWidth,h:innerHeight,sw:document.scrollingElement.scrollWidth,sh:document.scrollingElement.scrollHeight})''')
            assert metrics['sw']<=metrics['w']+1 and metrics['sh']<=metrics['h']+1,(name,metrics)
            for selector in selectors:
                for box in page.locator(selector).evaluate_all('els=>els.map(e=>{let r=e.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,h:r.height};})'):
                    assert box['h']>0 and box['bottom']<=metrics['h']+1 and box['right']<=metrics['w']+1,(name,selector,box,metrics)
            reports.append({'scene':name,**metrics})
            page.screenshot(path=str(args.output/f'{name}-{metrics["w"]}.png'))
        def sizes(name,selectors=()):
            for w,h in [(1280,720),(960,600),(800,500),(1920,1080)]:
                page.set_viewport_size({'width':w,'height':h});check(name,selectors)
            page.set_viewport_size({'width':1280,'height':720})
        page.goto(f'http://127.0.0.1:{args.port}',wait_until='networkidle')
        button('Play').click();button('Open Core').click()
        page.locator('.pd-town-workspace').wait_for()
        if not args.skip_market:
            button('Marketplace').click()
            page.locator('.pm-workspace').wait_for()
            expect(page.locator('.pm-offer')).to_have_count(3)
            sizes('market-browse',['.pm-intro','.pm-offers','.pm-inspection'])
            button('Inspect The Essential').click()
            page.locator('.pm-item-sheet').wait_for()
            sheet=page.locator('.pm-item-sheet').get_attribute('id')
            button('Inspect The Wildcard').hover();page.wait_for_timeout(700)
            assert page.locator('.pm-item-sheet').get_attribute('id')==sheet
            sizes('market-inspect',['.pm-inspection','.pm-purchase'])
            review=page.get_by_role('button',name='Review Purchase /',exact=False).first
            fee=int(re.search(r'([\d,]+)g',review.inner_text())[1].replace(',',''))
            before=slots()[0]
            review.click();check('market-confirm',['.pm-purchase'])
            assert slots()[0]['player']['gold']==before['player']['gold']
            button('Confirm Purchase').click();page.locator('.pm-receipt').wait_for()
            after=slots()[0]
            assert after['player']['gold']==before['player']['gold']-fee
            assert len(after['player']['inventory'])==len(before['player']['inventory'])+1
            assert after['player']['equipped']==before['player']['equipped']
            page.wait_for_timeout(1000)
            check('market-acquired',['.pm-purchase','.pm-inspection'])
            audio=page.evaluate('window.PrismAudio.inspect()')
            assert audio['played'].get('story_purchase')==1 and not audio['failed'],audio
            button('Return to Town').click();button('Marketplace').click()
            page.locator('.pm-offer.sold').wait_for()
            assert slots()[0]['player']['gold']==after['player']['gold']
            button('Return to Town').click()
        before=copy.deepcopy(slots())
        button('Prismatic Quest').click()
        page.locator('.ps-scene').wait_for()
        assert slots()[0]['player']['gold']==before[0]['player']['gold']
        sizes('threshold',['.ps-scene','.ps-threshold-art','.ps-threshold-brief','.ps-primary'])
        button('Review the Rite').click()
        check('commit-climb')
        enter=page.get_by_role('button',name='Enter the Rite /',exact=False).first
        fee=int(re.search(r'(\d+)g',enter.inner_text())[1])
        enter.click();page.locator('.ps-chamber').wait_for()
        assert slots()[0]['player']['gold']==before[0]['player']['gold']-fee
        assert 'solution' not in page.locator('[data-ps-signal]').get_attribute('data-ps-signal')
        sizes('chamber',['.ps-chamber','.ps-essences','.ps-vessels','.ps-commit-zone','.ps-ritual-guide > button'])
        for attempt in range(6):
            if page.locator('.ps-aftermath').count():break
            lights=page.locator('.ps-essence:not(.bound):not([disabled])')
            essence=lights.first.get_attribute('data-ps-essence')
            target_light=page.locator(f'[data-ps-essence="{essence}"]')
            if target_light.get_attribute('aria-pressed') != 'true':
                target_light.click()
            try:
                expect(page.locator('.ps-essence.selected')).to_have_count(1)
            except AssertionError:
                page.screenshot(path=str(args.output/'selection-failure.png'))
                print({'attempt':attempt,'light':essence,'signal':page.locator('[data-ps-signal]').get_attribute('data-ps-signal'),
                       'lights':page.locator('.ps-essence').evaluate_all('es=>es.map(e=>({k:e.dataset.psEssence,cl:e.className}))')},flush=True)
                raise
            vessels=page.locator('.ps-vessel:not([disabled])')
            if args.mode!='blind':
                oracle=json.loads((args.profile/'qa-oracle.json').read_text())
                correct=oracle['solution'][essence]
                vessel=correct if args.mode=='success' else next(v for v in oracle['solution'].values() if v!=correct)
                target=page.locator(f'[data-ps-vessel="{vessel}"]')
            else:target=vessels.first
            target.click()
            expect(page.locator('.ps-vessel.selected')).to_have_count(1)
            assert not page.locator('.ps-aftermath').count()
            assert json.loads(page.locator('[data-ps-signal]').get_attribute('data-ps-signal'))['phase']=='ready'
            assert len(slots()[0].get('pq_ledger_entries',[]))==len(before[0].get('pq_ledger_entries',[]))
            button('Commit Offering').click()
            page.wait_for_timeout(180)
            check('judging-'+str(attempt))
            if args.reload_judging and attempt==0:
                page.reload(wait_until='networkidle')
                page.locator('.ps-chamber').wait_for()
                # A fresh document requires a trusted gesture to unlock audio.
                page.mouse.click(4,4)
            if args.quick_reveal:
                page.locator('.ps-quick').click()
            page.wait_for_function('''() => {const el=document.querySelector('[data-ps-signal]');if(!el)return false;return !['judging','matched','rejected','unsealing'].includes(JSON.parse(el.dataset.psSignal).phase)}''')
            if page.get_by_role('button',name='Continue Offering',exact=True).count():
                page.get_by_role('button',name='Continue Offering',exact=True).first.click()
                page.wait_for_function('''() => {const el=document.querySelector('[data-ps-signal]');return el&&!['judging','matched','rejected','unsealing','interrupted'].includes(JSON.parse(el.dataset.psSignal).phase)}''')
        page.locator('.ps-aftermath').wait_for()
        signal=json.loads(page.locator('[data-ps-signal]').get_attribute('data-ps-signal'))
        assert signal['phase'] in ('success','failure','final')
        if args.mode=='success':assert signal['phase'] in ('success','final')
        if args.mode=='failure':assert signal['phase']=='failure'
        page.wait_for_timeout(300)
        audio=page.evaluate('window.PrismAudio.inspect()')
        assert audio['chapterVoices']==1 and audio['scoreMode']=='aftermath',audio
        page.wait_for_timeout(2000)
        sizes('aftermath',['.ps-aftermath','.ps-aftermath-body','.ps-aftermath-primary'])
        audio=page.evaluate('window.PrismAudio.inspect()')
        cue={'success':'rite_ascend','failure':'story_fracture','final':'rite_complete'}[signal['phase']]
        assert audio['played'].get(cue)==1 and not audio['failed'],audio
        if args.reduced_motion:
            assert page.evaluate('PrismChapters.inspect().animations')==0
        after=slots()
        assert after[1:]==before[1:]
        assert owned(after[0])==owned(before[0])
        assert len(after[0]['pq_ledger_entries'])==len(before[0].get('pq_ledger_entries',[]))+1
        assert not page.locator('.q-dialog').filter(has_text='You have succeeded the PQ!').count()
        if signal['phase']=='final':
            assert after[0]['player'] is not None
            button('Return Victorious').click();page.locator('.pd-town-workspace').wait_for()
        else:
            assert after[0]['player'] is None
            button('Choose Your Next Legend' if signal['phase']=='success' else 'Begin the Next Climb').click()
            page.wait_for_timeout(300)
            assert not page.locator('.ps-aftermath').count()
        assert not errors,errors
        assert not external,external
        report={'passed':True,'phase':signal['phase'],'errors':errors,'external':external,'scenes':reports,'conservation':True}
        (args.output/'report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps({'passed':True,'outcome':signal['phase'],'scenes':len(reports),'conservation':True}))
        browser.close()


if __name__=='__main__':main()
