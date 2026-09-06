#!/usr/bin/env python
import subprocess
import sys
from ytmusicapi import YTMusic
from pathlib import Path

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
    if len(sys.argv) < 2:
        print("Usage: ", sys.argv[0], "file_to_upload [additional_files...]")
        sys.exit(1)

    # Support batch file uploads
    files_to_upload = sys.argv[1:]

    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'

    # Always ensure a clean start to avoid race conditions or stale credentials
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
    finally:
        # Clean up unencrypted file immediately to maintain strict system security
        if browser_file.exists():
            browser_file.unlink()

    successful_uploads = []
    failed_uploads = []

    for filepath in files_to_upload:
        p = Path(filepath)
        filename = p.name
        try:
            print(f"Uploading: {filepath}")
            response = ytmusic.upload_song(str(p))

            # Check for upload failure states to ensure systemd catches errors
            if isinstance(response, str) and "STATUS_FAILED" in response:
                print(f"Upload failed for {filename}: {response}")
                failed_uploads.append((filename, response))
            else:
                print(f"Uploaded successfully: {filename}")
                successful_uploads.append(filename)
        except Exception as e:
            print(f"Upload error for {filename}: {e}")
            failed_uploads.append((filename, str(e)))

    # Construct and send aggregated Discord message
    if successful_uploads or failed_uploads:
        msg_parts = ["🎵 **YouTube Music Upload Summary**"]
        if successful_uploads:
            msg_parts.append("\n✅ **Successful Uploads:**")
            for f in successful_uploads:
                msg_parts.append(f"- `{f}`")
        if failed_uploads:
            msg_parts.append("\n❌ **Failed Uploads:**")
            for f, err in failed_uploads:
                msg_parts.append(f"- `{f}` (Error: `{err}`)")

        send_discord_message("\n".join(msg_parts))

    # Exit with error if any uploads failed
    if failed_uploads:
        sys.exit(1)

if __name__ == "__main__":
    main()
