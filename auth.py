import os
import re
import subprocess
import pytesseract
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
from io import BytesIO
from dotenv import load_dotenv
from playwright.async_api import Page
from utils import get_logger, wait_for_otp

load_dotenv()
logger = get_logger()

ITAX_URL = "https://itax.kra.go.ke/KRA-Portal/"


# ─────────────────────────────────────────────
#  Load Credentials
# ─────────────────────────────────────────────

def load_credentials() -> tuple[str, str]:
    pin = os.getenv("KRA_PIN", "").strip()
    password = os.getenv("KRA_PASSWORD", "").strip()
    if not pin or not password:
        raise ValueError("❌ KRA_PIN or KRA_PASSWORD missing in .env file.")
    return pin, password


# ─────────────────────────────────────────────
#  Login Flow
# ─────────────────────────────────────────────

async def login(page: Page, pin: str, password: str) -> bool:
    try:
        logger.info(f"🌐 Opening iTax portal for PIN: {pin}")
        await page.goto(ITAX_URL, wait_until="domcontentloaded", timeout=60000)

        # ── STEP 1: Fill PIN ───────────────────────
        logger.info("🔑 Entering PIN...")
        await page.wait_for_selector("#logid", timeout=30000)
        await page.click("#logid", click_count=3)
        await page.fill("#logid", pin)

        # ── STEP 2: Click Continue ─────────────────
        logger.info("🖱️  Clicking Continue...")
        await page.click("a:has-text('Continue')")
        await page.wait_for_timeout(2000)

        # ── STEP 3: Type Password ──────────────────
        logger.info("🔒 Typing password...")
        pwd_field = page.locator("input[type='password']").first
        await pwd_field.wait_for(state="visible", timeout=15000)
        await pwd_field.click()
        await pwd_field.type(password, delay=50)
        await page.wait_for_timeout(500)

        # ── STEP 4: Solve Captcha ──────────────────
        logger.info("🔢 Solving security stamp...")
        answer = await _solve_captcha(page)

        if answer is not None:
            logger.info(f"🔢 Captcha answer: {answer}")
            captcha_input = page.locator("#captcahText").first
            await captcha_input.wait_for(state="visible", timeout=5000)
            await captcha_input.click(click_count=3)
            await captcha_input.fill(str(answer))
        else:
            logger.warning("⚠️  Auto-solve failed — falling back to manual input.")
            answer = _ask_captcha_answer()
            if answer is not None:
                captcha_input = page.locator("#captcahText").first
                await captcha_input.click(click_count=3)
                await captcha_input.fill(str(answer))

        # ── STEP 5: Click Login ────────────────────
        logger.info("🖱️  Clicking Login...")
        await page.click("a#loginButton")
        await page.wait_for_load_state("domcontentloaded")
        await page.wait_for_timeout(2000)

        # ── STEP 6: OTP if triggered ───────────────
        if await _is_otp_required(page):
            logger.info("📱 OTP detected...")
            otp = wait_for_otp()
            await page.locator("input[name='otp'], input[id='otp']").first.fill(otp)
            await page.click("a#loginButton")
            await page.wait_for_load_state("domcontentloaded")

        # ── STEP 7: Verify login ───────────────────
        if await _is_logged_in(page):
            logger.info(f"✅ Login successful for PIN: {pin}")
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
            if error:
                logger.error(f"❌ KRA error: {error}")
            else:
                logger.error(f"❌ Login failed for PIN: {pin}.")
            await page.screenshot(path=f"logs/login_fail_{pin}.png")
            return False

    except Exception as e:
        logger.error(f"💥 Exception during login for {pin}: {e}")
        await page.screenshot(path=f"logs/login_exception_{pin}.png")
        return False


# ─────────────────────────────────────────────
#  Captcha Solver
# ─────────────────────────────────────────────

async def _solve_captcha(page: Page) -> int | None:
    """
    Locates the captcha image, takes a screenshot, and runs OCR.
    """
    os.makedirs("logs", exist_ok=True)

    # ── Find the captcha <img> element via JS ──────────────────────────
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
                    return {
                        src: img.src,
                        width: img.width,
                        height: img.height,
                        naturalWidth: img.naturalWidth,
                        naturalHeight: img.naturalHeight
                    };
                }
            }
        }
        return null;
    }""")

    logger.debug(f"Captcha img attrs: {img_attrs}")

    # ── Screenshot the img element directly ────────────────────────────
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
        logger.debug("📸 Captcha img screenshot saved to logs/captcha_img.png")

    except Exception as e:
        logger.warning(f"img locator failed ({e}), falling back to row screenshot")
        try:
            row = page.locator("tr:has(#captcahText)").first
            await row.wait_for(state="visible", timeout=8000)
            screenshot_bytes = await row.screenshot()
            with open("logs/captcha_img.png", "wb") as f:
                f.write(screenshot_bytes)
        except Exception as e2:
            logger.error(f"Row screenshot also failed: {e2}")
            return None

    return _ocr_and_solve(screenshot_bytes)


def _ocr_and_solve(image_bytes: bytes) -> int | None:
    """
    Upscales, denoises, and runs OCR.
    Fixes: 
    - '?' splitting into '7?' (Logic to strip digit before ?).
    - '?' being read as '7'.
    - 3-digit numbers support.
    """
    img = Image.open(BytesIO(image_bytes))
    logger.debug(f"📐 Raw screenshot size: {img.size}")

    # 1. Upscale
    target_height = 200
    if img.height < target_height:
        scale = target_height // max(img.height, 1)
        img = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)

    # 2. Preprocessing
    proc = img.convert("L")
    proc = ImageEnhance.Contrast(proc).enhance(2.5)
    
    # Binarize
    proc = proc.point(lambda p: 255 if p > 128 else 0)
    
    # Dilate to connect broken shapes
    proc = proc.filter(ImageFilter.MaxFilter(3))
    
    # Denoise
    proc = proc.filter(ImageFilter.MedianFilter(size=3))
    
    proc.save("logs/captcha_processed.png")

    # 3. Tesseract Config
    cfg = r"--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789+-xX*? "

    try:
        raw = pytesseract.image_to_string(proc, config=cfg).strip()
        
        # Clean spaces
        clean = re.sub(r"\s+", "", raw)
        logger.info(f"🔍 OCR Raw result: '{raw}' -> Cleaned: '{clean}'")

        # ── ROBUST CLEANING LOGIC ───────────────────────────────
        
        # CASE A: The '?' is found.
        if '?' in clean:
            # Fix for "128+157?" -> "128+15?"
            # Tesseract splits '?' into '7' (hook) and '?' (dot).
            # If we see a digit immediately before '?', it's likely a misread hook.
            # We only check for 7 and 2 as they are the common shapes.
            
            # Check if string ends with 7? or 2?
            if len(clean) >= 2 and clean[-2] in ['7', '2'] and clean[-1] == '?':
                logger.warning(f"⚠️ Detected split '?' pattern (e.g. 7?). Removing digit before '?'.")
                clean = clean[:-2] + '?' # Remove the digit, keep the ?
            
            # Now safe remove the '?'
            clean = clean.replace("?", "")
            
        # CASE B: No '?' found (Tesseract read '?' purely as a digit).
        else:
            # If no '?' found, the last digit is highly suspicious.
            # It is very likely the '?' was read as '7' or '2'.
            if clean and clean[-1].isdigit():
                logger.warning(f"⚠️ No '?' found. Stripping trailing digit '{clean[-1]}' assuming it is a misread '?'.")
                clean = clean[:-1]

        # ── MATH PARSING ───────────────────────────────────────
        # Allow 3 digits {1,3}
        match = re.search(r"(\d{1,3})([+\-xX*])(\d{1,3})", clean)
        
        if match:
            a = int(match.group(1))
            op = match.group(2)
            b = int(match.group(3))

            # Calculate
            if op in ['+', 'x', 'X', '*']:
                result = a + b
            elif op == '-':
                result = a - b
            else:
                return None

            # Sanity check
            if 0 <= result <= 999:
                logger.info(f"✅ Solved: {a} {op} {b} = {result}")
                return result
        
        logger.warning(f"⚠️ Could not parse math from: '{clean}'")

    except Exception as e:
        logger.error(f"💥 OCR Exception: {e}")

    return None


# ─────────────────────────────────────────────
#  Manual Fallback
# ─────────────────────────────────────────────

def _ask_captcha_answer() -> int | None:
    _open_image("logs/captcha_img.png")
    print("\n" + "─" * 50)
    print("🔐 Auto-solve failed — please solve manually.")
    print("   Image: logs/captcha_img.png")
    print("─" * 50)
    for _ in range(3):
        raw = input("   Enter the answer: ").strip()
        digits = re.sub(r"[^\d]", "", raw)
        if digits:
            return int(digits)
        print("   ⚠️  Numbers only please.")
    return None


def _open_image(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        for viewer in ["xdg-open", "eog", "feh", "display"]:
            try:
                subprocess.Popen([viewer, path],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
            except FileNotFoundError:
                continue
    except Exception:
        pass


# ─────────────────────────────────────────────
#  State Checkers
# ─────────────────────────────────────────────

async def _is_otp_required(page: Page) -> bool:
    try:
        return await page.locator(
            "input[name='otp'], input[id='otp']"
        ).first.is_visible(timeout=3000)
    except Exception:
        return False


async def _is_logged_in(page: Page) -> bool:
    """
    Tries multiple known dashboard indicators one by one.
    The iTax dashboard shows 'Logout', 'Integrated iTax Dashboard',
    and a welcome message — any one of these confirms login success.
    """
    indicators = [
        "text=Logout",
        "text=Integrated iTax Dashboard",
        "text=Welcome",
        "text=Returns",
        "#mainMenu",
        "a:has-text('Logout')",
    ]
    for selector in indicators:
        try:
            await page.wait_for_selector(selector, timeout=5000)
            logger.debug(f"✅ Login confirmed via: {selector}")
            return True
        except Exception:
            continue
    return False
