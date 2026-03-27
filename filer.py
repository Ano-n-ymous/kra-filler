from playwright.async_api import Page
from utils import get_logger, receipt_path

logger = get_logger()


async def file_nil_return(page: Page, pin: str) -> bool:
    """
    Files a nil return for the given PIN.
    Flow: Returns -> File Nil Return -> Select Tax -> Next -> Answer Questions -> Submit
    """
    try:
        # ── STEP 1: Hover over 'Returns' menu ──────────
        logger.info("📂 Hovering over Returns menu...")
        returns_menu = page.locator("text=Returns").first
        await returns_menu.hover()
        await page.wait_for_timeout(1000)

        # ── STEP 2: Click 'File Nil Return' ───────
        logger.info("📝 Clicking File Nil Return...")
        nil_return_link = page.locator("text=File Nil Return")
        await nil_return_link.wait_for(state="visible", timeout=5000)
        await nil_return_link.click()
        
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="logs/nil_return_page.png")

        # ── STEP 3: Select Tax Obligation ─────────
        logger.info("📋 Selecting Income Tax - Resident Individual...")
        await page.wait_for_selector("select", timeout=20000)

        selects = page.locator("select")
        count = await selects.count()

        # Select the Tax Obligation
        for i in range(count):
            sel = selects.nth(i)
            try:
                opts = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
                if "Income Tax - Resident Individual" in str(opts):
                    await sel.select_option(label="Income Tax - Resident Individual")
                    logger.info("✅ Selected: Income Tax - Resident Individual")
                    break
            except Exception:
                continue

        await page.wait_for_timeout(1000)

        # ── STEP 4: Select Year (if applicable) ─────
        try:
            year_selects = page.locator("select")
            for i in range(await year_selects.count()):
                sel = year_selects.nth(i)
                options = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
                if "2025" in str(options):
                    await sel.select_option(label="2025")
                    logger.info("✅ Selected year: 2025")
                    break
        except Exception:
            pass

        # ── STEP 5: Click NEXT ─────────────────────
        logger.info("➡️  Clicking 'Next' button...")
        try:
            next_btn = page.locator("input[value='Next'], button:has-text('Next')").first
            await next_btn.wait_for(state="visible", timeout=5000)
            await next_btn.click()
            logger.info("✅ Clicked Next. Waiting for questions page...")
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2000)
            await page.screenshot(path="logs/after_next.png")
        except Exception as e:
            logger.warning(f"⚠️ Could not find 'Next' button: {e}")

        # ── STEP 6: Answer 'Rental Property' Question ───────
        logger.info("🏠 Checking for rental property question...")
        try:
            question_row = page.locator("tr:has-text('Do you own rental Property')").first
            
            if await question_row.is_visible(timeout=3000):
                logger.info("❓ Found rental property question. Selecting 'No'...")
                
                no_radio = question_row.locator("input[type='radio'][value='N']")
                
                if await no_radio.count() == 0:
                    no_radio = question_row.locator("text=No").first
                
                await no_radio.click()
                logger.info("✅ Selected 'No' for rental property.")
                await page.wait_for_timeout(500)
            else:
                logger.info("ℹ️ Rental property question not found.")

        except Exception as e:
            logger.warning(f"⚠️ Could not interact with rental question: {e}")

        # ── STEP 7: Submit ─────────────────────────
        logger.info("🚀 Submitting nil return...")
        
        # CRITICAL: Handle the JavaScript Confirmation Popup
        # We define a function to accept the dialog and register it.
        async def handle_dialog(dialog):
            logger.info(f"💬 Browser Popup detected: '{dialog.message}'")
            await dialog.accept()
            logger.info("✅ Clicked OK on popup.")

        # Register the handler
        page.on("dialog", handle_dialog)

        submit_selectors = [
            "input[value='Submit']",
            "button:has-text('Submit')",
            "input[type='submit']",
        ]
        
        submitted = False
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    logger.info(f"⏳ Found submit button: {sel}. Clicking...")
                    await btn.click()
                    submitted = True
                    break
            except Exception:
                continue
        
        if not submitted:
            logger.error("❌ Could not find a clickable Submit button!")
            await page.screenshot(path="logs/no_submit_button.png")
            return False

        # Wait for navigation to finish after the dialog is accepted
        logger.info("⏳ Waiting for acknowledgement page...")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        await page.screenshot(path="logs/after_submit.png")

        # ── STEP 8: Download receipt ───────────────
        success = await _download_receipt(page, pin)
        return success

    except Exception as e:
        logger.error(f"💥 Filing error for {pin}: {e}")
        await page.screenshot(path=f"logs/filing_error_{pin}.png")
        return False


async def _download_receipt(page: Page, pin: str) -> bool:
    """Downloads the acknowledgement receipt as PDF."""
    try:
        # Wait for success/acknowledgement page
        await page.wait_for_selector(
            "text=Acknowledgement, text=successfully, text=Receipt, text=filed",
            timeout=30000
        )

        save_path = receipt_path(pin)

        # Try clicking a download link first
        for sel in [
            "a:has-text('Download')",
            "a:has-text('Receipt')",
            "a:has-text('Acknowledgement')",
            "input[value='Download']",
        ]:
            try:
                link = page.locator(sel).first
                if await link.is_visible(timeout=2000):
                    async with page.expect_download() as dl:
                        await link.click()
                    download = await dl.value
                    await download.save_as(save_path)
                    logger.info(f"📄 Receipt saved → {save_path}")
                    return True
            except Exception:
                continue

        # Fallback: save page as PDF
        await page.pdf(path=save_path)
        logger.info(f"📄 Page saved as PDF → {save_path}")
        return True

    except Exception as e:
        logger.error(f"❌ Could not get receipt: {e}")
        body_text = await page.locator("body").inner_text()
        logger.error(f"⚠️ Page content snippet:\n{body_text[:500]}")
        await page.screenshot(path=f"logs/receipt_fail_{pin}.png")
        return False
