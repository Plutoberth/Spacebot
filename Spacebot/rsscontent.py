import rethinkdb as db
import discord
import asyncio
import json
import sys
import aiohttp
import async_timeout
import feedparser
from io import TextIOWrapper
import re

f = open("tokens.json", "r")
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
        self.session = aiohttp.ClientSession(loop=self.bot.loop)
        self.RSS_ICON = "http://icons.iconarchive.com/icons/sicons/basic-round-social/512/rss-icon.png"
        self.html_pattern = re.compile(r'<[^>]+>')

    async def on_ready(self):
        self.bot.loop.create_task(self.rss_content())

    async def fetch(self, url):
        with async_timeout.timeout(90):
            async with self.session.get(url) as response:
                try:
                    return await response.text()
                except Exception as e:
                    print("Exception in RSS Fetch for {}, e: {}".format(url, e))

    async def get_rss_feed(self, rss_link):
        feed_string = await self.fetch(rss_link)
        feed = feedparser.parse(feed_string)
        return feed

    @staticmethod
    def verify_rss_feed(feed):
        return len(feed['entries']) > 0

    @staticmethod
    def remove_rss_feed(rss_link):
        db.table("subdata").insert({"id": "rss", rss_link: []}, conflict="update").run()

    async def rss_content(self):
        while not self.bot.is_closed:
            try:
                complete_rss_db = db.table("subdata").get("rss").run()
            except db.ReqlNonExistenceError:
                print("Fatal error, rethinkdb table inaccessible.")
                await asyncio.sleep(60)
                continue

            rss_lp = db.table("subdata").get("rsslp").run()
            if not rss_lp:
                rss_lp = {}

            for rss_link, rss_subs in complete_rss_db.items():
                if rss_link == "id":
                    continue

                feed = await self.get_rss_feed(rss_link)
                if not self.verify_rss_feed(feed) or len(rss_subs) == 0:
                    self.remove_rss_feed(rss_link)
                    await asyncio.sleep(60)
                    continue

                entry = feed['entries'][0]
                feed_data = feed['feed']

                feed_id = entry.get('id', None)

                if not feed_id:
                    continue

                if rss_link in rss_lp:
                    if rss_lp[rss_link] == feed_id:
                        continue

                db.table("subdata").insert({"id": "rsslp", rss_link: feed_id}, conflict="update").run()

                em = self.construct_embed(feed_data, entry, rss_link)

                for channel in rss_subs[:]:
                    # first we check if we have access to the channel.
                    channel_object = self.bot.get_channel(channel)
                    if channel_object is None:
                        rss_subs.remove(channel)
                        continue
                    # If we do, we check if we can send messages.
                    bot_user = self.bot.user
                    bot_member = channel_object.server.get_member(bot_user.id)
                    if not bot_member.permissions_in(channel_object).send_messages:
                        rss_subs.remove(channel)
                        continue
                    try:
                        await self.bot.send_message(channel_object, embed=em)
                    except discord.Forbidden as e:
                        print("Forbidden in RSSContent - sending message! e: {}".format(e))
                        pass

                    # commit the possible channel changes
                    db.table("subdata").insert({"id": "rss", rss_link: rss_subs}, conflict="update").run()

            await asyncio.sleep(60)

        pass

    def construct_embed(self, feed_data, entry, rss_link):

        summary_without_html = self.html_pattern.sub('', entry['title'])

        em = discord.Embed(
            description="{} \n\n [Link]({})".format(summary_without_html,entry['link']), color=discord.Color.blue())

        em.set_author(name="RSS Feed - {}".format(feed_data['title']))

        em.set_footer(text="RSS Feed Link - {}".format(rss_link), icon_url=self.RSS_ICON)

        return em


def setup(bot):
    bot.add_cog(RSSContent(bot))



