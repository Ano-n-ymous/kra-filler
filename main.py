import asyncio
import getpass
from playwright.async_api import async_playwright
from auth import login
from filer import file_nil_return
from utils import get_logger, console, CaptchaError

logger = get_logger()

async def run():
    console.info("Starting KRA Nil Returns Filer...")
    
    # ── STEP 1: Get Credentials ───────────────────────
    print("\n" + "─" * 50)
    pin = input("🔑 Enter KRA PIN: ").strip()
    # getpass hides the password input completely
    password = getpass.getpass("🔒 Enter KRA Password: ").strip()
    print("─" * 50 + "\n")

    if not pin or not password:
        console.error("PIN and Password cannot be empty.")
        return

    # ── STEP 2: The Retry Loop ───────────────────────
    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        browser = None
        page = None
        
        try:
            console.update("Launching browser...")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(headless=False, slow_mo=300)
            context = await browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
            page = await context.new_page()

            # ── Attempt Login ──
            logged_in = await login(page, pin, password)

            if not logged_in:
                # This block shouldn't run often because login() raises errors on failure
                console.error("Login failed.")
                break

            # ── Attempt Filing ──
            success = await file_nil_return(page, pin)
            
            if success:
                console.success("ALL DONE! Process completed successfully.")
            else:
                console.error("Filing failed. Check logs.")
            
            # Break loop on success or non-retryable failure
            break

        except CaptchaError as e:
            # ── Math Was Wrong: Restart Process ──
            console.error("Math/Captcha was wrong! Restarting process...")
            console.update("Closing browser to retry...")
            if browser: await browser.close()
            if 'playwright' in locals(): await playwright.stop()
            
            console.info(f"Retrying... (Attempt {attempt} of {max_retries})")
            # Loop continues here
            
        except ValueError as e:
            # ── Wrong Credentials or Bad Error: Stop ──
            console.error(str(e))
            break

        except Exception as e:
            logger.error(f"Unexpected: {e}")
            console.error("An unexpected error occurred.")
            break
        
        finally:
            # Cleanup if loop finishes or breaks
            if browser:
                try:
                    console.update("Closing browser...")
                    await browser.close()
                except: pass
            if 'playwright' in locals():
                try:
                    await playwright.stop()
                except: pass

    if attempt >= max_retries:
        console.error("Max retries reached. Please try again later.")

if __name__ == "__main__":
    asyncio.run(run())
