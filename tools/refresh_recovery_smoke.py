"""Disposable browser regression for deleted slots, burst refresh and recovery.

Runs a standalone test fixture with the shipping page-refresh binder, never a
game profile or a shipped debug route. Intentional errors stay in its report.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def serve(port):
    import asyncio

    os.environ['NICEGUI_STORAGE_PATH'] = str(ROOT/f'.local-test/refresh-fixture-ui-{port}')
    from nicegui import ui

    from steam_client.refresh import bind_page_refresh

    @ui.page('/')
    def fixture():
        state = {'count':0,'fail':False}
        async def burst():
            state['count'] += 1
            queue.request(force=True)
            # The submitting button and its slot have just been replaced.
            await asyncio.sleep(.02)
            for _ in range(12):
                state['count'] += 1
                queue.request()
            await asyncio.sleep(.35)
            state['count'] += 1
            queue.request()
        def fail():
            state['fail'] = True
            queue.request(force=True)
        @ui.refreshable
        def panel():
            if state['fail']:
                state['fail'] = False
                raise RuntimeError('Intentional transient renderer failure')
            ui.label(str(state['count'])).classes('qa-count')
            ui.button('Replace Then Refresh', on_click=burst)
            ui.button('Fail One View', on_click=fail)
        queue = bind_page_refresh(ui.context.client, panel.refresh)
        panel()
    ui.run(host='127.0.0.1',port=port,show=False,reload=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8897)
    parser.add_argument('--serve',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'.local-test/refresh-recovery-report.json')
    args = parser.parse_args()
    if args.serve:
        serve(args.port)
        return
    from playwright.sync_api import expect, sync_playwright
    output = args.output.resolve()
    if not output.is_relative_to(ROOT/'.local-test'):
        raise SystemExit('The report must be in .local-test.')
    output.parent.mkdir(parents=True,exist_ok=True)
    log = output.with_suffix('.log')
    with log.open('w',encoding='utf-8') as stream:
        process = subprocess.Popen([sys.executable,__file__,'--serve','--port',str(args.port)],cwd=ROOT,stdout=stream,stderr=stream)
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
                page = browser.new_page()
                for attempt in range(30):
                    try:
                        page.goto(f'http://127.0.0.1:{args.port}')
                        break
                    except Exception:
                        if attempt == 29:
                            raise
                        time.sleep(.2)
                for i in range(4):
                    page.get_by_role('button',name='Replace Then Refresh',exact=True).click()
                    expect(page.locator('.qa-count')).to_have_text(str((i+1)*14))
                page.get_by_role('button',name='Fail One View',exact=True).click()
                expect(page.get_by_role('button',name='Retry View',exact=True)).to_be_visible()
                page.get_by_role('button',name='Retry View',exact=True).click()
                expect(page.locator('.qa-count')).to_have_text('56')
                expect(page.locator('.pd-view-recovery')).not_to_be_visible()
                page.get_by_role('button',name='Replace Then Refresh',exact=True).click()
                expect(page.locator('.qa-count')).to_have_text('70')
                browser.close()
            report = {'passed':True,'burst_replacements':5,'counter':70,'render_error_recovered':True}
            output.write_text(json.dumps(report,indent=2),encoding='utf-8')
            print(json.dumps(report))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
