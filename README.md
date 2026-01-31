# Discord Music Bot

A Discord bot that plays music from YouTube using discord.py and yt-dlp.

## Features

- 🎵 Play music from YouTube URLs
- ⏸️ Pause/Resume playback
- ⏭️ Skip songs
- 📋 Queue system for multiple songs
- 🔊 Join/Leave voice channels

## Prerequisites

Before you begin, make sure you have:

1. **Python 3.8 or higher** installed
2. **FFmpeg** installed on your system
3. A **Discord Bot Token**

### Installing FFmpeg

**On Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**On macOS:**
```bash
brew install ffmpeg
```

**On Windows:**
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH

## Setup Instructions

### 1. Create a Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section
4. Click "Add Bot"
5. Under "Privileged Gateway Intents", enable:
   - Message Content Intent
   - Server Members Intent
6. Click "Reset Token" and copy your bot token (keep it secret!)

### 2. Invite the Bot to Your Server

1. In the Developer Portal, go to "OAuth2" → "URL Generator"
2. Select scopes:
   - `bot`
   - `applications.commands`
3. Select bot permissions:
   - Send Messages
   - Connect
   - Speak
   - Use Voice Activity
4. Copy the generated URL and open it in your browser
5. Select your server and authorize the bot

### 3. Install Dependencies

```bash
# Install Python dependencies
pip install -r requirements.txt

# Or install individually:
pip install discord.py yt-dlp PyNaCl
```

### 4. Set Up Your Bot Token

**Option A: Environment Variable (Recommended)**
```bash
# On Linux/macOS:
export DISCORD_BOT_TOKEN='your-token-here'

# On Windows (CMD):
set DISCORD_BOT_TOKEN=your-token-here

# On Windows (PowerShell):
$env:DISCORD_BOT_TOKEN='your-token-here'
```

**Option B: Edit the Code**
Replace the last section in `discord_music_bot.py`:
```python
if __name__ == "__main__":
    TOKEN = 'your-token-here'  # Replace with your actual token
    bot.run(TOKEN)
```

### 5. Run the Bot

```bash
python discord_music_bot.py
```

You should see:
```
[Bot Name] has connected to Discord!
Bot is in X guilds
Synced X command(s)
```

## Usage

Once the bot is running and in your server, use these slash commands:

### Commands

- `/play <url>` - Play a song from a YouTube URL
  - Example: `/play https://www.youtube.com/watch?v=dQw4w9WgXcQ`
  
- `/pause` - Pause the current song

- `/resume` - Resume the paused song

- `/skip` - Skip the current song and play the next in queue

- `/stop` - Stop playing and clear the queue

- `/leave` - Make the bot leave the voice channel

- `/queue` - Show the current queue of songs

## How It Works

1. Join a voice channel in Discord
2. Use `/play <YouTube URL>` to start playing music
3. The bot will join your channel and start playing
4. If a song is already playing, new songs are added to the queue
5. Use other commands to control playback

## Troubleshooting

### Bot doesn't respond to commands
- Make sure slash commands are synced (wait a few minutes after starting)
- Check that the bot has proper permissions in your server
- Verify Message Content Intent is enabled

### Audio doesn't play
- Ensure FFmpeg is installed and in your system PATH
- Check that the bot has "Connect" and "Speak" permissions
- Make sure you're in a voice channel when using `/play`

### "403 Forbidden" errors
- Some YouTube videos may be restricted
- Try a different video URL
- Check if yt-dlp needs updating: `pip install -U yt-dlp`

### Bot disconnects immediately
- Check your internet connection
- Verify the bot token is correct
- Look for error messages in the console

## Notes

- The bot streams audio rather than downloading files to save disk space
- Videos from playlists will only play the first video
- Some videos may not be available due to regional restrictions or age gates

## License

This project is open source and available for personal use.
