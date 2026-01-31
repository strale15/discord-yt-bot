import discord
from discord.ext import commands
from discord.ui import Button, View
import yt_dlp
import asyncio
import os
import shutil
from dotenv import load_dotenv

# Check for FFmpeg
def check_ffmpeg():
    """Check if FFmpeg is available"""
    # Check in PATH
    if shutil.which("ffmpeg"):
        return True
    
    # Check in current directory
    if os.path.exists("ffmpeg.exe"):
        return True
    
    return False

if not check_ffmpeg():
    print("=" * 60)
    print("ERROR: FFmpeg not found!")
    print("=" * 60)
    print()
    print("FFmpeg is required for this bot to work.")
    print()
    print("Quick fixes:")
    print("1. Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/")
    print("2. Extract and copy ffmpeg.exe to this folder")
    print("   OR")
    print("3. Add FFmpeg to your system PATH")
    print()
    print("See FFMPEG_INSTALL.md for detailed instructions.")
    print("=" * 60)
    input("Press Enter to exit...")
    exit(1)

# Bot setup with intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix='/', intents=intents)

# Optimized yt-dlp options for Raspberry Pi Zero 2W
# Lower quality = less CPU usage and bandwidth
ytdl_format_options = {
    # Optimized format selection for low-power devices
    # Prefer opus (most efficient) > m4a > lower quality audio
    'format': 'bestaudio[ext=opus]/bestaudio[ext=m4a]/worstaudio/bestaudio',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
    'prefer_ffmpeg': True,
    'keepvideo': False,
    # Lighter postprocessing for Pi Zero
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'opus',  # Opus is lighter than mp3
        'preferredquality': '96',   # Lower quality = less CPU (was default ~192)
    }],
    # Additional optimizations
    'concurrent_fragment_downloads': 1,  # Reduce parallel downloads
    'buffersize': 4096,  # Smaller buffer
    'http_chunk_size': 1048576,  # 1MB chunks (smaller for Pi)
}

# Separate config for playlist handling
ytdl_playlist_options = {
    **ytdl_format_options,
    'noplaylist': False,
    'extract_flat': True,  # Don't download metadata for all videos at once
    'lazy_playlist': True,  # Process playlist items one at a time
}

# Optimized FFmpeg options for Raspberry Pi Zero 2W
ffmpeg_options = {
    'options': '-vn -b:a 96k -ac 2',  # 96kbps, stereo (lower bitrate = less CPU)
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)
ytdl_playlist = yt_dlp.YoutubeDL(ytdl_playlist_options)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            # Take first item from a playlist
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)

# Queue system and playback state
queues = {}
loop_state = {}
history = {}

def get_queue(guild_id):
    if guild_id not in queues:
        queues[guild_id] = []
    return queues[guild_id]

def get_loop_state(guild_id):
    return loop_state.get(guild_id, False)

def set_loop_state(guild_id, state):
    loop_state[guild_id] = state

def get_history(guild_id):
    if guild_id not in history:
        history[guild_id] = []
    return history[guild_id]

def is_youtube_playlist(url):
    """Check if URL is a YouTube playlist (not a single video from a playlist)"""
    if 'list=' not in url or 'youtube.com' not in url:
        return False
    
    if 'v=' in url or '/watch?' in url:
        return False
    
    if '/playlist?' in url:
        return True
    
    return False

async def extract_playlist_urls(playlist_url):
    """Extract all video URLs from a YouTube playlist (optimized for Pi)"""
    loop = asyncio.get_event_loop()
    
    try:
        # Use lazy extraction to reduce memory usage
        data = await loop.run_in_executor(
            None, 
            lambda: ytdl_playlist.extract_info(playlist_url, download=False)
        )
        
        if 'entries' in data:
            urls = []
            # Limit playlist size to prevent overwhelming the Pi
            max_songs = 50  # Safety limit for Pi Zero
            for i, entry in enumerate(data['entries']):
                if i >= max_songs:
                    break
                if entry:
                    url = entry.get('url') or entry.get('webpage_url') or f"https://www.youtube.com/watch?v={entry.get('id')}"
                    urls.append(url)
            return urls, data.get('title', 'Unknown Playlist')
    except Exception as e:
        print(f"Playlist extraction error: {e}")
    
    return [], None

# Music Control Buttons
class MusicControlView(View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.guild_id = guild_id
    
    @discord.ui.button(label="⏮️ Prev", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: Button):
        voice_client = interaction.guild.voice_client
        song_history = get_history(self.guild_id)
        
        if not voice_client:
            await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)
            return
        
        if len(song_history) < 2:
            await interaction.response.send_message("No previous song!", ephemeral=True)
            return
        
        song_history.pop()
        prev_url = song_history.pop()
        
        queue = get_queue(self.guild_id)
        if voice_client.is_playing():
            voice_client.stop()
        
        queue.insert(0, prev_url)
        voice_client.stop()
        await interaction.response.send_message("⏮️ Playing previous song...", ephemeral=True)
    
    @discord.ui.button(label="⏭️ Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: discord.Interaction, button: Button):
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_playing():
            voice_client.stop()
            await interaction.response.send_message("⏭️ Skipped to next song", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
    
    @discord.ui.button(label="⏸️ Pause", style=discord.ButtonStyle.primary)
    async def pause_button(self, interaction: discord.Interaction, button: Button):
        voice_client = interaction.guild.voice_client
        
        if voice_client and voice_client.is_playing():
            voice_client.pause()
            button.label = "▶️ Resume"
            button.style = discord.ButtonStyle.success
            await interaction.response.edit_message(view=self)
        elif voice_client and voice_client.is_paused():
            voice_client.resume()
            button.label = "⏸️ Pause"
            button.style = discord.ButtonStyle.primary
            await interaction.response.edit_message(view=self)
        else:
            await interaction.response.send_message("Nothing is playing!", ephemeral=True)
    
    @discord.ui.button(label="🔁 Loop: Off", style=discord.ButtonStyle.secondary)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_state = get_loop_state(self.guild_id)
        new_state = not current_state
        set_loop_state(self.guild_id, new_state)
        
        if new_state:
            button.label = "🔁 Loop: On"
            button.style = discord.ButtonStyle.success
        else:
            button.label = "🔁 Loop: Off"
            button.style = discord.ButtonStyle.secondary
        
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(label="⏹️ Stop", style=discord.ButtonStyle.danger)
    async def stop_button(self, interaction: discord.Interaction, button: Button):
        voice_client = interaction.guild.voice_client
        
        if voice_client:
            queue = get_queue(self.guild_id)
            queue.clear()
            set_loop_state(self.guild_id, False)
            voice_client.stop()
            await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)
        else:
            await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    print(f'Bot is in {len(bot.guilds)} guilds')
    print('Optimized for Raspberry Pi Zero 2W - Using 96kbps audio')
    
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

@bot.tree.command(name="play", description="Play a song from YouTube")
async def play(interaction: discord.Interaction, url: str):
    """Play a song from a YouTube URL"""
    
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel to use this command!", ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Handle YouTube playlists
        if is_youtube_playlist(url):
            await interaction.followup.send("📝 Detected playlist! Extracting songs...", ephemeral=True)
            playlist_urls, playlist_name = await extract_playlist_urls(url)
            
            if not playlist_urls:
                await interaction.followup.send("❌ Could not extract playlist!", ephemeral=True)
                return
            
            queue = get_queue(interaction.guild.id)
            
            for playlist_url in playlist_urls:
                queue.append(playlist_url)
            
            # Show warning if playlist was limited
            if len(playlist_urls) >= 50:
                await interaction.followup.send(
                    f"✅ Added **{len(playlist_urls)}** songs (max 50 for Pi performance)\nPlaylist: **{playlist_name}**", 
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    f"✅ Added **{len(playlist_urls)}** songs from playlist: **{playlist_name}**", 
                    ephemeral=True
                )
            
            voice_client = interaction.guild.voice_client
            if voice_client is None:
                voice_client = await channel.connect()
            elif voice_client.channel != channel:
                await voice_client.move_to(channel)
            
            if not voice_client.is_playing():
                first_url = queue.pop(0)
                player = await YTDLSource.from_url(first_url, loop=bot.loop, stream=True)
                
                song_history = get_history(interaction.guild.id)
                song_history.append(first_url)
                
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next(interaction.guild.id, interaction.channel), bot.loop))
                
                view = MusicControlView(interaction.guild.id)
                await interaction.channel.send(f'Now playing: **{player.title}**', view=view)
            
            return
        
        # Connect to voice channel
        if interaction.guild.voice_client is None:
            voice_client = await channel.connect()
        else:
            voice_client = interaction.guild.voice_client
            if voice_client.channel != channel:
                await voice_client.move_to(channel)
        
        # If already playing, add to queue
        if voice_client.is_playing() or voice_client.is_paused():
            queue = get_queue(interaction.guild.id)
            queue.append(url)
            await interaction.followup.send(f"Added to queue! Position: {len(queue)}", ephemeral=True)
            return
        
        # Play the audio
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        
        song_history = get_history(interaction.guild.id)
        song_history.append(url)
        
        voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next(interaction.guild.id, interaction.channel), bot.loop))
        
        view = MusicControlView(interaction.guild.id)
        await interaction.channel.send(f'Now playing: **{player.title}**', view=view)
        await interaction.followup.send(f'Started playing: **{player.title}**', ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in play command: {e}")

@bot.tree.command(name="play-now", description="Skip queue and play a song immediately")
async def play_now(interaction: discord.Interaction, url: str):
    """Play a song immediately, skipping the queue"""
    
    if not interaction.user.voice:
        await interaction.response.send_message("You need to be in a voice channel to use this command!", ephemeral=True)
        return
    
    channel = interaction.user.voice.channel
    await interaction.response.defer(ephemeral=True)
    
    try:
        if interaction.guild.voice_client is None:
            voice_client = await channel.connect()
        else:
            voice_client = interaction.guild.voice_client
            if voice_client.channel != channel:
                await voice_client.move_to(channel)
        
        if voice_client.is_playing() or voice_client.is_paused():
            voice_client.stop()
        
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        
        song_history = get_history(interaction.guild.id)
        song_history.append(url)
        
        voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
            play_next(interaction.guild.id, interaction.channel), bot.loop))
        
        view = MusicControlView(interaction.guild.id)
        await interaction.channel.send(f'Playing now: **{player.title}**', view=view)
        await interaction.followup.send(f'Started playing immediately: **{player.title}**', ephemeral=True)
    
    except Exception as e:
        await interaction.followup.send(f"An error occurred: {str(e)}", ephemeral=True)
        print(f"Error in play-now command: {e}")

async def play_next(guild_id, channel):
    """Play the next song in the queue"""
    voice_client = discord.utils.get(bot.voice_clients, guild__id=guild_id)
    if not voice_client:
        return
    
    # Check if loop is enabled
    if get_loop_state(guild_id):
        song_history = get_history(guild_id)
        if song_history:
            url = song_history[-1]
            try:
                player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
                voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                    play_next(guild_id, channel), bot.loop))
                view = MusicControlView(guild_id)
                await channel.send(f'🔁 Looping: **{player.title}**', view=view)
                return
            except Exception as e:
                await channel.send(f"Error looping song: {str(e)}")
                print(f"Error in loop playback: {e}")
    
    queue = get_queue(guild_id)
    
    if len(queue) > 0:
        url = queue.pop(0)
        try:
            song_history = get_history(guild_id)
            song_history.append(url)
            
            player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
            voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(
                play_next(guild_id, channel), bot.loop))
            view = MusicControlView(guild_id)
            await channel.send(f'Now playing: **{player.title}**', view=view)
        except Exception as e:
            await channel.send(f"Error playing next song: {str(e)}")
            print(f"Error in play_next: {e}")

@bot.tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    """Pause the currently playing song"""
    voice_client = interaction.guild.voice_client
    
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Paused", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing right now!", ephemeral=True)

@bot.tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    """Resume the paused song"""
    voice_client = interaction.guild.voice_client
    
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Resumed", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is paused right now!", ephemeral=True)

@bot.tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    """Skip the current song"""
    voice_client = interaction.guild.voice_client
    
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing right now!", ephemeral=True)

@bot.tree.command(name="stop", description="Stop playing and clear the queue")
async def stop(interaction: discord.Interaction):
    """Stop playing and clear the queue"""
    voice_client = interaction.guild.voice_client
    
    if voice_client:
        queue = get_queue(interaction.guild.id)
        queue.clear()
        set_loop_state(interaction.guild.id, False)
        voice_client.stop()
        await interaction.response.send_message("⏹️ Stopped and cleared queue", ephemeral=True)
    else:
        await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)

@bot.tree.command(name="leave", description="Leave the voice channel")
async def leave(interaction: discord.Interaction):
    """Leave the voice channel"""
    voice_client = interaction.guild.voice_client
    
    if voice_client:
        await voice_client.disconnect()
        queue = get_queue(interaction.guild.id)
        queue.clear()
        set_loop_state(interaction.guild.id, False)
        await interaction.response.send_message("👋 Disconnected", ephemeral=True)
    else:
        await interaction.response.send_message("I'm not in a voice channel!", ephemeral=True)

@bot.tree.command(name="queue", description="Show the current queue")
async def show_queue(interaction: discord.Interaction):
    """Show the current queue"""
    queue = get_queue(interaction.guild.id)
    
    if len(queue) == 0:
        await interaction.response.send_message("The queue is empty!", ephemeral=True)
    else:
        queue_list = "\n".join([f"{i+1}. {url}" for i, url in enumerate(queue[:20])])  # Show first 20
        if len(queue) > 20:
            queue_list += f"\n... and {len(queue) - 20} more"
        await interaction.response.send_message(f"**Current Queue:**\n{queue_list}", ephemeral=True)

@bot.tree.command(name="volume", description="Set playback volume (0-100)")
async def volume(interaction: discord.Interaction, level: int):
    """Set the playback volume"""
    if not 0 <= level <= 100:
        await interaction.response.send_message("Volume must be between 0 and 100!", ephemeral=True)
        return
    
    voice_client = interaction.guild.voice_client
    
    if voice_client and voice_client.source:
        voice_client.source.volume = level / 100
        await interaction.response.send_message(f"🔊 Volume set to {level}%", ephemeral=True)
    else:
        await interaction.response.send_message("Nothing is playing right now!", ephemeral=True)

# Run the bot
if __name__ == "__main__":
    load_dotenv()
    TOKEN = os.getenv("DISCORD_BOT_TOKEN", "NONE")
    if not TOKEN:
        print("ERROR: Please set DISCORD_BOT_TOKEN environment variable")
        print("You can get a token from https://discord.com/developers/applications")
    else:
        bot.run(TOKEN)