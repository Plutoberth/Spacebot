import rethinkdb as db
import discord
import asyncio
import json
import sys
from io import TextIOWrapper

f = open("tokens.json","r")
tokens = json.loads(f.read())
f.close()

# Adds error logging to Linux journalctl
sys.stdout = TextIOWrapper(sys.stdout.detach(),
                           encoding=sys.stdout.encoding,
                           errors="replace",
                           line_buffering=True)

db.connect("localhost", 28015, 'spacebot').repl()

class RSSContent:
    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):

        self.bot.loop.create_task(self.RSSContent())

    async def rss_content(self):
        while not self.bot.is_closed:
            pass

def setup(bot):
    bot.add_cog(RSSContent(bot))



