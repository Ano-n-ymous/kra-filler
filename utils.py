import logging
import os
import sys
import time
from datetime import datetime
from itertools import cycle

# ─────────────────────────────────────────────
#  Custom Exception for Captcha Failures
# ─────────────────────────────────────────────

class CaptchaError(Exception):
    """Raised when the math/captcha solution is wrong."""
    pass


# ─────────────────────────────────────────────
#  Lightweight Terminal Animator
# ─────────────────────────────────────────────

class Animator:
    def __init__(self):
        self.steps = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        self.current_step = cycle(self.steps)
        self.last_len = 0

    def update(self, message: str):
        """Overwrites the current line with a spinner and message."""
        frame = next(self.current_step)
        # Construct the line: Spinner + Message
        line = f"{frame} {message}"
        # Clear the previous line
        sys.stdout.write("\r" + " " * self.last_len + "\r")
        # Write new line
        sys.stdout.write(line)
        sys.stdout.flush()
        self.last_len = len(line)

    def success(self, message: str):
        self._finish("✅", message)

    def error(self, message: str):
        self._finish("❌", message)

    def info(self, message: str):
        self._finish("ℹ️ ", message)

    def _finish(self, icon, message):
        sys.stdout.write("\r" + " " * self.last_len + "\r")
        print(f"{icon} {message}")
        self.last_len = 0

# Global animator instance
console = Animator()


# ─────────────────────────────────────────────
#  Logger Setup (File only for debug)
# ─────────────────────────────────────────────

def get_logger(name: str = "kra-nil-filer") -> logging.Logger:
    os.makedirs("logs", exist_ok=True)
    log_filename = f"logs/{datetime.now().strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # File handler (detailed logs)
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    return logger


# ─────────────────────────────────────────────
#  Folder Helpers
# ─────────────────────────────────────────────

def ensure_receipts_folder() -> str:
    os.makedirs("receipts", exist_ok=True)
    return "receipts"

def receipt_path(pin: str) -> str:
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = ensure_receipts_folder()
    return os.path.join(folder, f"{pin}_{date_str}.pdf")

# ─────────────────────────────────────────────
#  OTP Helper
# ─────────────────────────────────────────────

def wait_for_otp() -> str:
    print("\n" + "─" * 50)
    print("📱 OTP Required! Check your phone.")
    otp = input("   Enter OTP: ").strip()
    print("─" * 50 + "\n")
    return otp
