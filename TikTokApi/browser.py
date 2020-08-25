import asyncio
import pyppeteer
import random
import time
import string
import requests
import logging
from threading import Thread

# Import Detection From Stealth
from .stealth import stealth

from .get_acrawler import get_acrawler

async_support = False
def set_async():
    global async_support
    async_support = True

logger = logging.getLogger("tiktokapi.browser")

REFRESH_INTERVAL = 1800 # 30 min
class browser:
    def __init__(self, url, language='en', proxy=None, find_redirect=False, single_instance=False, api_url=None, debug=False, newParams=False):
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

        self.userAgent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/84.0.4147.125 Safari/537.36"
        self.args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certifcate-errors",
            "--ignore-certifcate-errors-spki-list",
            "--user-agent=" + self.userAgent
        ]

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
        
        if async_support:
            loop = asyncio.new_event_loop()
            t = Thread(target=self.__start_background_loop, args=(loop, ), daemon=True)
            t.start()
            if find_redirect:
                fut = asyncio.run_coroutine_threadsafe(self.find_redirect(), loop)
            elif newParams:
                fut = asyncio.run_coroutine_threadsafe(self.newParams(), loop)
            else:
                fut = asyncio.run_coroutine_threadsafe(self.start(), loop)
            fut.result()
        else:
            try:
                self.loop = asyncio.new_event_loop()
                if find_redirect:
                    self.loop.run_until_complete(self.find_redirect())
                elif newParams:
                    self.loop.run_until_complete(self.newParams())
                else:
                    self.loop.run_until_complete(self.start())
            except:
                self.loop.close()

    def __start_background_loop(self, loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    def call(self, url, language='en', proxy=None):
        logger.info("browser.call %s" % url)
        self.url = url
        if self.url.endswith("&verifyFp="):
            self.url = self.url[:-10]
        self.language = language
        self.proxy = proxy
        try:
            self.loop.run_until_complete(asyncio.wait_for(self.start(), 500))
        except asyncio.TimeoutError:
            logger.info("browser did not respond in 500 seconds")
            try:
                self.loop.run_until_complete(asyncio.wait_for(self.stop(), 300))
            except Exception:
                logger.info("browser close failed")
                self.page = None
                self.browser = None
        logger.info("browser.call finished")

    async def newParams(self) -> None:
        self.browser = await pyppeteer.launch(self.options)
        self.page = await self.browser.newPage()
        await self.page.goto("about:blank")

        #self.browser_language = await self.page.evaluate("""() => { return navigator.language || navigator.userLanguage; }""")
        self.browser_language = ""
        #self.timezone_name = await self.page.evaluate("""() => { return Intl.DateTimeFormat().resolvedOptions().timeZone; }""")
        self.timezone_name = ""
        #self.browser_platform = await self.page.evaluate("""() => { return window.navigator.platform; }""")
        self.browser_platform = ""
        #self.browser_name = await self.page.evaluate("""() => { return window.navigator.appCodeName; }""")
        self.browser_name = ""
        #self.browser_version = await self.page.evaluate("""() => { return window.navigator.appVersion; }""")
        self.browser_version = ""

        self.width = await self.page.evaluate("""() => { return screen.width; }""")
        self.height = await self.page.evaluate("""() => { return screen.height; }""")

        await self.browser.close()
        self.browser.process.communicate()
        self.browser = None

        return 0

    def randomWord(self, count):
        return ''.join(random.choice(string.ascii_lowercase + string.ascii_uppercase + string.digits) for i in range(count))

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

            current_time = int(time.time())
            if self.last_refresh + REFRESH_INTERVAL < current_time:
                logger.info("refreshing page")
                self.last_refresh = current_time
                # might have to switch to a tiktok url if they improve security
                # await self.page.goto("https://www.bing.com/")
                await self.page.goto("about:blank", {
                    'waitUntil': "load"
                })

                self.userAgent = await self.page.evaluate("""() => {return navigator.userAgent; }""")

            self.verifyFp = '_'.join(['verify_', self.randomWord(8), self.randomWord(8), self.randomWord(4), self.randomWord(4), self.randomWord(4), self.randomWord(12)])

            await self.page.evaluate("() => { " + get_acrawler() + " }")
            
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
                logger.info(self.data)
                #self.data = await json.loads(self.data)

            if self.single_instance is False:
                await self.stop()
        except:
            if self.single_instance is False:
                await self.stop()


    async def stop(self):
        try:
            await self.page.close()
        except Exception:
            logger.exception("page close failed")
        try:
            await self.browser.close()
            self.browser.process.communicate()
        except Exception:
            logger.exception("browser close failed")
        self.page = None
        self.browser = None


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
            self.browser.process.communicate()

        except:
            await self.browser.close()
            self.browser.process.communicate()

    def __format_proxy(self, proxy):
        if proxy != None:
            return {
                'http': proxy.replace('socks5', 'socks5h'),
                'https': proxy.replace('socks5', 'socks5h')
            }
        else:
            return None

    def __get_js(self, proxy=None):
        return requests.get("https://sf16-muse-va.ibytedtos.com/obj/rc-web-sdk-gcs/acrawler.js", proxies=self.__format_proxy(proxy), timeout=300).text