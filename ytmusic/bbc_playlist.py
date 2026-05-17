#!/usr/bin/python
from ytmusicapi import YTMusic
from pathlib import Path

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
    headers = Path(__file__).parent / 'browser.json'
    ytmusic = YTMusic(str(headers.resolve()))
    zerolength = False
    try:
        current_contents = ytmusic.get_playlist(beebplaylist)['tracks']
        if len(current_contents) == 0:
            zerolength = True
    except KeyError as e:
        zerolength = True
        print(e)
    if not zerolength:
        ytmusic.remove_playlist_items(beebplaylist, current_contents)
    latest = []
    #for album in [tong_album, howard_album, future_album, clubmix_album, essentialmix_album, residency_album]:
    for album in [tong_album, howard_album, future_album, tongmix_album, clubmix_album, essentialmix_album, residency_album, presents_album]:
        ytalbum = ytmusic.get_library_upload_album(album)
        if 'tracks' in ytalbum:
            tracks = ytalbum['tracks']
            two_track_albums = {presents_album, residency_album}
            if album in two_track_albums and len(tracks) > 1:
                latest.append(tracks[-2]['videoId'])
            latest.append(tracks[-1]['videoId'])
        else:
            print(f"No tracks in {album}")
    print(latest)
    result = ytmusic.add_playlist_items(beebplaylist, latest)
    print(result)


if __name__ == "__main__":
    main()
