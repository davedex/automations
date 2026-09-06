#!/usr/bin/python
import subprocess
import sys
from pathlib import Path
from ytmusicapi import YTMusic

beebplaylist = 'PLcBZP0TaYjtGyqhwng66iAC94flzjXqdZ'
tong_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIOcGV0ZSB0b25nIDIwMjYaCXBldGUgdG9uZyINaHR0cCB1cGxvYWRlcg'
residency_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIfcmVzaWRlbmN5IG9uIHJhZGlvIDEgZGFuY2UgMjAyNhoacmVzaWRlbmN5IG9uIHJhZGlvIDEgZGFuY2UiDWh0dHAgdXBsb2FkZXI'
howard_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIrcmFkaW8gMXMgZGFuY2UgcGFydHkgd2l0aCBkYW5ueSBob3dhcmQgMjAyNhomcmFkaW8gMXMgZGFuY2UgcGFydHkgd2l0aCBkYW5ueSBob3dhcmQiDWh0dHAgdXBsb2FkZXI'
clubmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIhcmFkaW8gMSBkYW5jZSBwYXJ0eSBzdGFydGVycyAyMDI2GhxyYWRpbyAxIGRhbmNlIHBhcnR5IHN0YXJ0ZXJzIg1odHRwIHVwbG9hZGVy'
essentialmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIbcmFkaW8gMXMgZXNzZW50aWFsIG1peCAyMDI2GhZyYWRpbyAxcyBlc3NlbnRpYWwgbWl4Ig1odHRwIHVwbG9hZGVy'
future_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIrcmFkaW8gMXMgZnV0dXJlIGRhbmNlIHdpdGggc2FyYWggc3RvcnkgMjAyNhomcmFkaW8gMXMgZnV0dXJlIGRhbmNlIHdpdGggc2FyYWggc3RvcnkiDWh0dHAgdXBsb2FkZXI'
tongmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIXcGV0ZSB0b25ncyBob3QgbWl4IDIwMjYaEnBldGUgdG9uZ3MgaG90IG1peCINaHR0cCB1cGxvYWRlcg'
presents_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIbcmFkaW8gMSBkYW5jZSBwcmVzZW50cyAyMDI2GhZyYWRpbyAxIGRhbmNlIHByZXNlbnRzIg1odHRwIHVwbG9hZGVy'


def main():
    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'

    # Decrypt encrypted_browser.json if local browser.json doesn't exist
    if not browser_file.exists():
        if not encrypted_browser.exists():
            print(f"Error: {encrypted_browser} does not exist.")
            sys.exit(1)

        print("Decrypting browser.json...")
        key_path = Path.home() / '.config/sops/age/keys.txt'
        with open(browser_file, 'w') as fh:
            subprocess.run(
                ['sops', '--age', str(key_path), '-d', str(encrypted_browser)],
                stdout=fh,
                check=True,
                timeout=10
            )
    else:
        print("Already decrypted browser.json found")

    ytmusic = YTMusic(str(browser_file))

    # Clear current contents of the playlist safely
    try:
        playlist_info = ytmusic.get_playlist(beebplaylist, limit=None)
        current_contents = playlist_info.get('tracks', [])
        if current_contents:
            print(f"Clearing {len(current_contents)} tracks from playlist...")
            ytmusic.remove_playlist_items(beebplaylist, current_contents)
    except Exception as e:
        print(f"Warning: Failed to clear playlist contents: {e}")

    latest = []
    # For each album, fetch the tracks and grab the latest uploads safely
    for album in [tong_album, howard_album, future_album, tongmix_album, clubmix_album, essentialmix_album, residency_album, presents_album]:
        try:
            ytalbum = ytmusic.get_library_upload_album(album)
            if 'tracks' in ytalbum:
                tracks = ytalbum['tracks']
                if not tracks:
                    print(f"No tracks in {album}")
                    continue

                two_track_albums = {presents_album, residency_album}
                if album in two_track_albums and len(tracks) > 1:
                    latest.append(tracks[-2]['videoId'])
                latest.append(tracks[-1]['videoId'])
            else:
                print(f"No tracks list in album {album}")
        except Exception as e:
            print(f"Error fetching album {album}: {e}")

    if latest:
        print(f"Adding tracks to playlist: {latest}")
        result = ytmusic.add_playlist_items(beebplaylist, latest)
        print(result)
    else:
        print("No tracks found to add to playlist.")


if __name__ == "__main__":
    main()
