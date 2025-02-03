#!/usr/bin/python
import subprocess
import sys
from ytmusicapi import YTMusic
from pathlib import Path


def main():
    headers = Path(__file__).parent / 'browser.json'
    if not headers.exists():
        print("Decrypting browser.json")
        with open('browser.json', 'w') as fh:
            decrypt_process = subprocess.run(['sops', '--age', '~/.config/sops/age/keys.txt', '-d', 'encrypted_browser.json'], stdout=fh, timeout=5)
    else:
        print("Already decrypted browser.json found")
    ytmusic = YTMusic(str(headers.resolve()))
    if len(sys.argv) != 2:
        print("Usage: ", sys.argv[0], "file_to_upload")
        sys.exit(1)
    print(upload(ytmusic, sys.argv[1]))

def upload(ytm, uploadfile):
    print('Uploading: ', uploadfile)
    return ytm.upload_song(uploadfile)


if __name__ == "__main__":
    main()
