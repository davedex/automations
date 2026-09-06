#!/usr/bin/env python3
import os
import sys
import shutil
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def main():
    profile_dir = Path("/home/ddexter/.config/ytmusic-automation-profile")
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"Using persistent Chrome profile directory: {profile_dir}")

    options = Options()
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")

    # Discovery of Chromium / Chrome binary on NixOS
    chrome_bin = os.environ.get("CHROME_BIN")
    if not chrome_bin:
        for bin_name in ["chromium", "google-chrome", "google-chrome-stable", "chrome"]:
            found = shutil.which(bin_name)
            if found:
                chrome_bin = found
                break

    if chrome_bin:
        print(f"Found Chrome/Chromium binary at: {chrome_bin}")
        options.binary_location = chrome_bin
    else:
        print("Warning: Could not find chromium or google-chrome in PATH. Let's hope Selenium can auto-discover it.")

    # Discovery of Chromedriver on NixOS
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if not chromedriver_path:
        chromedriver_path = shutil.which("chromedriver")

    service = None
    if chromedriver_path:
        print(f"Found Chromedriver at: {chromedriver_path}")
        service = Service(executable_path=chromedriver_path)
    else:
        print("Warning: Could not find chromedriver in PATH. Let's hope Selenium can auto-discover it.")
        service = Service()

    # Stealth settings to avoid automated browser detection during login
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    print("Initializing webdriver in non-headless mode...")
    try:
        driver = webdriver.Chrome(service=service, options=options)

        # Override navigator.webdriver property
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        print("Navigating to YouTube Music...")
        driver.get("https://music.youtube.com")

        print("\n" + "="*70)
        print("INTERACTIVE SETUP INSTRUCTIONS:")
        print("1. A non-headless Chrome window should have opened on your display.")
        print("   (Ensure X11 forwarding with 'ssh -Y' is active if running remotely).")
        print("2. Click 'Sign In' in the top-right corner of the page.")
        print("3. Enter your credentials and log in to your Google / YouTube Music account.")
        print("4. Verify that you are successfully logged in and can view your home feed.")
        print("5. Once complete, return to this terminal and press Enter to save the session.")
        print("="*70 + "\n")

        input("Press [ENTER] after logging in to save your Chrome session and exit...")

        print("Closing the browser and saving session...")
        driver.quit()
        print("Success: Persistent Chrome profile saved to /home/ddexter/.config/ytmusic-automation-profile")

    except Exception as e:
        print(f"Error executing setup: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
