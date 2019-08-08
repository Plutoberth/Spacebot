import rethinkdb as db
import discord
import asyncio
from io import TextIOWrapper
import sys
import praw
import prawcore
import json
from .constants import *

f = open("tokens.json", "r")
tokens = json.loads(f.read())["reddit"]
f.close()

# Adds error logging to Linux journalctl
sys.stdout = TextIOWrapper(sys.stdout.detach(),
                           encoding=sys.stdout.encoding,
                           errors="replace",
                           line_buffering=True)

db.connect("localhost", 28015, 'spacebot').repl()


class RedditContent:
    def __init__(self, bot):
        self.bot = bot

        self.reddit = praw.Reddit(client_id=tokens["client_id"], client_secret=tokens["client_secret"],
                                  user_agent='PythonLinux:Spacebot:v1.2.3 (by /u/Cakeofdestiny)')

    async def on_ready(self):
        self.bot.loop.create_task(self.reddit_content())

    async def fetch_single_sub(self, subreddit: str, limit: int = 1):
        """
        Fetch a single sub and return the results. This is mainly done for async granularity as a quick fix to the
        long reddit_content loop.
        :param subreddit: The subreddit to fetch.
        :param limit: Limit of posts.
        :return: Posts for the subreddit
        """
        return self.reddit.subreddit(subreddit).new(limit=limit).next()

    async def reddit_content(self):
        while not self.bot.is_closed:
            subdb = db.table("subdata").get("reddit").run()

            redditlp = db.table("subdata").get("redditlp").run()

            if not redditlp:
                redditlp = {}

            # loop through all subs
            for subreddit, subscribers in dict(subdb).items():
                if subreddit == "id":
                    continue
                # if sub has zero members delete it
                if subscribers is not None:
                    if len(subscribers) == 0:
                        subdb.pop(subreddit, None)
                        continue
                else:
                    subdb.pop(subreddit, None)
                    continue

                # if sub not in lp set lp 0
                if subreddit not in redditlp:
                    redditlp[subreddit] = 0
                try:
                    post = await self.fetch_single_sub(subreddit)
                except prawcore.exceptions.NotFound:
                    print("Removing sub {}".format(subreddit))
                    subdb.pop(subreddit, None)
                except Exception as e:
                    print("exception in getting post! e: {} \n subreddit: {}".format(e, subreddit))
                    await asyncio.sleep(30)  # Reddit might be offline or blocking the bot. Sleep for a while.
                    continue

                if not post:
                    subdb.pop(subreddit, None)
                    continue

                # if post isn't older than the redditlp post continue
                if not post.created_utc > redditlp[subreddit]:
                    continue
                # set lp to current time
                redditlp[subreddit] = post.created_utc
                # -Construct Embed
                em = self.construct_embed(post, subreddit)
                for channel in subscribers[:]:
                    try:
                        channel_object = self.bot.get_channel(channel)
                    except Exception as e:
                        print("reddit get channel, exception {}! Details below for debugging: \n\n "
                              "channel: {}\n post: {}\n".format(e, channel, post.shortlink))
                        subdb[subreddit].remove(channel)
                        continue
                    if not channel_object:
                        subdb[subreddit].remove(channel)
                    else:
                        try:
                            await self.bot.send_message(channel_object, embed=em)
                        except discord.Forbidden:
                            print("Forbidden - Removing channel...")
                            subdb[subreddit].remove(channel)
                        except discord.HTTPException as e:
                            print("discord HTTPException in RedditContent - sending message! e: {} "
                                  "\n channel: {} \n post:{}"
                                  .format(e, channel, post.shortlink))

            redditlp["id"] = "redditlp"
            subdb["id"] = "reddit"

            db.table("subdata").insert(subdb, conflict="replace").run()
            db.table("subdata").insert(redditlp, conflict="replace").run()
            await asyncio.sleep(60)

    def construct_embed(self, post, subreddit: str) -> discord.Embed:
        """
        Constructs an embed for a reddit post based on a PRAW post object.
        :param post: A praw post object.
        :param subreddit: The name of the subreddit
        :return: A discord embed.
        """
        em = discord.Embed(color=discord.Color.blue())

        desc = ""
        if len(post.title) > 225:
            title = "[{}]({})".format(post.title, post.shortlink)
            em.title = title
        else:
            desc = "**[{}]({})**\n".format(post.title, post.shortlink)

        # check if it's a self post
        if post.is_self:
            if len(post.selftext) < 1200:
                desc += "\n{}".format(post.selftext)  # If it's short enough, post the full text
            else:
                desc += "\n{}\n [More...]({})".format(post.selftext, post.shortlink)  # Otherwise truncate

        else:
            # add post link
            desc += "[Post link]({})".format(post.url)
            if not post.thumbnail == "default":
                image_format = post.url[-3:]
                if image_format in ["png", "jpg", "gif"]:
                    em.set_image(url=post.url)
                elif post.thumbnail != "default":
                    em.set_thumbnail(url=post.thumbnail)

        em.description = desc

        em.set_author(name="New post in r/{}, by {}:"
                      .format(subreddit, post.author.name),
                      icon_url=ICON_URLS.get(subreddit,
                                             ICON_URLS["reddit"]))

        return em


def setup(bot):
    bot.add_cog(RedditContent(bot))
