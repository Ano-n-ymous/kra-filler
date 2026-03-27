import asyncio
from playwright.async_api import async_playwright
from auth import load_credentials, login
from filer import file_nil_return
from utils import get_logger

logger = get_logger()


async def run():
    logger.info("=" * 50)
    logger.info("  KRA Nil Returns Filer — Phase 1")
    logger.info("=" * 50)

    # ── Load credentials ───────────────────────
    try:
        pin, password = load_credentials()
    except ValueError as e:
        logger.error(str(e))
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=300
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            accept_downloads=True
        )
        page = await context.new_page()

        # ── Login ──────────────────────────────
        logged_in = await login(page, pin, password)

        if not logged_in:
            logger.error("🛑 Login failed — check logs/ for screenshots.")
            logger.info("⏸️  Keeping browser open 30s for inspection...")
            await asyncio.sleep(30)
            await browser.close()
            return

        logger.info("🎉 Logged in! Proceeding to file nil return...")

        # ── File Nil Return ────────────────────
        success = await file_nil_return(page, pin)

        if success:
            logger.info(f"🎉 Nil return filed successfully for {pin}!")
            logger.info(f"📁 Check receipts/ folder for your PDF.")
        else:
            logger.error(f"❌ Filing failed. Check logs/ for screenshots.")

        logger.info("⏸️  Keeping browser open 15s...")
        await asyncio.sleep(15)

        logger.info("=" * 50)
        logger.info("  Run complete.")
        logger.info("=" * 50)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(run())
