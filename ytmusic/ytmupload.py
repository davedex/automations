#!/usr/bin/env python
import subprocess
import sys
from ytmusicapi import YTMusic
from pathlib import Path


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

    if len(sys.argv) != 2:
        print("Usage: ", sys.argv[0], "file_to_upload")
        sys.exit(1)

    result = upload(ytmusic, sys.argv[1])
    print(result)

def upload(ytm, uploadfile):
    print('Uploading:', uploadfile)
    response = ytm.upload_song(uploadfile)
    
    # Check for upload failure states to ensure systemd catches errors
    if isinstance(response, str) and "STATUS_FAILED" in response:
        print("Upload failed:", response)
        sys.exit(1)
        
    return response


if __name__ == "__main__":
    main()
