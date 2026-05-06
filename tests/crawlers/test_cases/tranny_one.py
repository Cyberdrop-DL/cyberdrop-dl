DOMAIN = "tranny.one"
TEST_CASES = [
    # Video
    (
        "https://es.tranny.one/view/1195231",
        [
            {
                "url": r"re:https://stream.tranny.one/.+/3176393.mp4",
                "filename": "Travesti pelirroja voluptuosa muy intensa y sudorosa. [1195231].mp4",
                "referer": "https://es.tranny.one/view/1195231",
                "uploaded_at": None,
            }
        ],
    ),
    # Search
    (
        "https://www.tranny.one/search/ruby+wren/",
        [],
        2,
    ),
    # Album
    (
        "https://www.tranny.one/pics/album/2967/",
        [
            {
                "url": "re:https://pics.tranny.one/work/orig/2904/339248",
                "download_folder": r"re:Natalie mars cuckolds the world \[album\] \(Tranny\.One\)",
                "referer": "https://www.tranny.one/pics/album/2967",
                "album_id": "2967",
            }
        ],
        17,
    ),
    # Direct image download
    (
        "https://pics.tranny.one/work/orig/2915/385865/1.jpg",
        [
            {
                "url": "https://pics.tranny.one/work/orig/2915/385865/1.jpg",
                "filename": "1.jpg",
                "download_folder": r"re:Tranny\.One",
                "referer": "https://pics.tranny.one/work/orig/2915/385865/1.jpg",
            }
        ],
    ),
]
