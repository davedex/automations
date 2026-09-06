import json
import random
import time
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from ytmusicapi import YTMusic

def send_discord_message(message: str):
    token_file = Path('/run/user/1000/secrets/discord_bot_token')
    if not token_file.exists():
        print(f"Warning: Discord token file not found at {token_file}. Skipping notification.")
        return

    try:
        import discord
        from discord.ext import commands
    except ImportError:
        print("Warning: discord.py package not found. Skipping notification.")
        return

    try:
        with open(token_file, 'r') as file:
            token = file.read().strip()

        channel_id = 1330828675847028819
        intents = discord.Intents.default()
        intents.messages = True

        bot = commands.Bot(command_prefix='!', intents=intents)

        @bot.event
        async def on_ready():
            print(f"Logged into Discord as {bot.user.name}")
            channel = bot.get_channel(channel_id)
            if channel:
                print(f"Sending Discord message to channel {channel_id}...")
                await channel.send(message)
            else:
                print(f"Error: Discord channel {channel_id} not found.")
            await bot.close()

        print("Starting Discord bot client...")
        bot.run(token)
        print("Discord notification sent and bot disconnected.")
    except Exception as e:
        print(f"Warning: Failed to send Discord notification: {e}", file=sys.stderr)

# =============================================================================
# CONFIG
# =============================================================================

# Replace with your ListenBrainz username
LISTENBRAINZ_USERNAME = "dexforgets"

# Optional: Add your User Token from listenbrainz.org/settings/ if you encounter rate limits
LISTENBRAINZ_TOKEN = "060d8725-2d1f-4c70-abed-b8cb5d0942af"

YTMUSIC_HEADERS = Path(__file__).parent / "browser.json"

SCROBBLE_CACHE_FILE = Path("listenbrainz_scrobbles_cache.json")

# ListenBrainz allows up to 1000 listens per API request
PAGE_SIZE = 1000

PLAYLIST_ID = "PLcBZP0TaYjtHM-j7uhESWdbr3KRpD_zoo"

# Playlist size + sampling
LEAST_LISTENED_POOL = 200
PRINT_SAMPLE = 20

# Matching thresholds
TRACK_MATCH_THRESHOLD = 0.85

# =============================================================================
# UTILS
# =============================================================================

def normalize(text: str) -> str:
    return (text or "").lower().strip()


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def scrobble_signature(s: Dict[str, Any]) -> Tuple:
    """
    Robust signature for de-duping cached listens.
    """
    t = int(s.get("listened_at", 0) or 0)
    meta = s.get("track_metadata") or {}

    artist = meta.get("artist_name", "")
    artists_norm = tuple(normalize(a) for a in [artist] if a)

    title = normalize(meta.get("track_name", ""))
    album_title = normalize(meta.get("release_name", ""))
    origin = ""  # ListenBrainz handles application origin through user-agents

    return (t, artists_norm, title, album_title, origin)


def track_key_from_scrobble(s: Dict[str, Any]) -> Tuple[str, str]:
    """
    Aggregation key used for playcounts: (artists_string, title)
    """
    meta = s.get("track_metadata") or {}
    artist_str = normalize(meta.get("artist_name", ""))
    title_str = normalize(meta.get("track_name", ""))
    return (artist_str, title_str)


def filter_to_liked_videoids(
    candidate_videoids: List[str],
    liked_songs: List[Dict[str, str]],
) -> Tuple[List[str], List[str]]:
    liked_ids = {s["videoId"] for s in liked_songs}
    kept = [vid for vid in candidate_videoids if vid in liked_ids]
    dropped = [vid for vid in candidate_videoids if vid not in liked_ids]
    return kept, dropped


# =============================================================================
# LISTENBRAINZ CACHE + FETCH
# =============================================================================

@dataclass
class ScrobbleCache:
    scrobbles: List[Dict[str, Any]]
    max_time: int  # latest time in cache (unix seconds)

    @staticmethod
    def load(path: Path) -> "ScrobbleCache":
        if not path.exists():
            return ScrobbleCache(scrobbles=[], max_time=0)
        with path.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        return ScrobbleCache(
            scrobbles=raw.get("scrobbles", []) or [],
            max_time=int(raw.get("max_time", 0) or 0),
        )

    def save(self, path: Path) -> None:
        payload = {
            "max_time": int(self.max_time),
            "count": len(self.scrobbles),
            "saved_at": int(time.time()),
            "scrobbles": self.scrobbles,
        }
        with path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)


def listenbrainz_get_listens(
    session: requests.Session,
    *,
    max_items: int,
) -> List[Dict[str, Any]]:
    """
    Fetch up to `max_items` most recent listens from ListenBrainz.
    """
    url = f"https://api.listenbrainz.org/1/user/{LISTENBRAINZ_USERNAME}/listens"
    params: Dict[str, Any] = {
        "count": max_items,
    }

    headers = {
        "User-Agent": "YTM-Least-Listened-Script/1.0.0"
    }
    if LISTENBRAINZ_TOKEN:
        headers["Authorization"] = f"Token {LISTENBRAINZ_TOKEN}"

    r = session.get(url, params=params, headers=headers, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data.get("payload", {}).get("listens", []) or []


def update_scrobble_cache(
    cache_path: Path = SCROBBLE_CACHE_FILE,
    batch_size: int = 1000,
) -> ScrobbleCache:
    """
    Fetch the most recent `batch_size` listens and merge into cache.
    No server-side filtering; rely on local dedupe.
    """
    cache = ScrobbleCache.load(cache_path)
    session = requests.Session()

    latest = listenbrainz_get_listens(session, max_items=batch_size)

    if not latest:
        print(f"✅ No listens returned. Cache size: {len(cache.scrobbles)}")
        return cache

    combined = cache.scrobbles + latest
    seen = set()
    deduped: List[Dict[str, Any]] = []

    for s in combined:
        sig = scrobble_signature(s)
        if sig in seen:
            continue
        seen.add(sig)
        deduped.append(s)

    cache.scrobbles = deduped
    cache.max_time = max(int(s["listened_at"]) for s in deduped if "listened_at" in s)
    cache.save(cache_path)

    print(
        f"✅ Fetched {len(latest)} recent listens; "
        f"cache now {len(cache.scrobbles)} total (max_time={cache.max_time})"
    )
    return cache


def build_playcounts_from_scrobbles(scrobbles: Iterable[Dict[str, Any]]) -> Dict[Tuple[str, str], int]:
    """
    Build playcounts per (artists_string, title) from raw listens.
    """
    counter = Counter()
    for s in scrobbles:
        key = track_key_from_scrobble(s)
        if key == ("", ""):
            continue
        counter[key] += 1
    return dict(counter)


# =============================================================================
# YTMUSIC HELPERS
# =============================================================================

def get_all_liked_songs(ytmusic: YTMusic) -> List[Dict[str, str]]:
    """
    Returns list of {title, artist, videoId} from the YouTube Music
    "Liked Music" playlist (list=LM).
    """
    liked_songs: List[Dict[str, str]] = []

    pl = ytmusic.get_playlist("LM", limit=5000)
    tracks = pl.get("tracks", []) or []

    for track in tracks:
        video_id = track.get("videoId")
        if not video_id:
            continue

        artists = track.get("artists") or []
        artist = (artists[0].get("name", "") if artists else "unknown")

        liked_songs.append(
            {
                "title": normalize(track.get("title", "")),
                "artist": normalize(artist),
                "videoId": video_id,
            }
        )

    return liked_songs


def build_liked_playcounts(
    liked_songs: List[Dict[str, str]],
    lb_tracks: Dict[Tuple[str, str], int],
    threshold: float = TRACK_MATCH_THRESHOLD,
) -> List[Tuple[str, int, str, str]]:
    """
    Returns (videoId, playcount, artist, title) for LIKED songs ONLY.
    - Exact match first (fast and safest)
    - Fuzzy match fallback only affects playcount assignment,
      never which songs are eligible.
    """
    lb_items = list(lb_tracks.items())
    scored: List[Tuple[str, int, str, str]] = []

    for song in liked_songs:
        exact_key = (song["artist"], song["title"])
        if exact_key in lb_tracks:
            scored.append((song["videoId"], lb_tracks[exact_key], song["artist"], song["title"]))
            continue

        # Fuzzy fallback
        best = 0
        for (m_artist, m_title), m_count in lb_items:
            if similar(song["artist"], m_artist) > threshold and similar(song["title"], m_title) > threshold:
                if m_count > best:
                    best = m_count

        scored.append((song["videoId"], best, song["artist"], song["title"]))

    return scored


# =============================================================================
# PLAYLIST MANAGEMENT
# =============================================================================

def replace_playlist_contents(video_ids: List[str], playlist_id: str, ytmusic: YTMusic) -> None:
    existing = ytmusic.get_playlist(playlist_id, limit=1000)
    tracks = existing.get("tracks") or []
    print(f"Length of existing playlist: {len(tracks)}")

    to_remove = []
    for t in tracks:
        if "videoId" in t and "setVideoId" in t:
            to_remove.append({"videoId": t["videoId"], "setVideoId": t["setVideoId"]})
        else:
            print(f"⚠️ Skipping track missing setVideoId: {t}")

    print(f"Removing: {len(to_remove)} tracks")
    if to_remove:
         ytmusic.remove_playlist_items(playlist_id, to_remove)

    time.sleep(5)

    unique_ids = list(dict.fromkeys(video_ids))  # drop duplicates, keep order

    if unique_ids:
        print(f"Adding to playlist: {len(unique_ids)}")
        add_result = ytmusic.add_playlist_items(playlist_id, unique_ids)

    time.sleep(5)

    updated = ytmusic.get_playlist(playlist_id, limit=1000)
    print(f"Length of updated playlist: {len(updated.get('tracks') or [])}")


def debug_verify_playlist_likedness(playlist_id: str, ytmusic: YTMusic, liked_songs: List[Dict[str, str]]) -> None:
    liked_ids = {s["videoId"] for s in liked_songs}
    pl = ytmusic.get_playlist(playlist_id, limit=5000)
    tracks = pl.get("tracks") or []

    not_liked = []
    for t in tracks:
        vid = t.get("videoId")
        if vid and vid not in liked_ids:
            not_liked.append((vid, t.get("title"), (t.get("artists") or [{}])[0].get("name")))

    print(f"Playlist tracks: {len(tracks)}")
    print(f"Not liked (by videoId): {len(not_liked)}")
    for vid, title, artist in not_liked[:20]:
        print(f"  {artist} – {title} ({vid})")


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    script_dir = Path(__file__).parent.resolve()
    browser_file = script_dir / 'browser.json'
    encrypted_browser = script_dir / 'encrypted_browser.json'

    # Always ensure a clean start to avoid race conditions or stale credentials
    if browser_file.exists():
        browser_file.unlink()

    if not encrypted_browser.exists():
        print(f"Error: {encrypted_browser} does not exist.")
        sys.exit(1)

    print("Decrypting browser.json...")
    key_path = Path.home() / '.config/sops/age/keys.txt'
    try:
        with open(browser_file, 'w') as fh:
            subprocess.run(
                ['sops', '--age', str(key_path), '-d', str(encrypted_browser)],
                stdout=fh,
                check=True,
                timeout=10
            )

        ytmusic = YTMusic(str(browser_file))
    except Exception as e:
        print(f"Bootstrap/Decryption failed: {e}")
        send_discord_message(f"❌ **Least Listened Playlist Sync FAILED!**\nCredential decryption error: `{e}`")
        sys.exit(1)
    finally:
        # Clean up unencrypted file immediately to maintain strict system security
        if browser_file.exists():
            browser_file.unlink()

    try:
        # 1) Update listen cache (max=1000 batches)
        cache = update_scrobble_cache(SCROBBLE_CACHE_FILE, PAGE_SIZE)

        # 2) Build playcounts from raw listens
        lb_tracks = build_playcounts_from_scrobbles(cache.scrobbles)
        print(f"Loaded playcounts for {len(lb_tracks)} unique tracks from cache")

        # Top 5 sanity check
        top5 = sorted(lb_tracks.items(), key=lambda x: x[1], reverse=True)[:5]
        print("Top 5 ListenBrainz tracks by listens:")
        for (a, t), c in top5:
            print(f"  {c:4}  {a} – {t}")

        # 3) Load liked songs
        print("🔄 Fetching liked songs from YouTube Music...")
        liked_songs = get_all_liked_songs(ytmusic)
        print(f"Liked songs: {len(liked_songs)}")

        # 4) Compute playcounts FOR LIKED SONGS ONLY
        scored = build_liked_playcounts(liked_songs, lb_tracks, threshold=TRACK_MATCH_THRESHOLD)

        # 5) Pick least listened, shuffle
        least_listened = sorted(scored, key=lambda x: x[1])[:LEAST_LISTENED_POOL]
        random.shuffle(least_listened)
        video_ids = [vid for vid, _, _, _ in least_listened]

        print(f"\n🎵 {PRINT_SAMPLE} least listened liked songs (listens, artist, title, videoId):")
        for vid, count, artist, title in least_listened[:PRINT_SAMPLE]:
            print(f"{count:4}  {artist} – {title}  ({vid})")

        # 6) Replace playlist
        video_ids, dropped = filter_to_liked_videoids(video_ids, liked_songs)

        if dropped:
            print("⚠️ Dropped non-liked videoIds (this should be empty):")
            for vid in dropped[:20]:
                print("  ", vid)
            if len(dropped) > 20:
                print(f"  ...and {len(dropped) - 20} more")

        random.shuffle(video_ids)
        replace_playlist_contents(video_ids, PLAYLIST_ID, ytmusic)
        debug_verify_playlist_likedness(PLAYLIST_ID, ytmusic, liked_songs)

        # Send success notification
        send_discord_message(
            f"✅ **Least Listened Playlist Sync Successful!**\n"
            f"Successfully updated 'Least Listened' playlist with {len(video_ids)} low-playcount liked songs."
        )

    except Exception as e:
        # Send failure notification
        send_discord_message(f"❌ **Least Listened Playlist Sync FAILED!**\nError: `{e}`")
        raise e


if __name__ == "__main__":
    main()
