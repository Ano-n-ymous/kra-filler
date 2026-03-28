import asyncio
import argparse
from dotenv import load_dotenv
import os
from playwright.async_api import async_playwright
from bulk import run_bulk
from auth import login
from filer import file_nil_return
from utils import get_logger, console, CaptchaError

load_dotenv()
logger = get_logger()

# ─────────────────────────────────────────────
#  Headless config
#  Default comes from .env: HEADLESS=true/false
#  Override via CLI: --no-headless (shows browser)
# ─────────────────────────────────────────────
parser = argparse.ArgumentParser(description="KRA Nil Returns Filer")
parser.add_argument(
    "--no-headless",
    action="store_true",
    help="Show the browser window (overrides .env HEADLESS=true)"
)
args = parser.parse_args()

# .env HEADLESS=true means headless by default
_env_headless = os.getenv("HEADLESS", "true").strip().lower() == "true"
# --no-headless flag flips it off
HEADLESS = _env_headless and not args.no_headless


# ─────────────────────────────────────────────
#  Single Filing
# ─────────────────────────────────────────────

async def run_single():
    console.info("Starting SINGLE Filing Mode...")
    mode = "HEADLESS (silent)" if HEADLESS else "HEADED (browser visible)"
    console.info(f"Browser mode: {mode}")

    print("\n" + "─" * 50)
    pin = input("🔑 Enter KRA PIN: ").strip()
    password = input("🔒 Enter KRA Password: ").strip()
    print("─" * 50 + "\n")

    if not pin or not password:
        console.error("PIN and Password cannot be empty.")
        return

    max_retries = 3
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        browser = None

        try:
            console.update("Launching browser...")
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=HEADLESS,
                slow_mo=0 if HEADLESS else 300   # no slow_mo in headless
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                accept_downloads=True
            )
            page = await context.new_page()

            logged_in = await login(page, pin, password)
            if not logged_in:
                console.error("Login failed.")
                break

            result = await file_nil_return(page, pin)

            if result == "SUCCESS":
                console.success("ALL DONE! Filed successfully.")
            elif result == "ALREADY_FILED":
                console.info("Return already filed for this period.")
            else:
                console.error("Filing failed. Check logs/")

            break

        except CaptchaError:
            console.error(f"Captcha wrong — retrying... ({attempt}/{max_retries})")
            if browser:
                try: await browser.close()
                except: pass
            if 'playwright' in locals():
                try: await playwright.stop()
                except: pass

        except ValueError as e:
            console.error(str(e))
            break

        except Exception as e:
            logger.error(f"Unexpected: {e}")
            console.error("Unexpected error occurred.")
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


# ─────────────────────────────────────────────
#  Bulk Filing
# ─────────────────────────────────────────────

async def run_bulk_mode():
    await run_bulk(headless=HEADLESS)


# ─────────────────────────────────────────────
#  Menu
# ─────────────────────────────────────────────

async def main_menu():
    mode = "HEADLESS" if HEADLESS else "HEADED"
    print("\n" + "=" * 40)
    print(f"   KRA NIL RETURNS BOT v2.0  [{mode}]")
    print("=" * 40)
    print(" 1. File Single Return")
    print(" 2. File Bulk Returns (CSV)")
    print(" 3. Exit")
    print("=" * 40)

    choice = input("Select Option (1-3): ").strip()

    if choice == "1":
        await run_single()
    elif choice == "2":
        await run_bulk_mode()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    asyncio.run(main_menu())
