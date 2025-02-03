#!/usr/bin/python
import discord
import sys
from discord.ext import commands
from pathlib import Path
from ytmusicapi import YTMusic

def main():
    print("Authenticating with ytmusic")
    headers = Path(__file__).parent / 'browser.json'
    ytmusic = YTMusic(str(headers.resolve()))

    # The following command will raise a YTMusicUserError if unauthorized (https://github.com/sigma67/ytmusicapi/blob/main/ytmusicapi/ytmusic.py#L260)
    ytmusic._check_auth()

    # Read the like songs. Make sure liked is greater than 800 songs
    liked = ytmusic.get_liked_songs() 
    if liked['trackCount'] < 800:
        message = """Authentication seems problematic.
                     Rerun browser authentication (perhaps in the ytmusic venv in wsl on the thinkpad)
                     Update the secret in nixos"""
        # Send discord message
        with open('/run/user/1000/secrets/discord_bot_token', 'r') as file:
            TOKEN = file.read().strip()
        CHANNEL_ID = 1330828675847028819
        intents = discord.Intents.default()
        intents.messages = True
        bot = commands.Bot(command_prefix='!', intents=intents)
        @bot.event
        async def on_ready():
            print(f'Logged in as {bot.user.name}')
            channel = bot.get_channel(CHANNEL_ID)
            await channel.send(message)
            await bot.close()
        bot.run(TOKEN)
        sys.exit(401)
    print("Authentication seems ok")


if __name__ == "__main__":
    main()
