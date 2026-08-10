"""
Agent monitorujący dostępność terminów na stronie ActiveNow.
Używa prawdziwej przeglądarki (Playwright), więc widzi treść taką,
jaką widzi człowiek - łącznie z tym, co ładuje się przez JavaScript.

Ten plik NIE wymaga ręcznej edycji - wszystkie dane wrażliwe (token bota,
chat_id) są wczytywane z "sekretów" ustawionych w GitHub (patrz README.md).
"""

import os
import sys
import time
import requests
from playwright.sync_api import sync_playwright

PAGE_URL = "https://zapisy.activenow.pl/zajecia-cetaphil-x-deski-zapisy/"
TEXT_WHEN_NO_SLOTS = "brak dostępnych wydarzeń"

STATE_FILE = os.path.join(os.path.dirname(__file__), "state.txt")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def get_page_text():
    """Otwiera stronę w prawdziwej przeglądarce i czeka, aż się w pełni załaduje."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(PAGE_URL, timeout=30000)
        try:
            page.wait_for_load_state("networkidle", timeout=20000)
        except Exception:
            pass
        page.wait_for_timeout(8000)
        text = page.inner_text("body")
        browser.close()
        return text


def check_current_state():
    text = get_page_text()
    return "unavailable" if TEXT_WHEN_NO_SLOTS in text.lower() else "available"


def read_previous_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return "unavailable"


def write_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        f.write(state)


def send_telegram_message(text):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("BRAK skonfigurowanych sekretów TELEGRAM_TOKEN / TELEGRAM_CHAT_ID - pomijam wysyłkę.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    resp = requests.post(url, data={"chat_id": TELEGRAM_CHAT_ID, "text": text}, timeout=15)
    resp.raise_for_status()


def main():
    previous_state = read_previous_state()
    current_state = check_current_state()

    print(f"Poprzedni stan: {previous_state} | Pierwsze sprawdzenie: {current_state}")

    if current_state == "available" and previous_state == "unavailable":
        print("Wygląda na dostępny termin - potwierdzam drugim sprawdzeniem za 15 sekund...")
        time.sleep(15)
        confirm_state = check_current_state()
        print(f"Drugie sprawdzenie: {confirm_state}")

        if confirm_state == "available":
            send_telegram_message(
                "🎾 Pojawił się nowy termin na zajęcia Cetaphil x Deski!\n"
                "Wejdź szybko i zapisz się:\n"
                "https://zapisy.activenow.pl/zajecia-cetaphil-x-deski-zapisy/"
            )
            print("Potwierdzone - wysłano powiadomienie!")
            current_state = "available"
        else:
            print("Fałszywy alarm - drugie sprawdzenie pokazało brak terminów. Nie wysyłam powiadomienia.")
            current_state = "unavailable"

    write_state(current_state)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Błąd: {e}", file=sys.stderr)
        sys.exit(1)
