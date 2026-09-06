#!/usr/bin/env python3
import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

def send_discord_message(message: str):
    token_file = Path('/run/user/1000/secrets/discord_bot_token')
    if not token_file.exists():
        print(f"Warning: Discord token file not found at {token_file}. Skipping notification.")
        return

    try:
        import discord
        from discord.ext import commands
    except ImportError:
        print("Warning: discord.py package not found. Skipping notification.")
        return

    try:
        with open(token_file, 'r') as file:
            token = file.read().strip()

        channel_id = 1330828675847028819
        intents = discord.Intents.default()
        intents.messages = True

        bot = commands.Bot(command_prefix='!', intents=intents)

        @bot.event
        async def on_ready():
            print(f"Logged into Discord as {bot.user.name}")
            channel = bot.get_channel(channel_id)
            if channel:
                print(f"Sending Discord message to channel {channel_id}...")
                await channel.send(message)
            else:
                print(f"Error: Discord channel {channel_id} not found.")
            await bot.close()

        print("Starting Discord bot client...")
        bot.run(token)
        print("Discord notification sent and bot disconnected.")
    except Exception as e:
        print(f"Warning: Failed to send Discord notification: {e}", file=sys.stderr)

def main():
    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'
    profile_dir = Path("/home/ddexter/.config/ytmusic-automation-profile")
    age_key_file = Path("/home/ddexter/.config/sops/age/keys.txt")
    age_public_key = "age1gv4dcqrw9hm3u9f04xwv0e94mf4dk3m3wpccr23nqqxs4049gq9qmxemfs"

    # Define debug file paths to clean up on success
    debug_screenshot_path = script_dir / 'debug_headless_state.png'
    debug_log_path = script_dir / 'debug_performance_logs.json'

    print("Checking directories and key files...")
    if not profile_dir.exists():
        print(f"Error: Profile directory {profile_dir} does not exist.")
        print("Please run chromium manually to authenticate once.")
        sys.exit(1)

    if not age_key_file.exists():
        print(f"Error: Age key file not found at {age_key_file}.")
        sys.exit(1)

    print(f"Target browser.json: {browser_file}")
    print(f"Target encrypted_browser.json: {encrypted_browser}")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument(f"--user-data-dir={profile_dir}")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1280,800")

    # Enable Performance Logging to capture outgoing HTTP requests (Authorization header)
    print("Enabling performance logs...")
    options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    # Discovery of Chromium / Chrome binary on NixOS
    chrome_bin = os.environ.get("CHROME_BIN")
    if not chrome_bin:
        for bin_name in ["chromium", "google-chrome", "google-chrome-stable", "chrome"]:
            found = shutil.which(bin_name)
            if found:
                chrome_bin = found
                break

    if chrome_bin:
        print(f"Using Chrome binary: {chrome_bin}")
        options.binary_location = chrome_bin

    # Discovery of Chromedriver on NixOS
    chromedriver_path = os.environ.get("CHROMEDRIVER_PATH")
    if not chromedriver_path:
        chromedriver_path = shutil.which("chromedriver")

    service = None
    if chromedriver_path:
        print(f"Using Chromedriver: {chromedriver_path}")
        service = Service(executable_path=chromedriver_path)
    else:
        service = Service()

    # Stealth settings to mimic a natural browser
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
    options.add_argument(f"user-agent={user_agent}")

    print("Starting headless Chrome browser...")
    driver = webdriver.Chrome(service=service, options=options)

    # CDP Script to mask automation
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            })
        """
    })

    try:
        print("Navigating to YouTube Music to trigger requests...")
        driver.get("https://music.youtube.com")

        print("Waiting 12 seconds for the feed to load and API requests to execute...")
        time.sleep(12)

        print("Taking debug screenshot to verify login state...")
        driver.save_screenshot(str(debug_screenshot_path))

        # Retrieve Cookies directly from browser's secure memory store
        print("Retrieving cookies directly from Selenium...")
        cookies_list = driver.get_cookies()
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies_list])
        print(f"Successfully retrieved {len(cookies_list)} session cookies.")

        print("Fetching performance logs...")
        logs = driver.get_log('performance')
        driver.quit()
        print("Headless browser closed.")

        browse_request_headers = None
        target_endpoint_found = ""

        print("Analyzing performance logs for youtubei API requests...")
        for entry in logs:
            try:
                log_data = json.loads(entry['message'])['message']
                if log_data.get('method') == 'Network.requestWillBeSent':
                    request = log_data.get('params', {}).get('request', {})
                    url = request.get('url', '')

                    if 'youtubei/v1/' in url:
                        headers = request.get('headers', {})
                        h_lower = {k.lower(): v for k, v in headers.items()}

                        # We only need to find the Authorization header here
                        if 'authorization' in h_lower:
                            # Prioritize the /browse endpoint specifically
                            if 'youtubei/v1/browse' in url:
                                print(f"Found request headers from target endpoint: {url}")
                                browse_request_headers = headers
                                target_endpoint_found = url
                                break
                            # Fallback to other authenticated youtubei endpoints
                            elif browse_request_headers is None:
                                print(f"Found request headers from fallback endpoint: {url}")
                                browse_request_headers = headers
                                target_endpoint_found = url
            except Exception:
                continue

        if not browse_request_headers:
            print("Error: Failed to intercept any authenticated requests to youtubei/v1/ API.", file=sys.stderr)

            # Dump raw logs to see what was actually captured
            print(f"Dumping raw performance logs for debugging to {debug_log_path}", file=sys.stderr)
            with open(debug_log_path, 'w') as f:
                json.dump([json.loads(e['message']) for e in logs], f, indent=2)

            print("Please ensure you are fully authenticated in Chromium.", file=sys.stderr)
            sys.exit(1)

        print(f"Extracted API parameters from endpoint: {target_endpoint_found}")

        # Map to standard browser.json format used by ytmusicapi
        h_lower = {k.lower(): v for k, v in browse_request_headers.items()}

        auth_header = h_lower.get("authorization")
        if not auth_header:
            print("Error: Missing crucial Authorization request header in performance logs.", file=sys.stderr)
            sys.exit(1)

        if not cookie_str:
            print("Error: Missing session Cookies from browser.", file=sys.stderr)
            sys.exit(1)

        browser_json_content = {
            "User-Agent": h_lower.get("user-agent", user_agent),
            "Accept": h_lower.get("accept", "*/*"),
            "Accept-Language": h_lower.get("accept-language", "en-US,en;q=0.9"),
            "Content-Type": h_lower.get("content-type", "application/json"),
            "x-goog-authuser": h_lower.get("x-goog-authuser", h_lower.get("x-goog-authuser", "0")),
            "x-origin": h_lower.get("origin", h_lower.get("x-origin", "https://music.youtube.com")),
            "Authorization": auth_header,
            "Cookie": cookie_str
        }

        print("Writing temporary unencrypted browser.json...")
        with open(browser_file, 'w') as fh:
            json.dump(browser_json_content, fh, indent=2)

        # Enforce sops encryption
        print("Encrypting browser.json to encrypted_browser.json via SOPS...")
        env = os.environ.copy()
        env["SOPS_AGE_KEY_FILE"] = str(age_key_file)

        with open(encrypted_browser, 'w') as fh:
            subprocess.run(
                [
                    'sops',
                    '--age', age_public_key,
                    '-e', str(browser_file)
                ],
                stdout=fh,
                check=True,
                timeout=15,
                env=env
            )

        print("Encryption successful! Deleting raw browser.json...")
        if browser_file.exists():
            browser_file.unlink()

        # Clean up any leftover debug artifacts on success to keep directory clean
        print("Cleaning up debug logs and screenshots...")
        if debug_screenshot_path.exists():
            debug_screenshot_path.unlink()
        if debug_log_path.exists():
            debug_log_path.unlink()

        print("Success! encrypted_browser.json has been refreshed and secure credentials saved.")
        send_discord_message("✅ **YouTube Music Headers Refreshed Successfully!**\nNew session credentials have been extracted and encrypted via SOPS on `dexnix`.")

    except Exception as e:
        error_msg = f"❌ **YouTube Music Header Refresh FAILED on `dexnix`!**\nError: `{e}`\n*Please check systemd journal logs for details.*"
        send_discord_message(error_msg)
        print(f"Error executing header refresh: {e}", file=sys.stderr)
        # Attempt to clean up raw browser.json on error
        try:
            if browser_file.exists():
                browser_file.unlink()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    main()
