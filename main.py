import asyncio
import getpass
from playwright.async_api import async_playwright
from auth import login
from filer import file_nil_return
from utils import get_logger

logger = get_logger()


async def run():
    logger.info("=" * 50)
    logger.info("  KRA Nil Returns Filer — Interactive Mode")
    logger.info("=" * 50)

    browser = None
    page = None

    while True:
        # ── STEP 1: Ask for Credentials ───────────────
        print("\n" + "─" * 50)
        pin = input("🔑 Enter KRA PIN: ").strip()
        
        # Use getpass to hide password input for security
        password = getpass.getpass("🔒 Enter KRA Password: ").strip()
        print("─" * 50)

        if not pin or not password:
            print("⚠️  PIN and Password cannot be empty.")
            continue

        # ── STEP 2: Launch Browser & Login ─────────────
        try:
            # Launch browser if not already running
            if browser is None:
                playwright = await async_playwright().start()
                browser = await playwright.chromium.launch(
                    headless=False,
                    slow_mo=300
                )
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    accept_downloads=True
                )
                page = await context.new_page()

            # Attempt Login
            try:
                logged_in = await login(page, pin, password)
            except ValueError as e:
                # This catches the "Credentials doesn't match" error we raise in auth.py
                print(f"\n⛔ {e}")
                print("   Please double-check your PIN and Password.\n")
                # Loop continues to ask for input again
                continue

            # ── STEP 3: If Login Fails (Technical Error) ───
            if not logged_in:
                logger.error("🛑 Login failed due to a technical error.")
                print("   Check logs/ for screenshots.")
                # Keep browser open briefly to see error
                await asyncio.sleep(5)
                # We break the loop on technical errors
                break

            # ── STEP 4: File Nil Return ──────────────────
            logger.info("🎉 Logged in! Proceeding to file nil return...")
            success = await file_nil_return(page, pin)

            if success:
                logger.info(f"🎉 Nil return filed successfully for {pin}!")
                logger.info(f"📁 Check receipts/ folder for your PDF.")
            else:
                logger.error(f"❌ Filing failed. Check logs/ for screenshots.")

            # Done
            break

        except Exception as e:
            logger.error(f"💥 Unexpected error: {e}")
            break

    # ── Cleanup ─────────────────────────────────────
    if browser:
        logger.info("⏸️  Keeping browser open 5s...")
        await asyncio.sleep(5)
        await browser.close()
    
    # Stop playwright instance if we started it
    if 'playwright' in locals():
         await playwright.stop()

    logger.info("=" * 50)
    logger.info("  Run complete.")
    logger.info("=" * 50)


if __name__ == "__main__":
    asyncio.run(run())
