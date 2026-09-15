#!/usr/bin/env python3
import os
import re
import sys
import json
import html
import time
import random
import requests
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from ytmusicapi import YTMusic

# =============================================================================
# CONFIG
# =============================================================================

PLAYLIST_ID = "PLcBZP0TaYjtHltisCNQ_A4v_beXwWN4Up"
CACHE_FILE = Path("essential_new_tunes_cache.json")

# Limit the number of new pages scraped in a single run to avoid rate-limiting or blocking.
# Set to None for unlimited. Let's set it to 2 for safe and rapid local testing!
MAX_PAGES_PER_RUN = 30

# =============================================================================
# DISCORD NOTIFICATIONS
# =============================================================================

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

# =============================================================================
# SCRAPING HELPERS
# =============================================================================

def get_date_from_url(url: str) -> str:
    """Extract date (YYYY-MM-DD) from the WordPress URL structure."""
    match = re.search(r'/(\d{4})/(\d{2})/(\d{2})/', url)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    # Fallback to year/month or placeholder
    match_short = re.search(r'/(\d{4})/(\d{2})/', url)
    if match_short:
        return f"{match_short.group(1)}-{match_short.group(2)}-01"
    return "1970-01-01"

def sanitize_query(text: str) -> str:
    """Clean up curly quotes and unescape HTML entities for optimal YTM search."""
    text = html.unescape(text)
    # Remove single and double curly/straight quotes
    for q in ["‘", "’", "“", "”", "'", '"']:
        text = text.replace(q, "")
    # Standardize whitespace
    return " ".join(text.split()).strip()

def extract_essential_new_tune(html_content: str) -> str | None:
    """Inspect element paragraphs to extract the tune following the label."""
    soup = BeautifulSoup(html_content, 'html.parser')
    for p in soup.find_all('p'):
        text = html.unescape(p.get_text('\n', strip=True))
        if 'essential new tune' in text.lower():
            lines = [l.strip() for l in text.split('\n') if l.strip()]
            for i, line in enumerate(lines):
                if 'essential new tune' in line.lower():
                    if i + 1 < len(lines):
                        return lines[i+1]
    return None

# =============================================================================
# MAIN PIPELINE
# =============================================================================

def main():
    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'

    # 1. Decryption Bootstrap
    if browser_file.exists():
        browser_file.unlink()

    if not encrypted_browser.exists():
        print(f"Error: {encrypted_browser} does not exist.")
        sys.exit(1)

    print("Decrypting browser.json...")
    key_path = Path.home() / '.config/sops/age/keys.txt'
    try:
        with open(browser_file, 'w') as fh:
            subprocess.run(
                ['sops', '--age', str(key_path), '-d', str(encrypted_browser)],
                stdout=fh,
                check=True,
                timeout=10
            )
        
        ytmusic = YTMusic(str(browser_file))
    except Exception as e:
        print(f"Bootstrap/Decryption failed: {e}")
        send_discord_message(f"❌ **Pete Tong Sync FAILED!**\nCredential decryption error: `{e}`")
        sys.exit(1)
    finally:
        # Clean up unencrypted file immediately to maintain strict system security
        if browser_file.exists():
            browser_file.unlink()

    try:
        # 2. Load Scraped Cache
        if CACHE_FILE.exists():
            with open(CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
        else:
            cache = {}

        print(f"Loaded cache containing {len(cache)} processed show links.")

        # 3. Discover all Radio Show links from directory
        print("Fetching Pete Tong Radio Directory page...")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept-Encoding': 'gzip, deflate'  # Explicitly omit 'br' to avoid Brotli decoding issues in python's urllib3
        }
        r = requests.get('https://www.petetong.com/radio/', headers=headers, timeout=20)
        r.raise_for_status()

        # Find absolute URL matches matching date structure
        all_show_links = re.findall(r'https://www.petetong.com/\d{4}/\d{2}/\d{2}/[a-zA-Z0-9-]+/', r.text)
        # Filter to Radio One shows specifically
        radio_one_links = sorted(list(set([l for l in all_show_links if 'radio-one' in l])))
        print(f"Discovered {len(radio_one_links)} total Radio One show URLs in JavaScript / HTML content.")

        # 4. Identify new show links to scrape
        new_links = [l for l in radio_one_links if l not in cache]
        print(f"Found {len(new_links)} new show links to scrape.")

        if new_links:
            # Sort reverse chronologically by date in URL (newest first) to scrape latest shows first
            new_links.sort(key=get_date_from_url, reverse=True)
            
            # Apply run limit
            if MAX_PAGES_PER_RUN is not None and len(new_links) > MAX_PAGES_PER_RUN:
                print(f"Limiting scraping to {MAX_PAGES_PER_RUN} pages in this run to avoid rate-limiting.")
                new_links = new_links[:MAX_PAGES_PER_RUN]

            scraped_count = 0
            found_count = 0

            print(f"Scraping batch of {len(new_links)} pages...")
            for idx, url in enumerate(new_links, 1):
                parsed_date = get_date_from_url(url)
                print(f"[{idx}/{len(new_links)}] Scraping: {url} ({parsed_date})")
                try:
                    show_res = requests.get(url, headers=headers, timeout=15)
                    show_res.raise_for_status()
                    
                    tune = extract_essential_new_tune(show_res.text)
                    if tune:
                        print(f"  -> Extracted Essential New Tune: {repr(tune)}")
                        cache[url] = {
                            "date": parsed_date,
                            "essential_new_tune": tune,
                            "videoId": None
                        }
                        found_count += 1
                    else:
                        print("  -> No Essential New Tune found on page.")
                        cache[url] = {
                            "date": parsed_date,
                            "essential_new_tune": None,
                            "videoId": None
                        }
                    scraped_count += 1
                    # Polite delay between scrapes
                    time.sleep(random.uniform(1.0, 2.5))
                except Exception as scrape_err:
                    print(f"  -> Error scraping page: {scrape_err}")
                    # Don't cache so we retry next run

            # Save scraped cache back to disk
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print(f"Scrape phase complete. Saved cache updates. Scraped {scraped_count} pages, found {found_count} tunes.")

        # 5. Search YouTube Music for missing videoIds
        unmatched_tunes = [url for url, data in cache.items() if data.get("essential_new_tune") and data.get("videoId") is None]
        print(f"Checking {len(unmatched_tunes)} tunes for missing YouTube Music videoIds...")

        matched_count = 0
        if unmatched_tunes:
            for idx, url in enumerate(unmatched_tunes, 1):
                data = cache[url]
                raw_tune = data["essential_new_tune"]
                query = sanitize_query(raw_tune)
                print(f"[{idx}/{len(unmatched_tunes)}] Searching YTM: {repr(query)}")
                try:
                    search_results = ytmusic.search(query=query, filter="songs")
                    if search_results and "videoId" in search_results[0]:
                        vid = search_results[0]["videoId"]
                        data["videoId"] = vid
                        print(f"  -> Found Match videoId: {vid} (Title: {search_results[0].get('title')})")
                        matched_count += 1
                    else:
                        print("  -> No songs found matching query.")
                    time.sleep(random.uniform(0.5, 1.2))
                except Exception as search_err:
                    print(f"  -> Search error: {search_err}")

            # Save updated videoIds to disk
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=2, ensure_ascii=False)
            print("YTM Search phase complete. Saved matches to cache.")

        # 6. Rebuild Playlist chronologically
        # Extract all valid videoIds, sorted by show date
        valid_entries = []
        for url, data in cache.items():
            if data.get("videoId"):
                valid_entries.append((data["date"], data["videoId"], data["essential_new_tune"]))

        # Sort reverse-chronologically by show date (latest first to oldest last)
        valid_entries.sort(key=lambda x: x[0], reverse=True)
        playlist_video_ids = [entry[1] for entry in valid_entries]

        print(f"Total resolved Essential New Tunes in cache: {len(playlist_video_ids)}")

        # Clear and sync the playlist
        print(f"Rebuilding playlist: {PLAYLIST_ID}")
        # Fetch existing items to clear
        existing_pl = ytmusic.get_playlist(PLAYLIST_ID, limit=5000)
        existing_tracks = existing_pl.get("tracks") or []
        
        if existing_tracks:
            print(f"Clearing {len(existing_tracks)} current tracks from playlist...")
            ytmusic.remove_playlist_items(PLAYLIST_ID, existing_tracks)
            time.sleep(3)

        # Unique videoIds, preserving chronological order
        unique_video_ids = list(dict.fromkeys(playlist_video_ids))

        if unique_video_ids:
            print(f"Adding {len(unique_video_ids)} Essential New Tunes to playlist...")
            # add_playlist_items can take up to 100 items at a time safely
            chunk_size = 100
            for i in range(0, len(unique_video_ids), chunk_size):
                chunk = unique_video_ids[i:i + chunk_size]
                print(f"Adding chunk {i // chunk_size + 1}...")
                ytmusic.add_playlist_items(PLAYLIST_ID, chunk, duplicates=False)
                time.sleep(2)
            print("Playlist successfully synchronized!")

        # 7. Discord notification
        scraped_summary = f"Scraped {len(new_links)} new show pages (found {found_count} tunes)." if new_links else "No new show pages scraped."
        match_summary = f"Matched {matched_count} tunes on YTM." if matched_count > 0 else "No new tunes matched."
        
        success_msg = (
            f"✅ **Pete Tong Essential New Tunes Sync Successful!**\n"
            f"- {scraped_summary}\n"
            f"- {match_summary}\n"
            f"- Total tunes currently in playlist: **{len(unique_video_ids)}**"
        )
        send_discord_message(success_msg)

    except Exception as e:
        print(f"Execution failed: {e}", file=sys.stderr)
        send_discord_message(f"❌ **Pete Tong Essential New Tunes Sync FAILED!**\nError: `{e}`")
        raise e

if __name__ == "__main__":
    main()
