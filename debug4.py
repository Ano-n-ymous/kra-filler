import asyncio, os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
PIN = os.getenv("KRA_PIN", "").strip()

JS = r"""() => {
    const walker = document.createTreeWalker(
        document.body, NodeFilter.SHOW_TEXT, null
    );
    const found = [];
    let node;
    while (node = walker.nextNode()) {
        const text = node.nodeValue.trim();
        if (
            text.length > 0 &&
            text.length <= 30 &&
            /\d/.test(text) &&
            (/\+/.test(text) || /\-/.test(text)) &&
            !/P\.O/.test(text) &&
            !/Tel/.test(text) &&
            text.indexOf('\n') === -1
        ) {
            const p = node.parentElement;
            found.push({
                text: text,
                tag: p?.tagName,
                id: p?.id,
                cls: p?.className
            });
        }
    }
    return JSON.stringify(found, null, 2);
}"""

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="domcontentloaded")
        await page.wait_for_selector("#logid", timeout=15000)
        await page.fill("#logid", PIN)
        await page.click("a:has-text('Continue')")
        await page.wait_for_timeout(2000)
        result = await page.evaluate(JS)
        print("Text nodes matching math pattern:")
        print(result)
        await browser.close()

asyncio.run(debug())
