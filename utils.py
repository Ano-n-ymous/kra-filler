import logging
import os
from datetime import datetime


# ─────────────────────────────────────────────
#  Logger Setup
# ─────────────────────────────────────────────

def get_logger(name: str = "kra-nil-filer") -> logging.Logger:
    """
    Returns a logger that writes to both the console
    and a daily log file inside the logs/ folder.
    """
    os.makedirs("logs", exist_ok=True)

    log_filename = f"logs/{datetime.now().strftime('%Y-%m-%d')}.log"

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Avoid adding duplicate handlers on re-import
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_filename, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger


# ─────────────────────────────────────────────
#  Folder Helpers
# ─────────────────────────────────────────────

def ensure_receipts_folder() -> str:
    """Creates receipts/ folder if it doesn't exist and returns its path."""
    os.makedirs("receipts", exist_ok=True)
    return "receipts"


def receipt_path(pin: str) -> str:
    """
    Generates a receipt file path for a given PIN.
    Example: receipts/A000000000X_2025-01-01.pdf
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    folder = ensure_receipts_folder()
    return os.path.join(folder, f"{pin}_{date_str}.pdf")


# ─────────────────────────────────────────────
#  OTP / Manual Pause Helper
# ─────────────────────────────────────────────

def wait_for_otp() -> str:
    """
    Pauses execution and prompts the user to enter the OTP
    received via SMS. Returns the OTP string.
    """
    print("\n" + "─" * 50)
    print("📱 OTP Required!")
    print("   Check your phone for the KRA SMS code.")
    otp = input("   Enter OTP here and press Enter: ").strip()
    print("─" * 50 + "\n")
    return otp
