#!/usr/bin/env python3
"""Optional real-browser smoke using installed Firefox + stdlib Marionette.

Synthetic fixtures only; isolated profile and loopback HTTP root. No downloads,
real human reviews, user browser state, model inference or third-party packages.
"""
import functools
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import threading
import time
import unittest
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

import test_review_workbench as fixture_tests


class Marionette:
    def __init__(self, socket_):
        self.socket, self.counter = socket_, 0
        self.receive()  # Protocol greeting.

    def receive(self):
        prefix = b''
        while not prefix.endswith(b':'):
            byte = self.socket.recv(1)
            if not byte or len(prefix) > 12:
                raise RuntimeError('invalid Marionette frame')
            prefix += byte
        length = int(prefix[:-1])
        if not 0 < length < 10_000_000:
            raise RuntimeError('oversized Marionette frame')
        body = b''
        while len(body) < length:
            block = self.socket.recv(length-len(body))
            if not block:
                raise RuntimeError('closed Marionette connection')
            body += block
        return json.loads(body)

    def command(self, name, params=None):
        self.counter += 1
        message = json.dumps([0, self.counter, name, params or {}]).encode()
        self.socket.sendall(str(len(message)).encode()+b':'+message)
        response = self.receive()
        if response[:2] != [1, self.counter]:
            raise RuntimeError(f'unexpected Marionette response: {response!r}')
        if response[2]:
            raise RuntimeError(f'{name}: {response[2]}')
        return response[3]

    def script(self, source, async_=False):
        result = self.command('WebDriver:ExecuteAsyncScript' if async_ else 'WebDriver:ExecuteScript',
                              {'script': source, 'args': [], 'newSandbox': False,
                               'sandbox': None, 'filename': 'synthetic-workbench-test'})
        return result.get('value') if isinstance(result, dict) and set(result) == {'value'} else result


@unittest.skipUnless(shutil.which('firefox'), 'optional installed Firefox unavailable')
class FirefoxWorkbenchTests(unittest.TestCase):
    def test_real_dom_images_navigation_drafts_exports_and_file_page(self):
        fixture = fixture_tests.ReviewWorkbenchTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        page, bundle, _ = fixture.generate('pair')
        originals = {path: path.read_bytes() for path in [fixture.pair_dir/'reviews.csv', fixture.pair_dir/'sample.json']}
        profile = fixture.root/'firefox-profile'
        profile.mkdir()
        with socket.socket() as available:
            available.bind(('127.0.0.1', 0))
            port = available.getsockname()[1]
        preferences = {
            'marionette.port': port, 'marionette.host': '127.0.0.1',
            'browser.shell.checkDefaultBrowser': False, 'browser.startup.page': 0,
            'browser.startup.homepage': 'about:blank', 'browser.startup.homepage_override.mstone': 'ignore',
            'browser.download.folderList': 2, 'browser.download.dir': str(profile/'downloads'),
            'browser.download.useDownloadDir': True,
            'datareporting.healthreport.uploadEnabled': False, 'toolkit.telemetry.enabled': False,
            'network.captive-portal-service.enabled': False, 'network.connectivity-service.enabled': False,
        }
        (profile/'user.js').write_text(''.join('user_pref('+json.dumps(key)+', '+json.dumps(value)+');\n'
                                             for key, value in preferences.items()))
        class QuietHandler(SimpleHTTPRequestHandler):
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(fixture.root)))
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        env = dict(os.environ, MOZ_HEADLESS='1', MOZ_CRASHREPORTER_DISABLE='1', MOZ_DISABLE_NONLOCAL_CONNECTIONS='1')
        log = (profile/'browser.log').open('w')
        self.addCleanup(log.close)
        process = subprocess.Popen([shutil.which('firefox'), '--headless', '--no-remote',
                                    '--profile', str(profile), '--marionette', 'about:blank'],
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        def stop():
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
        self.addCleanup(stop)
        connection = None
        for _ in range(150):
            if process.poll() is not None:
                break
            try:
                connection = socket.create_connection(('127.0.0.1', port), timeout=.5)
                break
            except OSError:
                time.sleep(.1)
        if connection is None:
            log.flush()
            self.fail('Firefox Marionette unavailable: '+(profile/'browser.log').read_text()[-3000:])
        self.addCleanup(connection.close)
        connection.settimeout(20)
        browser = Marionette(connection)
        browser.command('WebDriver:NewSession', {'capabilities': {'alwaysMatch': {}}})
        browser.command('WebDriver:SetTimeouts', {'script': 10000, 'pageLoad': 20000})
        url = f'http://127.0.0.1:{server.server_port}/pairs/workbench.html'
        browser.command('WebDriver:Navigate', {'url': url})
        def wait(expression):
            for _ in range(100):
                result = browser.script('return '+expression)
                if result:
                    return result
                time.sleep(.05)
            self.fail('Browser condition timed out: '+expression)
        wait('document.querySelector("#fields [name=identity]") !== null')
        wait('[...document.querySelectorAll("#images img")].length===2 && [...document.querySelectorAll("#images img")].every(x=>x.naturalWidth===16)')
        self.assertEqual(browser.script('return document.querySelector("[name=identity]").value'), '')
        self.assertEqual(browser.script('return document.querySelector("[name=confidence]").value'), '')
        self.assertEqual(browser.script('return document.querySelectorAll("script").length'), 3)
        # Prevent actual downloads. Inspect the actual browser Blob instead.
        browser.script("window.__downloads=[]; URL.createObjectURL=b=>{window.__downloads.push(b);return 'blob:synthetic'}; HTMLAnchorElement.prototype.click=function(){}; return true")
        browser.script("document.getElementById('globalReviewer').value='Synthetic browser reviewer'; document.getElementById('saveNext').click(); return true")
        self.assertEqual(browser.script('return localStorage.length'), 0, 'no-decision commit must not create a draft')
        first = browser.script('return document.getElementById("caseSelect").value')
        def input_(field, value):
            browser.script('var x=document.querySelector('+json.dumps('[name='+field+']')+'); x.value='+json.dumps(value)+'; x.dispatchEvent(new Event("input",{bubbles:true})); return true')
        input_('evidence', 'Synthetic "quote", étage\nsecond line')
        wait('document.getElementById("status").textContent.includes("Draft saved locally")')
        browser.command('WebDriver:Refresh')
        wait('document.querySelector("#fields [name=identity]") !== null')
        self.assertEqual(browser.script('return document.querySelector("[name=evidence]").value'), 'Synthetic "quote", étage\nsecond line')
        browser.script("window.__downloads=[]; URL.createObjectURL=b=>{window.__downloads.push(b);return 'blob:synthetic'}; HTMLAnchorElement.prototype.click=function(){}; document.getElementById('globalReviewer').value='Synthetic browser reviewer'; return true")
        input_('identity', 'ambiguous')
        input_('confidence', 'low')
        browser.script("document.getElementById('hideCompleted').checked=true; document.getElementById('saveNext').click(); return true")
        wait('document.getElementById("caseSelect").value !== '+json.dumps(first))
        self.assertNotEqual(browser.script('return document.getElementById("caseSelect").value'), first)
        browser.script("document.getElementById('exportCSV').click(); return true")
        text = browser.script('var done=arguments[arguments.length-1]; window.__downloads[0].text().then(done)', async_=True)
        returned = fixture.root/'firefox-returned.csv'
        returned.write_text(text, encoding='utf-8')
        from validate_pair_audit import validate
        report = validate(fixture.pair_dir/'sample.json', returned, fixture.pm, fixture.mm, fixture.pub, fixture.mp)
        self.assertEqual(report['counts']['ambiguous'], 1)
        self.assertIsNone(report['cleanliness'])
        self.assertEqual({path: path.read_bytes() for path in originals}, originals)
        # Open the same page twice before either edits again. A stale tab must
        # never replace the first tab's newly saved work, even on a disjoint row.
        def unwrap(value):
            return value['value'] if isinstance(value, dict) and set(value) == {'value'} else value
        first_handle = unwrap(browser.command('WebDriver:GetWindowHandle'))
        second_window = unwrap(browser.command('WebDriver:NewWindow', {'type': 'tab'}))
        browser.command('WebDriver:SwitchToWindow', {'handle': second_window['handle']})
        browser.command('WebDriver:Navigate', {'url': url})
        wait('document.querySelector("#fields [name=identity]") !== null')
        browser.command('WebDriver:SwitchToWindow', {'handle': first_handle})
        input_('evidence', 'First tab saved second-case work')
        wait('document.getElementById("status").textContent.includes("Draft saved locally")')
        stored = browser.script('return localStorage.getItem(localStorage.key(0))')
        browser.command('WebDriver:SwitchToWindow', {'handle': second_window['handle']})
        third = bundle['rows'][2]['key']
        browser.script('var select=document.getElementById("caseSelect"); select.value='+json.dumps(third)+'; select.dispatchEvent(new Event("change")); return true')
        input_('evidence', 'Second tab unsaved separate-case work')
        wait('document.getElementById("status").textContent.includes("Another tab")')
        self.assertEqual(browser.script('return localStorage.getItem(localStorage.key(0))'), stored)
        self.assertEqual(browser.script('return document.querySelector("[name=evidence]").value'), 'Second tab unsaved separate-case work')
        self.assertFalse(browser.script('return document.getElementById("exportRecovery").hidden'))
        browser.script("window.__downloads=[]; URL.createObjectURL=b=>{window.__downloads.push(b);return 'blob:synthetic'}; HTMLAnchorElement.prototype.click=function(){}; document.getElementById('exportJSON').click(); return true")
        backup = browser.script('var done=arguments[arguments.length-1]; window.__downloads[0].text().then(done)', async_=True)
        self.assertTrue(any(row['fields'].get('evidence') == 'Second tab unsaved separate-case work' for row in json.loads(backup)['rows']))
        browser.command('WebDriver:SwitchToWindow', {'handle': first_handle})
        # The same trusted page must load sibling images as a local file too.
        browser.command('WebDriver:Navigate', {'url': page.resolve().as_uri()})
        wait('document.querySelector("#fields [name=identity]") !== null')
        wait('[...document.querySelectorAll("#images img")].length===2 && [...document.querySelectorAll("#images img")].every(x=>x.naturalWidth===16)')
        self.assertEqual(browser.script('return document.querySelector("[name=identity]").value'), '')
        construction_page, _, _ = fixture.generate('construction')
        browser.command('WebDriver:Navigate', {'url': construction_page.resolve().as_uri()})
        wait('document.querySelector("#fields [name=applicability]") !== null')
        wait('[...document.querySelectorAll("#images img")].length===1 && document.querySelector("#images img").naturalWidth===16')
        self.assertEqual(browser.script('return document.querySelectorAll("script").length'), 3)
        self.assertIn('</script> __REVIEW_UI__', browser.script('return document.getElementById("context").textContent'))
        self.assertEqual(browser.script('return document.querySelector("[name=applicability]").value'), '')
        self.assertEqual(browser.script('return document.querySelector("[name=reviewer]").value'), '')


if __name__ == '__main__':
    unittest.main()
