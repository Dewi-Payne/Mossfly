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
import logging
import time
from googleapiclient.discovery import build


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


# Logging setuo
logging.basicConfig(
    level=logging.DEBUG,  # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def log_duration(name):
    def decorator(func):
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = await func(*args, **kwargs)
            end = time.perf_counter()
            logger.debug(f"{name} took {end - start:.2f} seconds")
            return result
        return wrapper
    return decorator


# Reading API keys
with open("api_keys.txt", "r+") as file:
    #logger.debug("reading keys")
    keys = file.readlines()
YOUTUBE_API_KEY = keys[3]
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

# ================================== #
# ========== AUDIO SEARCH ========== #
# ================================== #


def search_youtube(query):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=YOUTUBE_API_KEY)

    request = youtube.search().list(
        q=query,
        part="id,snippet",
        maxResults=1,
        type="video"
    )

    response = request.execute()

    if response["items"]:
        video_id = response["items"][0]["id"]["videoId"]
        return f"https://www.youtube.com/watch?v={video_id}"
    else:
        return None


@log_duration("get_audio_source_async")
async def get_audio_source_async(query):
    return await asyncio.to_thread(get_audio_source, query)


def get_audio_source(query):
    start_time = time.perf_counter()

    # Use YouTube API to search if the query is not a direct URL
    if "youtube.com" not in query and "youtu.be" not in query:
        query = search_youtube(query)
        if not query:
            logger.warning("No results found via YouTube API.")
            return None, None

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "quiet": True,
        "noplaylist": True,
        "source_address": "0.0.0.0",
        "nocheckcertificate": True,
        "extract_flat": "in_playlist",  # speeds up playlist queries
        "skip_download": True,
        "cachedir": False,
        "forceurl": True,  # avoids unnecessary metadata parsing
        "forcejson": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            if "entries" in info:
                info = info["entries"][0]
            duration = time.perf_counter() - start_time
            logger.debug(f"Audio source resolved in {duration:.2f} seconds")
            return info["url"], info.get("title", "Unknown Title")
    except Exception as e:
        logger.warning(f"yt-dlp extraction failed: {e}")
        return None, None


def create_ffmpeg_source(url):
    # Function that gets the audio stream for the bot to play
    start_time = time.perf_counter()
    #logger.debug("creating ffmeg source...")
    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn -acodec libopus -b:a 96k -f opus"
    }
    duration = time.perf_counter() - start_time
    logger.debug(f"Audio source created in {duration:.2f} seconds")
    return FFmpegOpusAudio(url, **ffmpeg_options)


# ================================= #
# ========= PLAYER CONFIG ========= #
# ================================= #


@log_duration("play_next")
async def play_next(ctx):
    #logger.debug("play_next triggered...")
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
    if queues[guild_id]:
        # If we have a non-empty queue, we remove the song and
        # update the source to the new song (i.e. the next url)
        url, title, user_id = queues[guild_id].pop(0)
        now_playing[guild_id] = (title, user_id)
        source = create_ffmpeg_source(url)
        vc = ctx.voice_client
        vc.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx),
                                                                         bot.loop))  # What does this do? We may never know.
        await ctx.send(f"Now playing: **{title}**")

    else:  # If the queue *is* empty, DC
        logger.info("queue empty, disconnecting.")
        #now_playing.pop(guild_id, None)
        #await ctx.voice_client.disconnect()


# =========================================== #
# ========== BOT EVENTS + COMMANDS ========== #
# =========================================== #


@log_duration("on_ready")
@bot.event
async def on_ready():
    logger.info("on_ready")
    # Login event
    print(f"me {bot.user}")


@log_duration("pause")
@bot.command()
async def pause(ctx):
    #logger.info("pause command read")
    if ctx.voice_client:
        if not ctx.voice_client.is_playing():
            await ctx.send("Nothing is playing")
        elif ctx.voice_client.is_paused():
            await ctx.send("Already paused")
        else:
            ctx.voice_client.pause()
            logger.info("paused")
            await ctx.send("Paused")


@log_duration("resume")
@bot.command()
async def resume(ctx):
    logger.info("resume command read")
    if ctx.voice_client:
        ctx.voice_client.resume()
        logger.info("resumed")
        await ctx.send("Resuming...")


@log_duration("queuetop")
@bot.command()
async def queuetop(ctx, *, query):
    logger.info("queuetop command read")
    if not ctx.voice_client:
        await ctx.invoke(join)

    url, title = get_audio_source_async(query)
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
        await play_next(ctx)


@log_duration("topqueue")
@bot.command()
async def topqueue(*args, **kwargs):
    logger.info("topqueue command read")
    await queuetop(*args, **kwargs)


@log_duration("volume")
@bot.command()
async def volume(ctx, *, vol):
    logger.info("volume command read")
    if ctx.voice_client.is_playing():
        await ctx.voice_client.volume(int(vol))


@log_duration("join")
@bot.command()
async def join(ctx):
    logger.info("join command read")
    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
    else:
        await ctx.send("You're not in a voice channel >:(")


@log_duration("play")
@bot.command()
async def play(ctx, *, query):
    #logger.info("play command read")
    if not ctx.voice_client:
        await ctx.invoke(join)

    url, title = await get_audio_source_async(query)
    if not url:
        await ctx.send("Err: Audio source not found.")
        return

    await ctx.send(f"Queuing...: {title}")

    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []

    queues[guild_id].append((url, title, ctx.author.id))

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


@bot.command()
async def skip(ctx):
    #logger.info("skip command read")
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Skipping...")


@log_duration("stop")
@bot.command()
async def stop(ctx):
    #logger.info("stop command read")
    if ctx.voice_client:
        queues[ctx.guild.id] = []
        await ctx.voice_client.disconnect()
        await ctx.send("Stopping...")


@log_duration("shuffle")
@bot.command()
async def shuffle(ctx):
    #logger.info("shuffle command read")
    if ctx.voice_client and ctx.voice_client.is_playing() and len(queues[ctx.guild.id]) > 1:
        random.shuffle(queues[ctx.guild.id])
        await ctx.send("Shuffling queue.")


@log_duration("deletequeue")
@bot.command()
async def deletequeue(ctx):
    #logger.info("deletequeue command read")
    if ctx.voice_client and ctx.voice_client.is_playing():
        queues[ctx.guild.id] = []
        await ctx.send("Deleting queue.")


@log_duration("undo")
@bot.command()
async def undo(ctx):
    logger.info("undo command read")
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
    #logger.info("queue command read")
    start_time = time.perf_counter()
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

    duration = time.perf_counter() - start_time
    logger.debug(f"Queue took {duration:.2f} seconds")


@log_duration("recommend")
@bot.command()
async def recommend(ctx, *, query):
    await ctx.send("Finding recommended songs...")
    guild_id = ctx.guild.id
    if guild_id not in queues:
        queues[guild_id] = []
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
    if not ctx.voice_client:
        await ctx.invoke(join)

    messages = []
    for track in similar_tracks:
        search_query = f"{track['name']} by {track['artist']['name']}"
        url, title = await get_audio_source_async(search_query)
        queues[guild_id].append((url, title, ctx.author.id))
        await ctx.send(f"Queueing: {title}")
        if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
            await play_next(ctx)



# LAST.FM API keys for music recommending
last_key1 = keys[0]
last_secret = keys[1]


# Runs the bot when this file is running
bot.run(keys[2])
logger.info("Bot running...")
