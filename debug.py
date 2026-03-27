"""
Run this to inspect iTax page HTML after PIN entry.
It will pause so you can see what's on the page.
"""
import asyncio
import os
from dotenv import load_dotenv
from playwright.async_api import async_playwright

load_dotenv()

PIN = os.getenv("KRA_PIN", "").strip()

async def debug():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=800)
        page = await browser.new_page()

        print("\n🌐 Opening iTax...")
        await page.goto("https://itax.kra.go.ke/KRA-Portal/", wait_until="domcontentloaded", timeout=60000)

        # Fill PIN
        await page.wait_for_selector("#logid", timeout=15000)
        await page.fill("#logid", PIN)
        print(f"✅ PIN filled: {PIN}")

        # Dump ALL buttons/inputs on page 1 before clicking
        print("\n📋 PAGE 1 — Buttons & inputs found:")
        elements = await page.query_selector_all("input, button, a")
        for el in elements:
            tag = await el.evaluate("el => el.tagName")
            id_ = await el.get_attribute("id") or ""
            name = await el.get_attribute("name") or ""
            type_ = await el.get_attribute("type") or ""
            value = await el.get_attribute("value") or ""
            text = (await el.inner_text()).strip()[:40] if tag == "A" else ""
            print(f"  <{tag.lower()}> id='{id_}' name='{name}' type='{type_}' value='{value}' text='{text}'")

        # Try clicking Continue
        print("\n🖱️  Attempting to click Continue...")
        clicked = False
        selectors = [
            "input#nextBtn", "input[name='nextBtn']", "a#nextBtn",
            "input[value='Continue']", "input[value='Login']",
            "a:has-text('Continue')", "button:has-text('Continue')",
        ]
        for sel in selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=1500):
                    print(f"  ✅ Clicking: {sel}")
                    await el.click()
                    clicked = True
                    break
            except:
                continue

        if not clicked:
            print("  ⚠️  No button found — pressing Enter")
            await page.keyboard.press("Enter")

        await page.wait_for_load_state("domcontentloaded")
        await asyncio.sleep(3)  # let page settle

        # Dump PAGE 2
        print("\n📋 PAGE 2 — All inputs & buttons after Continue:")
        elements = await page.query_selector_all("input, button, a, label")
        for el in elements:
            tag = await el.evaluate("el => el.tagName")
            id_ = await el.get_attribute("id") or ""
            name = await el.get_attribute("name") or ""
            type_ = await el.get_attribute("type") or ""
            value = await el.get_attribute("value") or ""
            text = (await el.inner_text()).strip()[:60]
            print(f"  <{tag.lower()}> id='{id_}' name='{name}' type='{type_}' value='{value}' text='{text}'")

        print("\n⏸️  Browser staying open for 30 seconds — look at the page!")
        print("   Check the terminal output above for correct selectors.")
        await asyncio.sleep(30)
        await browser.close()

asyncio.run(debug())
