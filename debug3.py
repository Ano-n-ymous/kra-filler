"""
Debug login - takes screenshot after clicking Login
to see exactly what KRA shows after submission.
"""
import asyncio, os, re, httpx, subprocess
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()
PIN = os.getenv("KRA_PIN", "").strip()
PASSWORD = os.getenv("KRA_PASSWORD", "").strip()

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=500)
        page = await browser.new_page()

        await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="domcontentloaded")
        await page.wait_for_selector("#logid", timeout=15000)
        await page.fill("#logid", PIN)
        await page.click("a:has-text('Continue')")
        await page.wait_for_timeout(2000)

        # Fill password
        pwd = page.locator("input[type='password']").first
        await pwd.fill(PASSWORD)

        # Download & show captcha
        cookies = await page.context.cookies()
        cookie_header = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
        img_url = await page.evaluate("""() => {
            const input = document.getElementById('captcahText');
            let parent = input?.parentElement;
            for (let i = 0; i < 5; i++) {
                if (!parent) break;
                const img = parent.querySelector('img');
                if (img) return img.src;
                parent = parent.parentElement;
            }
            return null;
        }""")

        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(img_url, headers={"Cookie": cookie_header}, timeout=15)
            with open("logs/captcha_raw.png", "wb") as f:
                f.write(resp.content)

        subprocess.Popen(["xdg-open", "logs/captcha_raw.png"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        answer = input("\n Enter captcha answer: ").strip()
        await page.fill("#captcahText", answer)

        # Screenshot BEFORE clicking login
        await page.screenshot(path="logs/before_login.png")
        print("📸 Screenshot saved: logs/before_login.png")

        # Click login
        await page.click("a#loginButton")
        await page.wait_for_timeout(3000)

        # Screenshot AFTER clicking login
        await page.screenshot(path="logs/after_login.png")
        print("📸 Screenshot saved: logs/after_login.png")

        # Dump page title and URL
        print(f"\n📄 Page title: {await page.title()}")
        print(f"🌐 Current URL: {page.url}")

        # Dump any error messages on page
        error_text = await page.evaluate("""() => {
            const selectors = [
                '.error', '.errorMessage', '#errorMessage',
                '[class*="error"]', '[class*="alert"]',
                'span[style*="red"]', 'font[color="red"]'
            ];
            const found = [];
            for (const sel of selectors) {
                const els = document.querySelectorAll(sel);
                for (const el of els) {
                    const t = el.innerText?.trim();
                    if (t) found.push(`[${sel}]: ${t}`);
                }
            }
            return found.join('\\n') || 'No error elements found';
        }""")
        print(f"\n⚠️  Error messages on page:\n{error_text}")

        # Check what menus/text exist
        visible_text = await page.evaluate("""() => {
            return document.body.innerText.slice(0, 500);
        }""")
        print(f"\n📝 Page text (first 500 chars):\n{visible_text}")

        print("\n⏸️  Browser staying open 30s — check the screenshots in logs/")
        await asyncio.sleep(30)
        await browser.close()

asyncio.run(debug())
