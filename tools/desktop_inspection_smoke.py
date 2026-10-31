"""Quick browser check of Ctrl-gated inspection; no game saves or server required."""

from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    assets = ROOT/'steam_client/static'
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True)
        page = browser.new_page(viewport={'width':1000,'height':700})
        errors = []
        page.on('pageerror',lambda error:errors.append(str(error)))
        page.set_content('''<html data-pq-nocturne="true"><body>
          <button data-pd-inspect-key="test" id="anchor" style="margin:60px;width:200px;height:60px">Inspect
          <span class="pd-inspect-content" hidden>Formula details</span></button>
          <div class="mq-item-hover-floating" id="legacy" style="position:fixed;top:400px">Legacy Lab tooltip</div>
        </body></html>''')
        page.add_style_tag(path=str(assets/'controls.css'))
        page.add_style_tag(content='.pd-item-inspection {position:fixed;width:250px;background:#111;color:white}.pd-item-inspection[hidden]{display:none!important}')
        page.add_script_tag(path=str(assets/'inspections.js'))
        anchor,overlay = page.locator('#anchor'),page.locator('#pd-item-inspection')
        anchor.hover()
        expect(overlay).not_to_be_visible()
        expect(page.locator('#legacy')).not_to_be_visible()
        page.keyboard.down('Control')
        expect(overlay).to_be_visible()
        expect(page.locator('#legacy')).to_be_visible()
        assert overlay.inner_text() == 'Formula details'
        page.locator('#anchor').evaluate('e=>e.replaceWith(e.cloneNode(true))')
        expect(overlay).to_be_visible()
        page.keyboard.up('Control')
        expect(overlay).not_to_be_visible()
        expect(page.locator('#legacy')).not_to_be_visible()
        page.mouse.move(900,600)
        page.keyboard.down('Control')
        anchor.hover()
        expect(overlay).to_be_visible()
        page.keyboard.press('Escape')
        expect(overlay).not_to_be_visible()
        page.keyboard.up('Control')
        anchor.focus()
        expect(overlay).not_to_be_visible()
        page.keyboard.down('Control')
        expect(overlay).to_be_visible()
        page.evaluate("window.dispatchEvent(new Event('blur'))")
        expect(overlay).not_to_be_visible()
        expect(page.locator('#legacy')).not_to_be_visible()
        page.keyboard.up('Control')
        assert not errors,errors
        print('PASS: Ctrl before/after hover, release, refresh, Escape, Ctrl-focus and blur; legacy panels gated.')
        browser.close()


if __name__ == '__main__':
    main()
