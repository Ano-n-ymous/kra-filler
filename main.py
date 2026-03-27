import asyncio
import getpass
from playwright.async_api import async_playwright
# Import the new bulk runner
from bulk import run_bulk
from auth import login
from filer import file_nil_return
from utils import get_logger, console, CaptchaError

logger = get_logger()

async def run_single():
    console.info("Starting SINGLE Filing Mode...")
    
    print("\n" + "─" * 50)
    pin = input("🔑 Enter KRA PIN: ").strip()
    password = getpass.getpass("🔒 Enter KRA Password: ").strip()
    print("─" * 50 + "\n")

    if not pin or not password:
        console.error("PIN and Password cannot be empty.")
        return

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

            logged_in = await login(page, pin, password)
            if not logged_in:
                console.error("Login failed.")
                break

            result = await file_nil_return(page, pin)
            
            if result == "SUCCESS":
                console.success("ALL DONE! Process completed successfully.")
            elif result == "ALREADY_FILED":
                console.info("Return was already filed for this period.")
            else:
                console.error("Filing failed. Check logs.")
            
            break

        except CaptchaError:
            console.error("Math/Captcha was wrong! Restarting process...")
            if browser: await browser.close()
            if 'playwright' in locals(): await playwright.stop()
            console.info(f"Retrying... (Attempt {attempt} of {max_retries})")

        except ValueError as e:
            console.error(str(e))
            break

        except Exception as e:
            logger.error(f"Unexpected: {e}")
            console.error("An unexpected error occurred.")
            break
        
        finally:
            if browser:
                try: await browser.close()
                except: pass
            if 'playwright' in locals():
                try: await playwright.stop()
                except: pass

    if attempt >= max_retries:
        console.error("Max retries reached.")

async def main_menu():
    print("\n" + "="*40)
    print("   KRA NIL RETURNS BOT v2.0")
    print("="*40)
    print(" 1. File Single Return")
    print(" 2. File Bulk Returns (CSV)")
    print(" 3. Exit")
    print("="*40)
    
    choice = input("Select Option (1-3): ").strip()
    
    if choice == "1":
        await run_single()
    elif choice == "2":
        await run_bulk()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    asyncio.run(main_menu())
