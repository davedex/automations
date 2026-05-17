#!/usr/bin/python
import os
import sys
import time
import requests
from datetime import datetime
from pathlib import Path
from ytmusicapi import YTMusic
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup

# beatportlist = 'PLcBZP0TaYjtG_oaPRTZrE0q2th51GCjSJ'
beatportlist = 'VLPLcBZP0TaYjtE2angVmOcZzovA6u60_cb0'


def get_searches():
    searches = []
    scrapedir = Path('/home/ddexter/misc/beatport_scrapes')
    scrapedir.mkdir(parents=True, exist_ok=True)
    logfile = scrapedir / datetime.now().strftime('beatport_%Y-%m-%d.html')

    if logfile.exists():
        with open(logfile, 'r') as f:
            source = f.read()

    else:
        print("Logfile not found. Starting browser scrape...")
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")

        # --- NEW STEALTH SETTINGS ---
        # 1. Disable the "Automation" flag that Cloudflare looks for
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 2. Use a very modern User-Agent (May 2026 version)
        user_agent = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36"
        options.add_argument(f"user-agent={user_agent}")

        driver = webdriver.Chrome(options=options)

        # 3. Use JavaScript to remove the 'webdriver' property entirely
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })

        driver.get("https://www.beatport.com/top-100")

        # Increase wait to allow Cloudflare to "pass" the browser
        print("Page requested. Waiting for Cloudflare/Loading...")
        time.sleep(15)

        try:
            print(f"Current Page Title: {driver.title}") # Debug: see if we hit Cloudflare
            print("Waiting for table rows...")

            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, '[data-testid="tracks-table-row"]'))
            )
            time.sleep(2)
            source = driver.page_source
            print("Rows detected and page captured.")

            with open(logfile, 'w') as f:
                f.write(source)

        except Exception as e:
            # If it fails, let's see what the page actually looked like
            print(f"Failed to find rows. URL: {driver.current_url}")
            print(f"Page Title at failure: {driver.title}")
            driver.save_screenshot("error_screenshot.png") # This is very helpful for debugging
            driver.quit()
            return []

        driver.quit()

    soup = BeautifulSoup(source, 'html.parser') # Use standard parser for better compatibility

    # 1. Find all 'track' links first
    track_links = [a for a in soup.find_all('a') if a.get('href') and '/track/' in a.get('href')]

    # Use a set to avoid duplicates (Beatport often has 2 links per track: artwork and title)
    seen_track_ids = set()

    for link in track_links:
        href = link.get('href')
        track_id = href.split('/')[-1]

        if track_id in seen_track_ids:
            continue
        seen_track_ids.add(track_id)

        # Now find the "Row" that contains this link
        # We go up the 'parents' until we find the div that looks like a row
        row = link.find_parent('div', class_=lambda x: x and 'TableRow' in x)
        if not row:
            # Fallback: just use the link's parent container
            row = link.parent.parent

        artists = []
        # Find all artist links inside this specific row
        artist_links = [a for a in row.find_all('a') if a.get('href') and '/artist/' in a.get('href')]
        for a in artist_links:
            artists.append(a.text.strip())

        # Get the track title and mix
        title = link.get('title', link.text).strip()

        if artists and title:
            artist_str = ", ".join(dict.fromkeys(artists)) # dict.fromkeys removes duplicates while keeping order
            searches.append(f"{artist_str} - {title}")

    print('Search count: {}'.format(len(searches)))
    if searches:
        print('First: {}'.format(searches[0]))
    return searches


def delete_playlist_contents(ytmusic, playlist):
    zerolength = False
    try:
        current_contents = ytmusic.get_playlist(playlist)['tracks']
        if len(current_contents) == 0:
            zerolength = True
    except KeyError as e:
        zerolength = True
        print(e)
    if not zerolength:
        ytmusic.remove_playlist_items(playlist, current_contents)


def dedupeListOrdered(listToDedupe):
    # Deduping from https://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-whilst-preserving-order
    seen = set()
    seen_add = seen.add
    return [x for x in listToDedupe if not (x in seen or seen_add(x))]


def add_top_search_hits(ytmusic, searches, playlist):
    if not searches:
        print("No searches found. YouTube Music update skipped.")
        return
    beatportIds = []
    for searchString in searches:
        search = ytmusic.search(query=searchString, filter='songs')
        if len(search) > 0 and 'videoId' in search[0]:
            print(f'Adding {searchString}')
            beatportIds.append(search[0]['videoId'])
        else:
            print(f'Not adding {searchString}')
            if len(search) > 0:
                print(search[0])
                print(search[0].keys())
                print()
    print(f'Adding: {beatportIds}')
    # current = ytmusic.get_playlist(playlist, limit=2000)
    # if tracks in current and len(current['tracks']) > 0:
    #     ytmusic.remove_playlist_items(playlist, current['tracks'])
    return ytmusic.add_playlist_items(playlist, dedupeListOrdered(beatportIds), duplicates=False)


def main():
    headers = Path(__file__).parent / 'browser.json'
    ytmusic = YTMusic(str(headers.resolve()))

    searches = get_searches()
    print(len(searches))
    delete_playlist_contents(ytmusic, beatportlist)
    add_top_search_hits(ytmusic, searches, beatportlist)


if __name__ == "__main__":
    main()
