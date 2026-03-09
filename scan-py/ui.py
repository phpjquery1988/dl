"""
ui.py — Terminal UI helpers
"""

import sys
import os


class UI:
    # ANSI colour codes (auto-disabled if not a TTY)
    _tty = sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and os.environ.get('TERM'))

    RESET  = "\033[0m"  if _tty else ""
    BOLD   = "\033[1m"  if _tty else ""
    DIM    = "\033[2m"  if _tty else ""
    GREEN  = "\033[92m" if _tty else ""
    YELLOW = "\033[93m" if _tty else ""
    RED    = "\033[91m" if _tty else ""
    CYAN   = "\033[96m" if _tty else ""
    BLUE   = "\033[94m" if _tty else ""
    WHITE  = "\033[97m" if _tty else ""

    @staticmethod
    def header(name: str, version: str):
        w = 62
        print()
        print(f"{UI.CYAN}{'═' * w}{UI.RESET}")
        title = f"  {name}  v{version}"
        print(f"{UI.BOLD}{UI.WHITE}{title}{UI.RESET}")
        sub = "  Engine: zxing-cpp (PDF417)  |  Standard: AAMVA DL/ID 2020"
        print(f"{UI.DIM}{sub}{UI.RESET}")
        print(f"{UI.CYAN}{'═' * w}{UI.RESET}")
        print()

    @staticmethod
    def success(msg: str):
        print(f"{UI.GREEN}  ✓  {msg}{UI.RESET}")

    @staticmethod
    def error(msg: str):
        print(f"{UI.RED}  ✗  {msg}{UI.RESET}")

    @staticmethod
    def warn(msg: str):
        print(f"{UI.YELLOW}  ⚠  {msg}{UI.RESET}")

    @staticmethod
    def info(msg: str):
        print(f"{UI.CYAN}  ›  {msg}{UI.RESET}")
