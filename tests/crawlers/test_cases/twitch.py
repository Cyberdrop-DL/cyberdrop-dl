DOMAIN = "twitch"
TEST_CASES = [
    (
        "https://www.twitch.tv/fanfan/clip/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
        [
            {
                "url": "re:/h0073-YuUM9o4kAK7QUTjA/AT-cm%7Ch0073-YuUM9o4kAK7QUTjA.mp4",
                "filename": "not scared btw [GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM][60fps][1080p].mp4",
                "debrid_link": None,
                "original_filename": "not scared btw",
                "referer": "https://clips.twitch.tv/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
                "album_id": None,
                "datetime": 1707334361,
                "download_folder": "re:Loose Files (Twitch)",
            }
        ],
    ),
    (
        "https://clips.twitch.tv/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
        [
            {
                "url": "re:/h0073-YuUM9o4kAK7QUTjA/AT-cm%7Ch0073-YuUM9o4kAK7QUTjA.mp4",
                "filename": "not scared btw [GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM][60fps][1080p].mp4",
                "referer": "https://clips.twitch.tv/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
            }
        ],
    ),
    (
        "https://clips.twitch.tv/embed?clip=GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
        [
            {
                "url": "re:/h0073-YuUM9o4kAK7QUTjA/AT-cm%7Ch0073-YuUM9o4kAK7QUTjA.mp4",
                "filename": "not scared btw [GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM][60fps][1080p].mp4",
                "referer": "https://clips.twitch.tv/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
            }
        ],
    ),
    (
        "https://m.twitch.tv/clip/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
        [
            {
                "url": "re:/h0073-YuUM9o4kAK7QUTjA/AT-cm%7Ch0073-YuUM9o4kAK7QUTjA.mp4",
                "filename": "not scared btw [GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM][60fps][1080p].mp4",
                "referer": "https://clips.twitch.tv/GeniusDifficultSproutPhilosoraptor-5i5Qz2jiQArtBROM",
            }
        ],
    ),
    (
        "https://www.twitch.tv/videos/1744169736",
        [
            {
                "url": "re:https://usher.ttvnw.net/vod/1744169736.m3u8",
                "filename": "who asked [1744169736][avc1][60fps][1080p].mp4",
                "debrid_link": None,
                "original_filename": "who asked",
                "referer": "https://www.twitch.tv/videos/1744169736",
                "album_id": None,
                "datetime": 1676928416,
                "download_folder": "re:Loose Files (Twitch)",
            }
        ],
    ),
    (
        "https://clips.twitch.tv/LitigiousNaiveReubenUWot-E0uuswUYOhs9htgV",
        [
            {
                "url": "ANY",
                "filename": "IM GUNNA MAKE IT... [LitigiousNaiveReubenUWot-E0uuswUYOhs9htgV][60fps][1440p].mp4",
                "debrid_link": None,
                "original_filename": "IM GUNNA MAKE IT...",
                "referer": "https://clips.twitch.tv/LitigiousNaiveReubenUWot-E0uuswUYOhs9htgV",
                "album_id": None,
                "datetime": 1767765454,
                "download_folder": "re:Loose Files (Twitch)",
            }
        ],
    ),
    (  # Unavailable media (4K)
        "https://www.twitch.tv/videos/2662839277",
        [
            {
                "url": "ANY",
                "filename": "Hanging out! [2662839277][avc1][60fps][4K].mp4",
            }
        ],
    ),
    (
        "https://www.twitch.tv/collections/3d4MEgywDhcOUg?filter=collections",
        [
            {
                "url": "ANY",
                "download_folder": "re:The Mix Contest - Season 7 (Twitch)",
                "album_id": "3d4MEgywDhcOUg",
            }
        ],
        8,
    ),
]
