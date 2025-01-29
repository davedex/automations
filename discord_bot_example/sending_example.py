import discord
from discord.ext import commands

# Read the bot token from the file
with open('/run/user/1000/secrets/discord_bot_token', 'r') as file:
    TOKEN = file.read().strip()

# Replace 'YOUR_CHANNEL_ID' with the ID of the channel you want to send a message to
CHANNEL_ID = 1330828675847028819

# Define the intents your bot needs
intents = discord.Intents.default()
intents.messages = True

# Create a bot instance with the specified intents
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send('Hey from a python discord bot again!')
    await bot.close()

# Run the bot
bot.run(TOKEN)
