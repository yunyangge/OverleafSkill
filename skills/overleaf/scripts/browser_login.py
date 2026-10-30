"""Interactive isolated-browser login. Requires the optional Playwright package/browser."""
from credentials import save_cookie
from online import Online
import os


def login(project, profile):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('Install playwright in this interpreter, then run python -m playwright install chromium')
    with sync_playwright() as playwright:
        proxy = os.environ.get('HTTPS_PROXY') or os.environ.get('https_proxy') or os.environ.get('HTTP_PROXY')
        options = {'headless': False}
        if proxy:
            options['proxy'] = {'server': proxy, 'bypass': os.environ.get('NO_PROXY', '').replace(',', ';')}
        browser = playwright.chromium.launch(**options)
        try:
            context = browser.new_context()
            page = context.new_page()
            page.goto('https://www.overleaf.com/login')
            input('Complete login in the opened browser, then press Enter here. Do not enter credentials in chat. ')
            cookies = context.cookies('https://www.overleaf.com/project')
            cookie = '; '.join(c['name'] + '=' + c['value'] for c in cookies)
            Online(project, cookie=cookie).csrf()
            save_cookie(cookie, profile)
            print('Website session verified and saved to OS-protected storage.')
        finally:
            browser.close()
