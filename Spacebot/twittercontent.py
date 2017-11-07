import rethinkdb as db
import discord
import asyncio
from io import TextIOWrapper
import sys
import json
import twitter

f = open("tokens.json","r")
tokens = json.loads(f.read())
f.close()

# Unbuffered
sys.stdout = TextIOWrapper(sys.stdout.detach(),
                           encoding=sys.stdout.encoding,
                           errors="replace",
                           line_buffering=True)

twitterapi = twitter.Api(consumer_key=tokens["twitter"]["consumer_key"],
                         consumer_secret=tokens["twitter"]["consumer_secret"],
                         access_token_key=tokens["twitter"]["access_token_key"],
                         access_token_secret=tokens["twitter"]["access_token_secret"])

db.connect("localhost", 28015, 'spacebot').repl()

class TwitterContent:
    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):
        self.bot.loop.create_task(self.twitterContent())

    async def twitterContent(self):
        while not self.bot.is_closed:
            try:
                twittersubs = db.table("subdata").get("twitter").run()
            except db.ReqlNonExistenceError:
                print("Fatal error, rethinkdb table inaccessible.")
                pass

            twitterlp = db.table("subdata").get("twitterlp").run()
            if not twittersubs:
                twittersubs = {}
            if not twitterlp:
                twitterlp = {}

            for sub, channels in twittersubs.items():
                if sub == "id":
                    continue
                #print(sub)
                try:
                    lasttweet = twitterapi.GetUserTimeline(screen_name=sub, count=1, include_rts=False, exclude_replies=True)[0]
                except (IndexError, twitter.error.TwitterError):
                    continue
                if sub in twitterlp:
                    if lasttweet.text == twitterlp[sub]:
                        continue

                db.table("subdata").insert({"id": "twitterlp", sub: lasttweet.text}, conflict="update").run()


                em = discord.Embed(
                    description="**{}** \n\n [Tweet Link](https://twitter.com/{}/status/{})".format(lasttweet.text,
                                                                                                    sub,
                                                                                                    lasttweet.id_str),
                    title="New tweet by {}:".format(lasttweet.user.name), color=discord.Color.blue())

                for channel in channels:
                    try:
                        await self.bot.send_message(self.bot.get_channel(channel), embed=em)
                    except discord.errors.InvalidArgument:
                        pass

            await asyncio.sleep(60)


def setup(bot):
    bot.add_cog(TwitterContent(bot))
