import os
import re
import subprocess
import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from io import BytesIO
from dotenv import load_dotenv
from playwright.async_api import Page
from utils import get_logger, wait_for_otp, console, CaptchaError

load_dotenv()
logger = get_logger()

ITAX_URL = "https://itax.kra.go.ke/KRA-Portal/"

async def login(page: Page, pin: str, password: str) -> bool:
    try:
        console.update(f"Opening iTax Portal...")
        await page.goto(ITAX_URL, wait_until="domcontentloaded", timeout=60000)

        # ── STEP 1: Fill PIN ───────────────────────
        console.update(f"Entering PIN: {pin}")
        await page.wait_for_selector("#logid", timeout=30000)
        await page.click("#logid", click_count=3)
        await page.fill("#logid", pin)

        # ── STEP 2: Click Continue ─────────────────
        console.update("Clicking Continue...")
        await page.click("a:has-text('Continue')")
        await page.wait_for_timeout(2000)

        # ── STEP 3: Type Password ──────────────────
        console.update("Typing password...")
        pwd_field = page.locator("input[type='password']").first
        await pwd_field.wait_for(state="visible", timeout=15000)
        await pwd_field.click()
        await pwd_field.type(password, delay=50)
        await page.wait_for_timeout(500)

        # ── STEP 4: Solve Captcha ──────────────────
        console.update("Solving Security Stamp...")
        answer = await _solve_captcha(page)

        if answer is not None:
            console.update(f"Typing answer: {answer}")
            captcha_input = page.locator("#captcahText").first
            await captcha_input.wait_for(state="visible", timeout=5000)
            await captcha_input.click(click_count=3)
            await captcha_input.fill(str(answer))
        else:
            # Fallback to manual
            console.info("Captcha image opened. Please solve manually.")
            answer = _ask_captcha_answer()
            if answer is not None:
                captcha_input = page.locator("#captcahText").first
                await captcha_input.click(click_count=3)
                await captcha_input.fill(str(answer))

        # ── STEP 5: Click Login ────────────────────
        console.update("Clicking Login...")
        await page.click("a#loginButton")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # ── STEP 6: OTP if triggered ───────────────
        if await _is_otp_required(page):
            console.info("OTP Required.")
            otp = wait_for_otp()
            console.update("Submitting OTP...")
            await page.locator("input[name='otp'], input[id='otp']").first.fill(otp)
            await page.click("a#loginButton")
            await page.wait_for_load_state("domcontentloaded")

        # ── STEP 7: Verify login ───────────────────
        console.update("Verifying login status...")
        if await _is_logged_in(page):
            console.success(f"Login successful for {pin}")
            return True
        else:
            error = await page.evaluate("""() => {
                const sels = ['.errorMessage','#errorMessage','font[color="red"]','span[style*="red"]'];
                for (const s of sels) {
                    const el = document.querySelector(s);
                    if (el?.innerText?.trim()) return el.innerText.trim();
                }
                return '';
            }""")
            
            await page.screenshot(path=f"logs/login_fail_{pin}.png")
            
            if error:
                logger.error(f"KRA Error: {error}")
                # Check if it's a captcha error
                if "security stamp" in error.lower() or "invalid captcha" in error.lower():
                    raise CaptchaError("Math solution was wrong.")
                
                # Check if it's credentials error
                if "invalid" in error.lower() or "incorrect" in error.lower() or "wrong" in error.lower():
                    raise ValueError("Credentials doesn't match!")
                
                # Other error
                raise ValueError(f"Login failed: {error}")
            
            raise ValueError("Login failed for unknown reason.")

    except CaptchaError:
        raise # Re-raise to main
    except ValueError:
        raise # Re-raise to main
    except Exception as e:
        logger.error(f"Exception: {e}")
        await page.screenshot(path=f"logs/login_exception_{pin}.png")
        raise ValueError("Connection or technical error.")

# ─────────────────────────────────────────────
#  Captcha Solver Logic (Same as before)
# ─────────────────────────────────────────────

async def _solve_captcha(page: Page) -> int | None:
    os.makedirs("logs", exist_ok=True)
    img_attrs = await page.evaluate("""() => {
        const input = document.getElementById('captcahText');
        if (!input) return null;
        let el = input;
        for (let i = 0; i < 10; i++) {
            el = el.parentElement;
            if (!el) break;
            const imgs = el.querySelectorAll('img');
            for (const img of imgs) {
                if (img.naturalWidth > 20 || img.width > 20 || img.naturalWidth === 0) {
                    return { src: img.src, width: img.width, height: img.height };
                }
            }
        }
        return null;
    }""")

    try:
        if img_attrs and img_attrs.get("src"):
            src = img_attrs["src"]
            src_base = src.split("?")[0].split("/")[-1]
            img_locator = page.locator(f"img[src*='{src_base}']").first
        else:
            img_locator = page.locator("tr:has(#captcahText) img").first

        await img_locator.wait_for(state="visible", timeout=8000)
        screenshot_bytes = await img_locator.screenshot()
        with open("logs/captcha_img.png", "wb") as f:
            f.write(screenshot_bytes)
    except Exception as e:
        logger.warning(f"Screenshot failed: {e}")
        return None

    return _ocr_and_solve(screenshot_bytes)

def _ocr_and_solve(image_bytes: bytes) -> int | None:
    img = Image.open(BytesIO(image_bytes))
    if img.height < 200:
        scale = 200 // max(img.height, 1)
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)

    proc = img.convert("L")
    proc = ImageEnhance.Contrast(proc).enhance(2.5)
    proc = proc.point(lambda p: 255 if p > 128 else 0)
    proc = proc.filter(ImageFilter.MaxFilter(3))
    proc = proc.filter(ImageFilter.MedianFilter(size=3))
    
    cfg = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789+-xX*? "
    raw = pytesseract.image_to_string(proc, config=cfg).strip()
    clean = re.sub(r"\s+", "", raw)
    logger.info(f"OCR: '{raw}' -> '{clean}'")

    if '?' in clean:
        if len(clean) >= 2 and clean[-2] in ['7', '2'] and clean[-1] == '?':
            clean = clean[:-2] + '?'
        clean = clean.replace("?", "")
    else:
        if clean and clean[-1].isdigit():
            clean = clean[:-1]

    match = re.search(r"(\d{1,3})([+\-xX*])(\d{1,3})", clean)
    if match:
        a, op, b = int(match.group(1)), match.group(2), int(match.group(3))
        res = (a + b) if op in ['+', 'x', 'X', '*'] else (a - b)
        if 0 <= res <= 999: return res
    return None

def _ask_captcha_answer() -> int | None:
    _open_image("logs/captcha_img.png")
    for _ in range(3):
        raw = input("   Enter answer: ").strip()
        digits = re.sub(r"[^\d]", "", raw)
        if digits: return int(digits)
    return None

def _open_image(path: str) -> None:
    if not os.path.exists(path): return
    try:
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

async def _is_otp_required(page: Page) -> bool:
    try: return await page.locator("input[name='otp'], input[id='otp']").first.is_visible(timeout=3000)
    except: return False

async def _is_logged_in(page: Page) -> bool:
    for s in ["text=Logout", "text=Returns", "#mainMenu"]:
        try: 
            await page.wait_for_selector(s, timeout=5000)
            return True
        except: continue
    return False
