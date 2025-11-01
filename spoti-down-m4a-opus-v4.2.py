import yt_dlp
import os
import requests
import base64
import re
from urllib.parse import urlparse

class JioSaavnAPI:
    """Handle JioSaavn API and audio extraction"""
    
    def __init__(self):
        self.base_url = "https://www.jiosaavn.com"
        self.api_url = "https://www.jiosaavn.com/api.php"
    
    def get_song_details(self, song_url):
        """Get song details from JioSaavn URL"""
        try:
            # Extract song ID from URL - it's the last part after /song/name/
            song_id = song_url.rstrip('/').split('/')[-1]
            print(f"📝 Extracted Song ID: {song_id}")
            
            # Get song details from API
            params = {
                '__call': 'song.getDetails',
                'cc': 'in',
                'pids': song_id,
                '_format': 'json',
                '_marker': '0'
            }
            
            api_response = requests.get(self.api_url, params=params)
            api_response.raise_for_status()
            data = api_response.json()
            
            print(f"🔍 Debug: API Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
            
            # Try different data structures
            if isinstance(data, dict):
                if song_id in data:
                    print("✅ Found song data by ID")
                    return data[song_id]
                elif 'songs' in data and len(data['songs']) > 0:
                    print("✅ Found song data in 'songs' array")
                    return data['songs'][0]
                else:
                    # JioSaavn sometimes returns with the song ID as key
                    for key in data.keys():
                        if isinstance(data[key], dict):
                            print(f"✅ Found song data with key: {key}")
                            return data[key]
            
            print("⚠️  Could not parse song data")
            return None
            
        except Exception as e:
            print(f"❌ Failed to fetch JioSaavn song details: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_audio_url(self, song_details, quality='320'):
        """Extract audio URL from song details"""
        try:
            # JioSaavn provides URLs for different qualities
            # Check for encrypted media URLs
            if 'encrypted_media_url' in song_details:
                encrypted_url = song_details['encrypted_media_url']
                # Decrypt URL
                audio_url = self.decrypt_url(encrypted_url, quality)
                return audio_url
            elif 'media_preview_url' in song_details:
                return song_details['media_preview_url']
            
            return None
        except Exception as e:
            print(f"❌ Failed to extract audio URL: {e}")
            return None
    
    def decrypt_url(self, encrypted_url, quality='320'):
        """Decrypt JioSaavn media URL"""
        try:
            # Call JioSaavn API to decrypt
            params = {
                '__call': 'song.generateAuthToken',
                'url': encrypted_url,
                'bitrate': quality,
                '_format': 'json',
                '_marker': '0'
            }
            
            response = requests.get(self.api_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if 'auth_url' in data:
                return data['auth_url']
            
            return None
        except Exception as e:
            print(f"⚠️  URL decryption failed: {e}")
            return None

class SpotifyAPI:
    """Handle Spotify API authentication and data fetching"""
    
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        
    def get_access_token(self):
        """Get Spotify API access token"""
        auth_url = "https://accounts.spotify.com/api/token"
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        
        headers = {
            "Authorization": f"Basic {auth_header}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {"grant_type": "client_credentials"}
        
        try:
            response = requests.post(auth_url, headers=headers, data=data)
            response.raise_for_status()
            self.access_token = response.json()["access_token"]
            return True
        except Exception as e:
            print(f"❌ Failed to authenticate with Spotify: {e}")
            return False
    
    def get_track_info(self, track_url):
        """Get track information from Spotify URL"""
        if not self.access_token:
            if not self.get_access_token():
                return None
        
        # Extract track ID from URL
        track_id = track_url.split("/track/")[-1].split("?")[0]
        
        api_url = f"https://api.spotify.com/v1/tracks/{track_id}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        
        try:
            response = requests.get(api_url, headers=headers)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Failed to fetch track info: {e}")
            return None

class AudioDownloader:
    """Download audio with quality selection options"""
    
    QUALITY_PRESETS = {
        '1': {'name': 'M4A 320kbps (Best Quality)', 'codec': 'm4a', 'bitrate': '320'},
        '2': {'name': 'Opus 160kbps (High Efficiency)', 'codec': 'opus', 'bitrate': '160'},
        '3': {'name': 'Best Available (No Conversion)', 'codec': 'best', 'bitrate': None},
    }
    
    def __init__(self, output_dir="downloads"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
    
    def show_quality_options(self):
        """Display available quality options"""
        print("\n" + "="*60)
        print("🎵 QUALITY SELECTION")
        print("="*60)
        for key, preset in self.QUALITY_PRESETS.items():
            print(f"  [{key}] {preset['name']}")
        print("="*60 + "\n")
    
    def get_download_options(self, quality_choice):
        """Get yt-dlp options based on quality selection"""
        preset = self.QUALITY_PRESETS.get(quality_choice, self.QUALITY_PRESETS['1'])
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{self.output_dir}/%(title)s.%(ext)s',
            'quiet': False,
            'keepvideo': True,
        }
        
        if preset['codec'] == 'best':
            # No conversion, keep original format
            ydl_opts['postprocessors'] = []
        else:
            # Convert to selected format
            postprocessor = {
                'key': 'FFmpegExtractAudio',
                'preferredcodec': preset['codec'],
            }
            
            if preset['bitrate']:
                postprocessor['preferredquality'] = preset['bitrate']
            
            ydl_opts['postprocessors'] = [postprocessor]
        
        return ydl_opts
    
    def download_direct(self, url, filename):
        """Download audio file directly from URL"""
        try:
            print(f"⬇️  Downloading from direct URL...")
            print(f"📁 Output directory: {self.output_dir}\n")
            
            response = requests.get(url, stream=True)
            response.raise_for_status()
            
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            
            print(f"\n✅ Successfully downloaded: {filename}")
            return True
            
        except Exception as e:
            print(f"\n❌ Download failed: {e}")
            return False
    
    def download_youtube(self, search_query, quality_choice='1'):
        """Download from YouTube search"""
        try:
            url = f"ytsearch1:{search_query}"
            
            ydl_opts = self.get_download_options(quality_choice)
            ydl_opts['no_warnings'] = False
            ydl_opts['extract_audio'] = True
            ydl_opts['extractor_args'] = {'youtube': {'player_client': ['android', 'web']}}
            
            preset = self.QUALITY_PRESETS.get(quality_choice, self.QUALITY_PRESETS['1'])
            
            print(f"⬇️  Downloading from YouTube...")
            print(f"🔍 Searching: {search_query}")
            print(f"🎵 Quality: {preset['name']}")
            print(f"📁 Output directory: {self.output_dir}\n")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Unknown')
                print(f"\n✅ Successfully downloaded: {title}")
                return True
                
        except Exception as e:
            print(f"\n❌ Download failed: {e}")
            return False

def detect_url_type(url):
    """Detect if URL is from Spotify, JioSaavn, or other"""
    if 'spotify.com' in url:
        return 'spotify'
    elif 'jiosaavn.com' in url or 'saavn.com' in url:
        return 'jiosaavn'
    else:
        return 'other'

def main():
    """Main function with intelligent URL handling"""
    downloader = AudioDownloader(output_dir="downloads")
    
    # Spotify API credentials
    SPOTIFY_CLIENT_ID = "2079ef31b1bb4feaaaa811d9f280faef"
    SPOTIFY_CLIENT_SECRET = "2e76121a91864d41a768ba1eaf80610e"
    
    print("\n🎵 MULTI-PLATFORM AUDIO DOWNLOADER 🎵")
    print("Supports: Spotify, JioSaavn, YouTube\n")
    
    # Get URL from user
    url = input("Enter track URL (Spotify/JioSaavn): ").strip()
    
    if not url:
        # Use default JioSaavn URL for testing
        url = "https://www.jiosaavn.com/song/slava-funk/Mi8IRkxDAUM"
        print(f"Using default: {url}")
    
    url_type = detect_url_type(url)
    print(f"\n🔍 Detected: {url_type.upper()} URL")
    
    # Show quality options
    downloader.show_quality_options()
    quality = input("Select quality (1-3) [default: 1]: ").strip() or '1'
    
    if quality not in downloader.QUALITY_PRESETS:
        print("⚠️  Invalid selection, using M4A 320kbps")
        quality = '1'
    
    print()
    
    if url_type == 'jiosaavn':
        print("🔄 Attempting to download from JioSaavn...\n")
        
        # Try direct download with yt-dlp first (it has JioSaavn support)
        try:
            ydl_opts = downloader.get_download_options(quality)
            preset = downloader.QUALITY_PRESETS.get(quality, downloader.QUALITY_PRESETS['1'])
            
            print(f"⬇️  Downloading from JioSaavn...")
            print(f"🎵 Quality: {preset['name']}")
            print(f"📁 Output directory: downloads\n")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                track_name = info.get('title', info.get('track', 'Unknown'))
                artists = info.get('artist', info.get('uploader', 'Unknown'))
                duration = info.get('duration', 0)
                duration_min = duration // 60
                duration_sec = duration % 60
                
                print("\n" + "="*60)
                print("✅ TRACK INFORMATION")
                print("="*60)
                print(f"🎵 Track: {track_name}")
                print(f"👤 Artists: {artists}")
                print(f"⏱️  Duration: {duration_min}:{duration_sec:02d}")
                print(f"🔗 JioSaavn URL: {url}")
                print("="*60)
                print(f"\n✅ Successfully downloaded: {track_name}")
                return
                
        except Exception as e:
            print(f"❌ JioSaavn download failed: {e}")
            print("⚠️  Falling back to YouTube search...\n")
            
            # Extract song name from URL for YouTube search
            song_name = url.split('/song/')[-1].split('/')[0].replace('-', ' ')
            downloader.download_youtube(song_name, quality)
    
    elif url_type == 'spotify':
        print("🔄 Fetching track information from Spotify API...\n")
        
        spotify = SpotifyAPI(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET)
        track_info = spotify.get_track_info(url)
        
        if not track_info:
            print("❌ Failed to get track information. Exiting.")
            return
        
        # Extract track details
        track_name = track_info.get('name', 'Unknown')
        artists = [artist['name'] for artist in track_info.get('artists', [])]
        album_name = track_info.get('album', {}).get('name', 'Unknown')
        release_date = track_info.get('album', {}).get('release_date', 'Unknown')
        duration_ms = track_info.get('duration_ms', 0)
        duration_min = duration_ms // 60000
        duration_sec = (duration_ms % 60000) // 1000
        
        print("="*60)
        print("✅ TRACK INFORMATION")
        print("="*60)
        print(f"🎵 Track: {track_name}")
        print(f"👤 Artists: {', '.join(artists)}")
        print(f"💿 Album: {album_name}")
        print(f"📅 Release Date: {release_date}")
        print(f"⏱️  Duration: {duration_min}:{duration_sec:02d}")
        print(f"🔗 Spotify URL: {url}")
        print("="*60 + "\n")
        
        print("⚠️  Note: Spotify uses DRM protection.")
        print("Searching for the track on YouTube...\n")
        
        search_query = f"{track_name} {' '.join(artists)}"
        downloader.download_youtube(search_query, quality)
    
    else:
        print("⚠️  Unknown URL type. Please provide a Spotify or JioSaavn URL.")

if __name__ == "__main__":
    main()