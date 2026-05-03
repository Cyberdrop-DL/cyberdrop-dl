DOMAIN = "imagevenue"
TEST_CASES = [
    (
        "https://www.imagevenue.com/ME1CO3FX",
        [
            {
                "url": "https://cdn-images.imagevenue.com/73/7a/ef/ME1CO3FX_o.png",
                "filename": "20260423200059937_480x320.png",
                "debrid_link": None,
                "original_filename": "20260423200059937_480x320.png",
                "referer": "https://www.imagevenue.com/ME1CO3FX",
                "album_id": None,
                "uploaded_at": None,
                "download_folder": "re:Loose Files (ImageVenue)",
            }
        ],
        1,
    ),
    (
        "https://www.imagevenue.com/ME1BEWWG",
        [
            {
                "url": "https://cdn-images.imagevenue.com/65/8b/4d/ME1BEWWG_o.jpg",
                "filename": "001.jpg",
                "referer": "https://www.imagevenue.com/ME1BEWWG",
            }
        ],
    ),
    (
        "https://cdn-thumbs.imagevenue.com/d2/90/5c/ME1BEWWG_t.jpg",
        [
            {
                "url": "https://cdn-images.imagevenue.com/65/8b/4d/ME1BEWWG_o.jpg",
                "referer": "https://www.imagevenue.com/ME1BEWWG",
            }
        ],
    ),
]
