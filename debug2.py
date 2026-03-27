"""
Targeted captcha element finder.
Finds the exact element holding the math question like "75 - 5?"
"""
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
PIN = os.getenv("KRA_PIN", "").strip()

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()

        await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="domcontentloaded")
        await page.wait_for_selector("#logid", timeout=15000)
        await page.fill("#logid", PIN)
        await page.click("a:has-text('Continue')")
        await page.wait_for_timeout(2000)

        print("\n" + "="*60)
        print("CAPTCHA AREA — JavaScript DOM inspection")
        print("="*60)

        # 1. Print everything near #captcahText
        result = await page.evaluate("""() => {
            const input = document.getElementById('captcahText');
            if (!input) return 'captcahText input NOT found';

            let output = [];
            // Walk up 3 parent levels and dump their HTML
            let el = input;
            for (let i = 0; i < 4; i++) {
                el = el.parentElement;
                if (!el) break;
                output.push('PARENT ' + i + ' [' + el.tagName + '#' + (el.id||'') + '.' + (el.className||'') + ']:');
                output.push(el.innerText.slice(0, 200));
                output.push('---');
            }
            return output.join('\\n');
        }""")
        print(result)

        # 2. Find ALL elements whose text looks like a math question
        print("\n" + "="*60)
        print("ALL elements with short text containing digits + operator:")
        print("="*60)
        result2 = await page.evaluate("""() => {
            const all = document.querySelectorAll('*');
            const found = [];
            for (const el of all) {
                const text = (el.innerText || el.textContent || '').trim();
                if (
                    text.length > 0 &&
                    text.length <= 25 &&
                    /\\d/.test(text) &&
                    (/\\+/.test(text) || /-/.test(text)) &&
                    !text.includes('\\n') &&
                    !text.includes('P.O')
                ) {
                    found.push({
                        tag: el.tagName,
                        id: el.id,
                        cls: el.className,
                        text: text
                    });
                }
            }
            return JSON.stringify(found, null, 2);
        }""")
        print(result2)

        # 3. Check if it's an image
        print("\n" + "="*60)
        print("Images near captcahText:")
        print("="*60)
        result3 = await page.evaluate("""() => {
            const input = document.getElementById('captcahText');
            if (!input) return 'not found';
            let parent = input.parentElement;
            const imgs = parent ? parent.querySelectorAll('img, canvas') : [];
            return imgs.length + ' image(s) found. src: ' + 
                   Array.from(imgs).map(i => i.src || i.tagName).join(', ');
        }""")
        print(result3)

        print("\n⏸️  Keeping browser open 20s...")
        await asyncio.sleep(20)
        await browser.close()

asyncio.run(debug())
