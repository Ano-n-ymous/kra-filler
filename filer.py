from playwright.async_api import Page
from utils import get_logger, receipt_path, console

logger = get_logger()

async def file_nil_return(page: Page, pin: str) -> bool:
    try:
        # STEP 1
        console.update("Hovering over Returns menu...")
        returns_menu = page.locator("text=Returns").first
        await returns_menu.hover()
        await page.wait_for_timeout(1000)

        # STEP 2
        console.update("Clicking 'File Nil Return'...")
        nil_return_link = page.locator("text=File Nil Return")
        await nil_return_link.wait_for(state="visible", timeout=5000)
        await nil_return_link.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # STEP 3
        console.update("Selecting Tax Obligation...")
        await page.wait_for_selector("select", timeout=20000)
        selects = page.locator("select")
        for i in range(await selects.count()):
            sel = selects.nth(i)
            opts = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
            if "Income Tax - Resident Individual" in str(opts):
                await sel.select_option(label="Income Tax - Resident Individual")
                break
        
        # STEP 4: Year
        try:
            for i in range(await selects.count()):
                sel = selects.nth(i)
                opts = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
                if "2025" in str(opts):
                    await sel.select_option(label="2025")
                    break
        except: pass

        # STEP 5: Next
        console.update("Clicking 'Next'...")
        next_btn = page.locator("input[value='Next'], button:has-text('Next')").first
        await next_btn.wait_for(state="visible", timeout=5000)
        await next_btn.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # STEP 6: Rental Question
        console.update("Answering Rental Property question...")
        try:
            q_row = page.locator("tr:has-text('Do you own rental Property')").first
            if await q_row.is_visible(timeout=3000):
                no_radio = q_row.locator("input[type='radio'][value='N']")
                if await no_radio.count() == 0: no_radio = q_row.locator("text=No").first
                await no_radio.click()
        except: pass

        # STEP 7: Submit
        console.update("Submitting Nil Return...")
        async def handle_dialog(dialog):
            console.update("Accepting popup confirmation...")
            await dialog.accept()
        page.on("dialog", handle_dialog)

        submit_btn = page.locator("input[value='Submit']").first
        await submit_btn.wait_for(state="visible", timeout=2000)
        await submit_btn.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # STEP 8: Receipt
        success = await _download_receipt(page, pin)
        return success

    except Exception as e:
        logger.error(f"Filing error: {e}")
        await page.screenshot(path=f"logs/filing_error_{pin}.png")
        return False

async def _download_receipt(page: Page, pin: str) -> bool:
    try:
        console.update("Waiting for Receipt...")
        await page.wait_for_selector("text=Acknowledgement, text=successfully, text=Receipt, text=filed", timeout=30000)
        console.success("Return Filed Successfully!")
        
        save_path = receipt_path(pin)
        
        # Try Download
        for sel in ["a:has-text('Download')", "a:has-text('Receipt')"]:
            try:
                link = page.locator(sel).first
                if await link.is_visible(timeout=1000):
                    async with page.expect_download() as dl:
                        await link.click()
                    download = await dl.value
                    await download.save_as(save_path)
                    console.success(f"Receipt saved to: {save_path}")
                    return True
            except: continue

        # Fallback PDF
        await page.pdf(path=save_path)
        console.info(f"Page saved as PDF: {save_path}")
        return True
    except Exception as e:
        logger.error(f"Receipt error: {e}")
        console.error("Failed to download receipt.")
        return False
