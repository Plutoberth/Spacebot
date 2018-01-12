import rethinkdb as db
import discord
import asyncio
from io import TextIOWrapper
import sys
import json
import twitter

f = open("tokens.json", "r")
tokens = json.loads(f.read())
f.close()

# Adds error logging to Linux journalctl
sys.stdout = TextIOWrapper(sys.stdout.detach(),
                           encoding=sys.stdout.encoding,
                           errors="replace",
                           line_buffering=True)

twitterapi = twitter.Api(consumer_key=tokens["twitter"]["consumer_key"],
                         consumer_secret=tokens["twitter"]["consumer_secret"],
                         access_token_key=tokens["twitter"]["access_token_key"],
                         access_token_secret=tokens["twitter"]["access_token_secret"],
                         tweet_mode='extended')

db.connect("localhost", 28015, 'spacebot').repl()


class TwitterContent:
    def __init__(self, bot):
        self.bot = bot

    async def on_ready(self):
        self.bot.loop.create_task(self.twitter_content())

    async def twitter_content(self):
        while not self.bot.is_closed:
            twittersubs = {}
            try:
                twittersubs = db.table("subdata").get("twitter").run()
            except db.ReqlNonExistenceError:
                print("Fatal error, rethinkdb table inaccessible.")
                pass

            twitterlp = {}
            twitterlp = db.table("subdata").get("twitterlp").run()

            for sub, channels in twittersubs.items():
                if sub == "id":
                    continue

                # If it has no members we just skip it for efficiencies sake
                if len(channels) == 0:
                    continue
                #print("sub: {} channels {}".format(sub,channels))
                try:
                    lasttweet = twitterapi.GetUserTimeline(screen_name=sub, count=1, include_rts=False, exclude_replies=True)[0]

                except (IndexError, twitter.error.TwitterError, asyncio.TimeoutError) as e:
                    print("Error in twittercontent - getting last tweet! e: {} sub:{}".format(e, sub))
                    # if it failed, we check if it even exists, if it doesn't we remove it
                    try:
                        twitterapi.GetUserTimeline(screen_name=sub, count=1)
                    except twitter.error.TwitterError:
                        # We can just insert an empty list for easy removal.
                        db.table("subdata").insert({"id": "twitter", sub: []}, conflict="update").run()
                        print("{} removed".format(sub))
                        return
                    await asyncio.sleep(60)
                    continue

                if sub in twitterlp:
                    if lasttweet.full_text == twitterlp[sub]:
                        #print("lasttweet: {} twitterlp: {}".format(lasttweet.full_text, twitterlp[sub]))
                        #print("skipped cause of twitterlp dupe")
                        continue

                db.table("subdata").insert({"id": "twitterlp", sub: lasttweet.full_text}, conflict="update").run()

                em = await self.construct_embed(lasttweet, sub)
                # incase we do any changes
                fullchannels = channels
                for channel in fullchannels:
                    # first we check if we have access to the channel.
                    channel = self.bot.get_channel(channel)
                    if not channel:
                        channels.remove(channel)
                        continue
                    # If we do, we check if we can send messages.
                    bot_user = self.bot.user
                    bot_member = channel.server.get_member(bot_user.id)
                    if not bot_member.permissions_in(channel).send_messages:
                        channels.remove(channel)
                        continue
                    try:

                        await self.bot.send_message(self.bot.get_channel(channel), embed=em)
                    except Exception as e:
                        print("Error in twittercontent - sending message! e: {}".format(e))
                        pass

            await asyncio.sleep(60)

    async def construct_embed(self, tweet, sub):

        em = discord.Embed(
            description="{} \n\n [Tweet Link](https://twitter.com/{}/status/{})".format(tweet.full_text,
                                                                                            sub,
                                                                                            tweet.id_str),
            title="New tweet by {}:".format(tweet.user.name), color=discord.Color.blue())

        if tweet.media is not None and len(tweet.media) > 0:
            if hasattr(tweet.media[0], 'media_url'):
                em.set_image(url=tweet.media[0].media_url)

        return em




def setup(bot):
    bot.add_cog(TwitterContent(bot))
