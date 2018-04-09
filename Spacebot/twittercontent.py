import rethinkdb as db
import discord
import asyncio
from io import TextIOWrapper
import sys
import json
import twitter
from time import time

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
        self.TWITTER_ICON = "http://icons.iconarchive.com/icons/uiconstock/socialmedia/512/Twitter-icon.png"

    async def on_ready(self):
        self.bot.loop.create_task(self.twitter_content())

    def delete_account(self, twitter_account):
        db.table("subdata").insert({"id":"twitter", twitter_account:[]}, conflict="update").run()

    async def twitter_content(self):
        while not self.bot.is_closed:
            try:
                twittersubs = db.table("subdata").get("twitter").run()
            except db.ReqlNonExistenceError:
                print("Fatal error, rethinkdb table inaccessible.")
                await asyncio.sleep(60)
                continue

            twitterlp = db.table("subdata").get("twitterlp").run()

            for sub, channels in twittersubs.items():
                if sub == "id":
                    continue

                # If it has no members we just skip it for efficiencies sake
                if len(channels) == 0:
                    continue
                try:
                    lasttweets = twitterapi.GetUserTimeline(screen_name=sub, count=1, include_rts=False, exclude_replies=True)
                    if len(lasttweets) > 0:
                        lasttweet = lasttweets[0]
                    else:
                        self.delete_account(sub)
                        continue

                except (twitter.error.TwitterError, asyncio.TimeoutError) as e:
                    print("Error in twittercontent - getting last tweet! e: {} sub:{}".format(e, sub))
                    # if it failed, we check if it even exists, if it doesn't we remove it
                    try:
                        twitterapi.GetUserTimeline(screen_name=sub, count=1)
                    except twitter.error.TwitterError:
                        #self.delete_account(sub)
                        print("{} removed - not really though".format(sub))
                    continue

                if sub in twitterlp:
                    if type(twitterlp[sub]) == str:
                        print("str matched")
                        db.table("subdata").insert({"id": "twitterlp", sub: lasttweet.created_at_in_seconds}, conflict="update").run()
                        continue
                    elif lasttweet.created_at_in_seconds <= twitterlp[sub]:
                        continue

                db.table("subdata").insert({"id": "twitterlp", sub: lasttweet.created_at_in_seconds}, conflict="update").run()

                em = self.construct_embed(lasttweet, sub)

                for channel in channels[:]:
                    # first we check if we have access to the channel.
                    channel_object = self.bot.get_channel(channel)
                    if channel_object is None:
                        channels.remove(channel)
                        continue
                    # If we do, we check if we can send messages.
                    bot_user = self.bot.user
                    bot_member = channel_object.server.get_member(bot_user.id)
                    if not bot_member.permissions_in(channel_object).send_messages:
                        channels.remove(channel)
                        continue
                    try:
                        await self.bot.send_message(channel_object, embed=em)
                    except discord.Forbidden as e:
                        print("Forbidden in TwitterContent - sending message! e: {}".format(e))
                        pass

                # commit the possible channel changes
                db.table("subdata").insert({"id": "twitter", sub: channels}, conflict="update").run()

            await asyncio.sleep(60)

    def construct_embed(self, tweet, sub):

        em = discord.Embed(
            description="{} \n\n [Tweet Link](https://twitter.com/{}/status/{})".format(tweet.full_text,
                                                                                            sub,
                                                                                            tweet.id_str), color=discord.Color.blue())

        em.set_author(name="New tweet by {}".format(tweet.user.name), icon_url=tweet.user.profile_image_url)

        em.set_footer(text="Twitter - @{}".format(tweet.user.screen_name), icon_url=self.TWITTER_ICON)
        if tweet.media is not None and len(tweet.media) > 0:
            if hasattr(tweet.media[0], 'media_url'):
                em.set_image(url=tweet.media[0].media_url)

        return em




def setup(bot):
    bot.add_cog(TwitterContent(bot))
