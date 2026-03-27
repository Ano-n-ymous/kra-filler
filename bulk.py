import asyncio
import csv
import os
from playwright.async_api import async_playwright
from auth import login
from filer import file_nil_return
from utils import get_logger, console, CaptchaError

logger = get_logger()

async def run_bulk():
    console.info("Starting BULK Filing Mode...")
    
    # 1. Check if file exists
    if not os.path.exists("clients.csv"):
        console.error("File 'clients.csv' not found!")
        console.info("Please create a clients.csv file with headers: PIN,Password")
        return

    # 2. Read Clients
    clients = []
    try:
        with open("clients.csv", mode="r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean whitespace
                pin = row.get("PIN", "").strip()
                pwd = row.get("Password", "").strip()
                if pin and pwd:
                    clients.append({"pin": pin, "pwd": pwd})
    except Exception as e:
        console.error(f"Failed to read CSV: {e}")
        return

    if not clients:
        console.error("No valid clients found in CSV.")
        return

    console.info(f"Found {len(clients)} clients to process.")
    
    # 3. Processing Loop
    results = []
    
    # Launch browser ONCE for all clients
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(headless=False, slow_mo=300)
    
    for i, client in enumerate(clients):
        pin = client['pin']
        pwd = client['pwd']
        
        console.info(f"--- Processing {i+1}/{len(clients)}: {pin} ---")
        
        status = "FAILED"
        retries = 1 # Allow 1 retry for Math errors
        
        for attempt in range(retries + 1):
            context = await browser.new_context(viewport={"width": 1280, "height": 800}, accept_downloads=True)
            page = await context.new_page()
            
            try:
                # Login
                await login(page, pin, pwd)
                
                # File
                result = await file_nil_return(page, pin)
                status = result
                break # Success or handled failure, exit retry loop
                
            except CaptchaError:
                console.error("Math error! Retrying...")
                status = "RETRY_MATH"
                # Close page and loop will restart
            except ValueError as e:
                console.error(str(e))
                status = "FAILED_CREDENTIALS"
                break # No point retrying if credentials are wrong
            except Exception as e:
                logger.error(f"Unexpected: {e}")
                status = "ERROR"
                break
            finally:
                await context.close()
        
        results.append({"pin": pin, "status": status})
        
        # Delay between clients to avoid bans
        if i < len(clients) - 1:
            console.update("Waiting 5s before next client...")
            await asyncio.sleep(5)

    await browser.close()
    await playwright.stop()

    # 4. Final Report
    print("\n" + "="*50)
    print("📊 FINAL REPORT")
    print("="*50)
    for r in results:
        icon = "✅" if r['status'] == "SUCCESS" else ("⏭️" if r['status'] == "ALREADY_FILED" else "❌")
        print(f"{icon} {r['pin']}: {r['status']}")
    print("="*50)
