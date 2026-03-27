from playwright.async_api import Page
from utils import get_logger, receipt_path, console

logger = get_logger()

async def file_nil_return(page: Page, pin: str) -> str:
    """
    Returns:
        "SUCCESS": Filed successfully.
        "ALREADY_FILED": Return for this period was already filed.
        "FAILED": An error occurred.
    """
    try:
        # STEP 1: Hover over Returns
        console.update("Hovering over Returns menu...")
        returns_menu = page.locator("text=Returns").first
        await returns_menu.hover()
        await page.wait_for_timeout(1000)

        # STEP 2: Click File Nil Return
        console.update("Clicking 'File Nil Return'...")
        nil_return_link = page.locator("text=File Nil Return")
        await nil_return_link.wait_for(state="visible", timeout=5000)
        await nil_return_link.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # STEP 3: Select Tax Obligation
        console.update("Selecting Tax Obligation...")
        await page.wait_for_selector("select", timeout=20000)
        selects = page.locator("select")
        
        found_obligation = False
        for i in range(await selects.count()):
            sel = selects.nth(i)
            opts = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
            if "Income Tax - Resident Individual" in str(opts):
                await sel.select_option(label="Income Tax - Resident Individual")
                found_obligation = True
                break
        
        if not found_obligation:
            console.error("Could not find 'Income Tax - Resident' option.")
            return "FAILED"

        # ── ALREADY FILED DETECTION ─────────────────
        # After selecting the obligation, iTax often shows a table of filed returns.
        # We check if "2025" appears in the "Filed" or "Status" column.
        # Alternatively, sometimes the dropdown for year is missing if already filed.
        await page.wait_for_timeout(1000)
        
        # Logic: Try to find "2025" text in a table row that contains "Filed"
        # Or simply check if the year dropdown has "2025" available.
        year_selects = page.locator("select")
        year_found_in_dropdown = False
        
        for i in range(await year_selects.count()):
            sel = year_selects.nth(i)
            options = await sel.evaluate("el => Array.from(el.options).map(o => o.text)")
            if "2025" in str(options):
                year_found_in_dropdown = True
                # Even if found, sometimes it's there but filing is blocked.
                # We proceed to click Next to be sure.
                await sel.select_option(label="2025")
                break

        # If 2025 is NOT in the dropdown, it's highly likely already filed.
        if not year_found_in_dropdown:
            # Double check by looking for a table message
            page_text = await page.locator("body").inner_text()
            if "return already filed" in page_text.lower() or "no return pending" in page_text.lower():
                console.info("Already filed (No pending return).")
                return "ALREADY_FILED"

        # STEP 4: Click Next
        console.update("Clicking 'Next'...")
        next_btn = page.locator("input[value='Next'], button:has-text('Next')").first
        try:
            await next_btn.wait_for(state="visible", timeout=3000)
            await next_btn.click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(2000)
        except:
            # If Next button isn't there, check for error message
            err = await page.locator("text=already filed, text=already exists").first
            if await err.is_visible(timeout=1000):
                console.info("Already filed (Detected on page).")
                return "ALREADY_FILED"

        # STEP 5: Rental Question
        console.update("Answering Rental Property question...")
        try:
            q_row = page.locator("tr:has-text('Do you own rental Property')").first
            if await q_row.is_visible(timeout=2000):
                no_radio = q_row.locator("input[type='radio'][value='N']")
                if await no_radio.count() == 0: no_radio = q_row.locator("text=No").first
                await no_radio.click()
        except: pass

        # STEP 6: Submit
        console.update("Submitting Nil Return...")
        
        # We need to track if a popup says "Already filed"
        popup_message = ""
        async def handle_dialog(dialog):
            nonlocal popup_message
            popup_message = dialog.message.lower()
            await dialog.accept()
        
        page.on("dialog", handle_dialog)
        
        submit_btn = page.locator("input[value='Submit']").first
        await submit_btn.wait_for(state="visible", timeout=2000)
        await submit_btn.click()
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)
        
        # Check if popup said "already filed"
        if "already filed" in popup_message or "already exists" in popup_message:
            console.info("Already filed (Detected in popup).")
            return "ALREADY_FILED"

        # STEP 7: Receipt
        success = await _download_receipt(page, pin)
        return "SUCCESS" if success else "FAILED"

    except Exception as e:
        logger.error(f"Filing error: {e}")
        await page.screenshot(path=f"logs/filing_error_{pin}.png")
        return "FAILED"

async def _download_receipt(page: Page, pin: str) -> bool:
    try:
        console.update("Waiting for Receipt...")
        await page.wait_for_selector("text=Acknowledgement, text=successfully, text=Receipt, text=filed", timeout=30000)
        console.success("Return Filed Successfully!")
        
        save_path = receipt_path(pin)
        for sel in ["a:has-text('Download')", "a:has-text('Receipt')"]:
            try:
                link = page.locator(sel).first
                if await link.is_visible(timeout=1000):
                    async with page.expect_download() as dl:
                        await link.click()
                    download = await dl.value
                    await download.save_as(save_path)
                    return True
            except: continue
        await page.pdf(path=save_path)
        return True
    except Exception as e:
        logger.error(f"Receipt error: {e}")
        return False
