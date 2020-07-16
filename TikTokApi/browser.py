import asyncio
import pyppeteer
import random
import time
import json
import string
import atexit
import requests

# Import Detection From Stealth
from .stealth import stealth

REFRESH_INTERVAL = 1800 # 30 min
class browser:
    def __init__(self, url, language='en', proxy=None, find_redirect=False, single_instance=False, api_url=None, debug=False):
        self.url = url
        self.debug = debug
        self.proxy = proxy
        self.api_url = api_url
        self.referrer = "https://www.tiktok.com/"
        self.language = language

        self.single_instance = single_instance
        self.last_refresh = 0
        self.browser = None
        self.page = None

        self.userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.0 Safari/537.36)"
        self.args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certifcate-errors",
            "--ignore-certifcate-errors-spki-list",
             "--user-agent=" + self.userAgent,
        ]

        #self.args = []
        # "--user-agent=" + self.userAgent,

        if proxy != None:
            if "@" in proxy:
                self.args.append("--proxy-server=" + proxy.split(":")[0] + "://" + proxy.split(
                    "://")[1].split(":")[1].split("@")[1] + ":" + proxy.split("://")[1].split(":")[2])
                self.args.append('--host-resolver-rules="MAP * ~NOTFOUND"')
            else:
                self.args.append("--proxy-server=" + proxy)
                self.args.append('--host-resolver-rules="MAP * ~NOTFOUND"')
        self.options = {
            'args': self.args,
            'headless': True,
            'ignoreHTTPSErrors': True,
            'userDataDir': "./tmp",
            'handleSIGINT': False,
            'handleSIGTERM': False,
            'handleSIGHUP': False
        }

        self.loop = asyncio.new_event_loop()

        if find_redirect:
            self.loop.run_until_complete(self.find_redirect())
        else:
            self.loop.run_until_complete(self.start())

    def call(self, url, language='en', proxy=None):
        print("browser.call %s" % url)
        self.url = url
        self.language = language
        self.proxy = proxy
        self.loop.run_until_complete(self.start())
        print("browser.call finished")

    async def start(self):
        try:
            if self.browser is None:
                self.browser = await pyppeteer.launch(self.options)
                self.page = await self.browser.newPage()

                await self.page.evaluateOnNewDocument("""() => {
            delete navigator.__proto__.webdriver;
                }""")

                # Check for user:pass proxy
                if self.proxy != None:
                    if "@" in self.proxy:
                        await self.page.authenticate({
                            'username': self.proxy.split("://")[1].split(":")[0],
                            'password': self.proxy.split("://")[1].split(":")[1].split("@")[0]
                        })

                await stealth(self.page)

                # await self.page.emulate({
                #    'viewport': {'width': random.randint(320, 1920), 'height': random.randint(320, 1920), },
                #    'deviceScaleFactor': random.randint(1, 3),
                #    'isMobile': random.random() > 0.5,
                #    'hasTouch': random.random() > 0.5
                # })
            current_time = int(time.time())
            if self.last_refresh + REFRESH_INTERVAL < current_time:
                # might have to switch to a tiktok url if they improve security
                await self.page.goto("https://www.bing.com/")

                self.last_refresh = current_time
                self.userAgent = await self.page.evaluate("""() => {return navigator.userAgent; }""")

            self.verifyFp = None

            #
            # Probably need to unmark this at a later point
            #
            #for c in await self.page.cookies():
            #    if c['name'] == "s_v_web_id":
            #        self.verifyFp = c['value']

            if self.verifyFp is None:
                if self.debug:
                    print("No verifyFp cookie.")
        
                key = ''
                for i in range(16):
                    key += random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits)
                self.verifyFp = key

            await self.page.evaluate("() => { " + self.__get_js(proxy=self.proxy) + " }")
            
            self.signature = await self.page.evaluate('''() => {
            var url = "''' + self.url + "&verifyFp=" + self.verifyFp + '''"
            var token = window.byted_acrawler.sign({url: url});
            return token;
            }''')

            if self.api_url != None:
                await self.page.goto(self.url +
                                    "&verifyFp=" + self.verifyFp +
                                    "&_signature=" + self.signature, {
                                        'waitUntil': "load"
                                    })

                self.data = await self.page.content()
                print(self.data)
                #self.data = await json.loads(self.data)

            if self.single_instance is False:
                await self.browser.close()
        except:
            if self.single_instance is False:
                await self.browser.close()

    async def find_redirect(self):
        try:
            self.browser = await pyppeteer.launch(self.options)
            self.page = await self.browser.newPage()

            await self.page.evaluateOnNewDocument("""() => {
        delete navigator.__proto__.webdriver;
    }""")

            # Check for user:pass proxy
            if self.proxy != None:
                if "@" in self.proxy:
                    await self.page.authenticate({
                        'username': self.proxy.split("://")[1].split(":")[0],
                        'password': self.proxy.split("://")[1].split(":")[1].split("@")[0]
                    })

            await stealth(self.page)

            # await self.page.emulate({'viewport': {
            #    'width': random.randint(320, 1920),
            #    'height': random.randint(320, 1920),
            #    'deviceScaleFactor': random.randint(1, 3),
            #    'isMobile': random.random() > 0.5,
            #    'hasTouch': random.random() > 0.5
            # }})

            # await self.page.setUserAgent(self.userAgent)

            await self.page.goto(self.url, {
                'waitUntil': "load"
            })

            self.redirect_url = self.page.url

            await self.browser.close()

        except:
            await self.browser.close()

    def __format_proxy(self, proxy):
        if proxy != None:
            return {
                'http': proxy.replace('socks5', 'socks5h'),
                'https': proxy.replace('socks5', 'socks5h')
            }
        else:
            return None

    def __get_js(self, proxy=None):
        return requests.get("https://sf16-muse-va.ibytedtos.com/obj/rc-web-sdk-gcs/acrawler.js", proxies=self.__format_proxy(proxy)).text