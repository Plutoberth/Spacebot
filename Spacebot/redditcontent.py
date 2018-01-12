import rethinkdb as db
import discord
import asyncio
from io import TextIOWrapper
import sys
import praw
import json

f = open("tokens.json","r")
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
        self.iconurls = {'spacex': 'https://pbs.twimg.com/profile_images/671865418701606912/HECw8AzK.jpg',
                         'blueorigin': 'https://yt3.ggpht.com/-7t1ah-4Rkmg/AAAAAAAAAAI/AAAAAAAAAAA/oCypeGgwHNA/s900-c-k-no-mo-rj-c0xffffff/photo.jpg',
                         'ula': 'https://pbs.twimg.com/profile_images/937905979865300992/o7etOvdP_400x400.jpg',
                         'nasa': 'http://i.imgur.com/tcjKucp.png',
                         'spacexlounge': 'https://pbs.twimg.com/profile_images/671865418701606912/HECw8AzK.jpg',
                         'esa': 'https://www.uncleninja.com/wp-content/uploads/2016/04/ESA_Logo.png',
                         'reddit': 'https://vignette.wikia.nocookie.net/theamazingworldofgumball/images/e/ec/Reddit_Logo.png/revision/latest?cb=20170105232917'}

    async def on_ready(self):
        self.bot.loop.create_task(self.reddit_content())

    async def reddit_content(self):
        while not self.bot.is_closed:
            try:
                reddit = praw.Reddit(client_id=tokens["client_id"], client_secret=tokens["client_secret"],
                                     user_agent='PythonLinux:Spacebot:v1.2.3 (by /u/Cakeofdestiny)')

                subdb = db.table("subdata").get("reddit").run()

                redditlp = db.table("subdata").get("redditlp").run()


                if not redditlp:
                    redditlp = {}

                # loop through all subs
                for s, v in dict(subdb).items():
                    if s == "id":
                        continue
                    # if sub has zero members delete it
                    if v is not None:
                        if len(v) == 0:
                            subdb.pop(s, None)
                            continue
                    else:
                        subdb.pop(s, None)
                        continue
                    # if sub not in lp set lp 0
                    if s not in redditlp:
                        redditlp[s] = 1500000000.0
                    try:
                        post = reddit.subreddit(s).new(limit=1).next()
                    except Exception as e:
                        print("exception in getting post! e: {} \n s: {}".format(e, s))
                        asyncio.sleep(30)
                        continue
                    if not post:
                        subdb.pop(s, None)
                        continue
                    #if post is older or the same than the lp continue
                    if redditlp[s] >= post.created_utc:
                        continue
                    #set lp to current time
                    redditlp[s] = post.created_utc
                    fullmessage = ""
                    # -Construct Embed
                    em = await self.construct_embed(post,fullmessage,s)
                    for channel in v:

                        try:
                            channel_object = self.bot.get_channel(channel)
                        except Exception as e:
                            print(
                                "reddit get channel, exception {}! Details below for debugging: \n\n channel: {}\n post: {}\n".format(
                                    e, channel, post.shortlink))
                            subdb[s] = v.remove(channel)
                            continue
                        if not channel_object:
                            subdb[s] = v.remove(channel)
                        else:
                            try:
                                await self.bot.send_message(channel_object, embed=em)
                            except Exception as e:
                                print(
                                    "reddit post embed, exception {}! Details below for debugging: \n\n channel: {}\n post: {}\n".format(
                                        e, channel, post.shortlink))
                                continue
                       
                redditlp["id"] = "redditlp"
                subdb["id"] = "reddit"

                db.table("subdata").insert(subdb, conflict="replace").run()
                db.table("subdata").insert(redditlp, conflict="replace").run()
                await asyncio.sleep(60)
            except Exception as e:
                print("exception in the entire reddit loop! e: {}".format(e))

    async def construct_embed(self, post, fullmessage, subreddit):
        if len(post.title) > 225:
            title = "[{}]({})".format(post.title, post.shortlink)
            em = discord.Embed(description=fullmessage, title=title, color=discord.Color.blue())
        else:
            fullmessage = "**[{}]({})**\n".format(post.title, post.shortlink)
        em = discord.Embed(description=fullmessage, color=discord.Color.blue())

        # check if it's a self post
        if post.is_self:
            if len(post.selftext) > 1200:
                fullmessage += "\n{}\n [More...]({})".format(post.selftext, post.shortlink)
            else:
                fullmessage += "\n{}".format(post.selftext)

        else:
            # add post link
            fullmessage += "[Post]({})".format(post.shortlink)
            if not post.thumbnail == "default":
                redditformat = post.url[-3:]
                imgformats = ["png", "jpg", "gif"]
                if redditformat in imgformats:
                    em.set_image(url=post.url)
                else:
                    em.set_thumbnail(url=post.thumbnail)

        em.description = fullmessage

        em.set_author(name="New post in r/{}, by {}:"
                      .format(subreddit, post.author.name),
                      icon_url=self.iconurls.get(subreddit,
                                                 self.iconurls["reddit"]))

        return em

def setup(bot):
    bot.add_cog(RedditContent(bot))
