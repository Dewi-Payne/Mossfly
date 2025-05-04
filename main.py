import discord
from discord.ext import commands
from discord import FFmpegOpusAudio
import asyncio
import yt_dlp
import copy
import random
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
import json
import requests


# MuzakBot ~ D. Payne 2025
# TODO - user guide
# TODO - queue saving / loading !!
#   Store as json or sqlite table?
# TODO - persistent queues !!
# TODO - improve queue command
# TODO - volume control fix


# Reads user messages with discord.py module
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# Global variables (eew) for the queue and playing song.
queues = {}
now_playing = {}


with open("api_keys.txt", "r+") as file:
    keys = file.readlines()


# ======================== #
# ===== AUDIO SEARCH ===== #
# ======================== #


def get_audio_source(query):
    # Search/Audio playback using the lib yt_dlp
    ydl_opts = {
        "format": "bestaudio",
        "noplaylist": True,
        "quiet": True,
        "default_search": "ytsearch",
        "source_address": "0.0.0.0"

    }

    # Safety check in case it's a lik
    if "youtube.com" in query or "youtu.be" in query:
        ydl_opts['default_search'] = 'ytsearch'
    elif "soundcloud.com" in query:
        ydl_opts['default_search'] = 'scloudsearch'

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(query, download=False)  # Just stream it (I think it's usually used for downloading)
            if "entries" in info:
                info = info["entries"][0]  # First search choice
            return info["url"], info["title"]
        except Exception as e:
            print(f"Search Error: {e}")
            return None, None


def create_ffmpeg_source(url):
    # Function that gets the audio stream for the bot to play
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -acodec libopus -b:a 96k -f opus"
    }
    return FFmpegOpusAudio(url, **ffmpeg_options)


# ======================= #
# ==== PLAYER CONFIG ==== #
# ======================= #


async def play_next(ctx, guild_id):
    # Plays the next song

    # ctx is some object that the python library uses to pass data.
    # We can do things like ctx.send to send chat messages using the bot, or ctx.invoke to run another func
    # guild_id is the server's ID, used to get the queue; the queues are stored per-server.

    if queues[guild_id]:
        # If we have a non-empty queue, we remove the song and
        # update the source to the new song (i.e. the next url)
        url, title, user_id = queues[guild_id].pop(0)
        now_playing[guild_id] = (title, user_id)
        source = create_ffmpeg_source(url)
        vc = ctx.voice_client
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, guild_id), bot.loop))  # What does this do? We may never know.
        await ctx.send(f"Now playing: **{title}**")

    else:  # If the queue *is* empty, DC
        await asyncio.sleep(60)  # Wait for 60 seconds

        # Check again in case something was queued during the delay
        if not queues[guild_id]:
            now_playing.pop(guild_id, None)
            await ctx.voice_client.disconnect()


# ================================= #
# ===== BOT EVENTS + COMMANDS ===== #
# ================================= #

@bot.event
async def on_ready():
    # Login event
    print(f"me {bot.user}")


@bot.command()
async def pause(ctx):
    if ctx.voice_client:
        if not ctx.voice_client.is_playing():
            await ctx.send("Nothing is playing")
        elif ctx.voice_client.is_paused():
            await ctx.send("Already paused")
        else:
            ctx.voice_client.pause()
            await ctx.send("Paused")


@bot.command()
async def resume(ctx):
    if ctx.voice_client:
        ctx.voice_client.resume()
        await ctx.send("Resuming...")


@bot.command()
async def queuetop(ctx, *, query):
    if not ctx.voice_client:
        await ctx.invoke(join)

    url, title = get_audio_source(query)
    if not url:
        await ctx.send("Err: Audio source not found.")
        return

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    # Flips the queue and adds a song, then un-flips it to add the song to the start.
    _temp_queue = copy.deepcopy(queues[guild_id])
    _temp_queue.reverse()
    _temp_queue.append((url, title, ctx.author.id))
    _temp_queue.reverse()
    queues[guild_id] = _temp_queue

    await ctx.send(f"Putting at front of queue...: {title}")

    if not ctx.voice_client.is_playing():
        await play_next(ctx, guild_id)


@bot.command()
async def topqueue(*args, **kwargs):
    await queuetop(*args, **kwargs)


@bot.command()
async def volume(ctx, *, vol):
    if ctx.voice_client.is_playing():
        await ctx.voice_client.volume(int(vol))


@bot.command()
async def join(ctx):
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.send("You're not in a voice channel >:(")


@bot.command()
async def play(ctx, *, query):
    if not ctx.voice_client:
        await ctx.invoke(join)

    url, title = get_audio_source(query)
    if not url:
        await ctx.send("Err: Audio source not found.")
        return

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append((url, title, ctx.author.id))
    await ctx.send(f"Queuing...: {title}")

    if not ctx.voice_client.is_playing():
        await play_next(ctx, guild_id)


@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipping...")


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        queues[ctx.guild.id] = []
        await ctx.voice_client.disconnect()
        await ctx.send("Stopping...")


@bot.command()
async def shuffle(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing() and len(queues[ctx.guild.id]) > 1:
        random.shuffle(queues[ctx.guild.id])
        await ctx.send("Shuffling queue.")


@bot.command()
async def deletequeue(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        queues[ctx.guild.id] = []
        await ctx.send("Deleting queue.")


@bot.command()
async def undo(ctx):
    guild_id = ctx.guild.id
    if guild_id not in queues or not queues[guild_id]:
        await ctx.send("There's nothing in the queue.")
        return

    # Find the most recent song queued by this user, from the end of the queue
    for i in reversed(range(len(queues[guild_id]))):
        url, title, user_id = queues[guild_id][i]
        if user_id == ctx.author.id:
            removed = queues[guild_id].pop(i)
            await ctx.send(f"Removed {title} from the queue.")
            return
    await ctx.send("You have no songs in the queue to undo.")


@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    queue_list = queues.get(guild_id, [])
    now = now_playing.get(guild_id)

    if not now and not queue_list:
        await ctx.send("The queue is currently empty.")
        return

    description = ""

    if now:
        user = await bot.fetch_user(now[1])
        description += f"🎵 **Now Playing**: {now[0]} (queued by {user.name})\n\n"

    if queue_list:
        description += "**Up Next:**\n"
        for i, (url, title, user_id) in enumerate(queue_list[:10], start=1):
            user = await bot.fetch_user(user_id)
            description += f"{i}.  {title}    [{user.name}]\n"

        if len(queue_list) > 10:
            description += f"\n+ {len(queue_list) - 10} more." 

    await ctx.send(description)



"""@bot.command()
async def save(ctx, *, file_name):
    url, title, user_id = queues[ctx.guild_id]
    with open("playlists.json", "w") as f:
        f.writelines(str(url, title, user_id))
        f.close()


@bot.command()
async def load(ctx, *, file_name):
    url, title, user_id = queues[ctx.guild_id]
    with open("playlists.json", "w") as f:
        f.writelines(str(url, title, user_id))
        f.close()
"""


@bot.command()
async def recommend(ctx, *, query):
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    await ctx.send("Finding recommended songs...")
    data = query.split("-")
    data = [x.strip() for x in data]
    if len(data) != 2:
        await ctx.send("Use the format: 'Artist - Song' to use this command.")
        return

    response = requests.get("http://ws.audioscrobbler.com/2.0/", params={
        "method": "track.getsimilar",
        "artist": data[0],
        "track": data[1],
        "api_key": last_key1,
        "format": "json",
        "limit": 5
    })

    if response.status_code != 200:
        await ctx.send("Failed to fetch recommendations from Last.fm.")
        return

    results = response.json()
    similar_tracks = results.get("similartracks", {}).get("track", [])

    if not similar_tracks:
        await ctx.send("No similar tracks found :(")
        return

    messages = []
    for track in similar_tracks:
        await ctx.send(search_query)
        search_query = f"{track['name']} by {track['artist']['name']}"
        url, title = get_audio_source(search_query)
        queues[guild_id].append((url, title, ctx.author.id))


# LAST.FM API keys for music recommending
last_key1 = keys[0]
last_secret = keys[1]


# Runs the bot when this file is running
bot.run(keys[2])

