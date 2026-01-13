DOMAIN = "bandcamp"
TEST_CASES = [
    (
        "https://0101.bandcamp.com/track/mal-damour",
        [
            {
                "url": "https://0101.bandcamp.com/track/mal-damour#mp3-320",
                "filename": "Snails House - .｡+mal damour.｡+.mp3",
                "original_filename": "Snail's House - .｡:+*mal d'amour.｡:+*.mp3",
                "referer": "https://0101.bandcamp.com/track/mal-damour",
                "datetime": 1529416422,
                "downloa_folder": "re:Loose Files (BandCamp)",
                "debrid_link": "ANY",
            }
        ],
    ),
    (
        "https://wetleg.bandcamp.com/album/moisturizer",
        [
            {
                "url": "https://wetleg.bandcamp.com/track/cpr#mp3-128",
                "referer": "https://wetleg.bandcamp.com/track/cpr",
                "download_folder": "re:moisturizer (Bandcamp)",
                "filename": "Wet Leg - CPR.mp3",
                "original_filename": "Wet Leg - CPR.mp3",
                "debrid_link": "ANY",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/mangetout#mp3-128",
                "filename": "Wet Leg - mangetout.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/pillow-talk#mp3-128",
                "filename": "Wet Leg - pillow talk.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/catch-these-fists#mp3-128",
                "filename": "Wet Leg - catch these fists.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/jennifers-body#mp3-128",
                "filename": "Wet Leg - jennifers body.mp3",
                "original_filename": "Wet Leg - jennifer's body.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/davina-mccall#mp3-128",
                "filename": "Wet Leg - davina mccall.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/pokemon#mp3-128",
                "filename": "Wet Leg - pokemon.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/liquidize#mp3-128",
                "filename": "Wet Leg - liquidize.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/pond-song#mp3-128",
                "filename": "Wet Leg - pond song.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/don-t-speak#mp3-128",
                "filename": "Wet Leg - don’t speak.mp3",  # noqa: RUF001
            },
            {
                "url": "https://wetleg.bandcamp.com/track/11-21#mp3-128",
                "filename": "Wet Leg - 1121.mp3",
            },
            {
                "url": "https://wetleg.bandcamp.com/track/u-and-me-at-home#mp3-128",
                "filename": "Wet Leg - u and me at home.mp3",
            },
        ],
    ),
]
