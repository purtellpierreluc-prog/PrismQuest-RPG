"""Measure short packaged UI samples; intentionally not a long-session claim."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--seconds', type=int, default=15)
    args = parser.parse_args()
    if not 5 <= args.seconds <= 120:
        raise SystemExit('Sample duration must be 5-120 seconds.')
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe', headless=True)
        page = browser.new_page(viewport={'width': 1280, 'height': 720})
        errors, external = [], []
        traffic = {'received_frames': 0, 'received_payload_bytes': 0, 'sent_frames': 0, 'sent_payload_bytes': 0}

        def count(payload, received):
            prefix = 'received' if received else 'sent'
            traffic[prefix + '_frames'] += 1
            traffic[prefix + '_payload_bytes'] += len(payload.encode('utf-8') if isinstance(payload, str) else payload)

        def socket_opened(socket):
            socket.on('framereceived', lambda payload: count(payload, True))
            socket.on('framesent', lambda payload: count(payload, False))

        def route(request):
            if urlsplit(request.request.url).hostname in {'localhost', '127.0.0.1'}:
                request.continue_()
            else:
                external.append(request.request.url)
                request.abort()

        page.on('websocket', socket_opened)
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.route('**/*', route)
        cdp = page.context.new_cdp_session(page)
        cdp.send('Performance.enable')
        page.goto(f'http://127.0.0.1:{args.port}', wait_until='networkidle')
        samples = []

        def metrics():
            return {m['name']: m['value'] for m in cdp.send('Performance.getMetrics')['metrics']}

        def sample(name):
            before, counters = metrics(), dict(traffic)
            page.wait_for_timeout(args.seconds * 1000)
            after = metrics()
            samples.append({
                'scene': name, 'seconds': args.seconds,
                'renderer_task_seconds': after['TaskDuration'] - before['TaskDuration'],
                'js_heap_bytes': after['JSHeapUsedSize'],
                'layout_seconds': after['LayoutDuration'] - before['LayoutDuration'],
                'local_websocket': {key: traffic[key] - counters[key] for key in traffic},
            })

        sample('title-idle')
        page.get_by_role('button', name='Play', exact=True).click()
        page.get_by_role('button', name='Open HC', exact=True).click()
        page.locator('.mq-lab-member-card').first.wait_for()
        assert page.locator('.mq-lab-member-card').count() == 5
        sample('five-member-lab-automatic-combat')
        page.screenshot(path=str(out / 'performance-lab.png'))
        report = {'samples': samples, 'page_errors': errors, 'external_requests': external,
                  'limitations': 'Short headless-Chrome renderer samples, not whole-process/native WebView CPU/RAM, total network framing overhead, or multi-hour soak. Combat may finish during the sample.'}
        (out / 'ui-performance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2))
        assert not errors and not external
        browser.close()


if __name__ == '__main__':
    main()
