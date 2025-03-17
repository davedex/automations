#!/usr/bin/python
import os
import sys
import requests
from datetime import datetime
from pathlib import Path
from ytmusicapi import YTMusic
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup

# beatportlist = 'PLcBZP0TaYjtG_oaPRTZrE0q2th51GCjSJ'
beatportlist = 'VLPLcBZP0TaYjtE2angVmOcZzovA6u60_cb0'


def get_searches():
    searches = []
    # Get the top100
    scrapedir = Path('/home/ddexter/misc/beatport_scrapes')
    scrapedir.mkdir(parents=True, exist_ok=True)
    logfile = scrapedir / datetime.now().strftime('beatport_%Y-%m-%d.html')
    if logfile.exists():
        with open(logfile, 'r') as f:
            source = f.read()
    else:
        options = Options()
        options.add_argument("--headless")  # Run without GUI
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")

        driver = webdriver.Chrome(options=options)
        driver.get("http://www.beatport.com/top-100")
        source = driver.page_source
        with open(logfile, 'w') as f:
            f.write(source)
        print(f'Written {logfile}')

    soup = BeautifulSoup(source, 'lxml')
    for entry in soup.find_all('div', attrs={'data-testid': 'tracks-list-item'}):
        data = {'artist':[], 'title':[]}
        #titlecell = entry.find('div', attrs={'class': "sc-fdd08fbd-0 bgDQwW cell title"})
        for link in entry.find_all('a'):
            if not link.has_attr('href'):
                continue
            if link['href'].split('/')[1] == 'track':
                data['title'] += [link['title']]
                track_spans = link.find_all('span', attrs={'class': "Lists-shared-style__ItemName-sc-d366b33c-7 iODurf"})
                first_span = track_spans[0] if track_spans else None
                data['mix'] = first_span.find_all('span')[0].text if first_span.find_all('span') else None
            if link['href'].split('/')[1] == 'artist':
                data['artist'] += [link['title']]
        title = ', '.join([x.replace('Original Mix', '').replace('Extended Mix', '') for x in data['title']])
        artists = ', '.join(data['artist'])
        mix = '' if data['mix'] == 'Original Mix' else data['mix']
        searches.append(f"{artists} - {title} {mix}")

    print('Search count: {}'.format(len(searches)))
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
