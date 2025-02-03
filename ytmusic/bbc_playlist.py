#!/usr/bin/python
from ytmusicapi import YTMusic
from pathlib import Path

beebplaylist = 'PLcBZP0TaYjtGyqhwng66iAC94flzjXqdZ'
tong_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIOcGV0ZSB0b25nIDIwMjUaCXBldGUgdG9uZyINaHR0cCB1cGxvYWRlcg'
residency_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIXcmFkaW8gMXMgcmVzaWRlbmN5IDIwMjUaEnJhZGlvIDFzIHJlc2lkZW5jeSINaHR0cCB1cGxvYWRlcg'
howard_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIrcmFkaW8gMXMgZGFuY2UgcGFydHkgd2l0aCBkYW5ueSBob3dhcmQgMjAyNRomcmFkaW8gMXMgZGFuY2UgcGFydHkgd2l0aCBkYW5ueSBob3dhcmQiDWh0dHAgdXBsb2FkZXI'
clubmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIwZGFubnkgaG93YXJkcyBjbHViIG1peCB0aGUgZmVlbCBnb29kIHNlcmllcyAyMDI1GitkYW5ueSBob3dhcmRzIGNsdWIgbWl4IHRoZSBmZWVsIGdvb2Qgc2VyaWVzIg1odHRwIHVwbG9hZGVy'
essentialmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIbcmFkaW8gMXMgZXNzZW50aWFsIG1peCAyMDI1GhZyYWRpbyAxcyBlc3NlbnRpYWwgbWl4Ig1odHRwIHVwbG9hZGVy'
future_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRImZnV0dXJlIGRhbmNlIG1peCB3aXRoIHNhcmFoIHN0b3J5IDIwMjUaIWZ1dHVyZSBkYW5jZSBtaXggd2l0aCBzYXJhaCBzdG9yeSINaHR0cCB1cGxvYWRlcg'
tongmix_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIXcGV0ZSB0b25ncyBob3QgbWl4IDIwMjUaEnBldGUgdG9uZ3MgaG90IG1peCINaHR0cCB1cGxvYWRlcg'
presents_album = 'FEmusic_library_privately_owned_release_detailb_po_COTTzu7ExOqlYRIbcmFkaW8gMSBkYW5jZSBwcmVzZW50cyAyMDI1GhZyYWRpbyAxIGRhbmNlIHByZXNlbnRzIg1odHRwIHVwbG9hZGVy'


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
    for album in [tong_album, howard_album, future_album, tongmix_album, clubmix_album, essentialmix_album, residency_album, presents_album]:
        ytalbum = ytmusic.get_library_upload_album(album)
        if 'tracks' in ytalbum:
            tracks = ytalbum['tracks']
            if album == presents_album and len(tracks) > 1:
                latest.append(tracks[-2]['videoId'])
            latest.append(tracks[-1]['videoId'])
        else:
            print(f"No tracks in {album}")
    print(latest)
    result = ytmusic.add_playlist_items(beebplaylist, latest)
    print(result)


if __name__ == "__main__":
    main()
