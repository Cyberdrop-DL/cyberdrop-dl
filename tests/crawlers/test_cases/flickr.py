DOMAIN = "flickr"
TEST_CASES = [
    (
        "https://www.flickr.com/photos/jillblack33/42279501790/in/photolist-27q6uTq-64djfR-bFAauM-79mSQe-294ixC3-s1Ltu4-MaSsV-4CUE8Q-4Rkr8R-QtkbP-aD588-2wyM-2mB9CCC-6AS9fc-7gdV1m-5TjWGC-5TfCwR-3y72Tr-48JHn-nemFJ-9dCzq1-MU2AYb-ctYWi",
        [
            {
                "url": "https://live.staticflickr.com/1779/42279501790_b008687536_o.png",
                "filename": "LONE SURVIVOR [42279501790].png",
                "debrid_link": None,
                "original_filename": "LONE SURVIVOR",
                "referer": "https://www.flickr.com/photos/jillblack33/42279501790",
                "album_id": None,
                "datetime": 1534502481,
                "download_folder": "re:Loose Files (Flickr)",
            }
        ],
    ),
    (
        "https://www.flickr.com/photos/soniaadammurray/52448052841",
        [
            {
                "url": "re:https://live.staticflickr.com/video/52448052841/e96cd3ae34/1080p.mp4",
                "filename": "Happy Birthday, to My Wonderful, Husband, Gerry [52448052841].mp4",
                "debrid_link": None,
                "original_filename": "Happy Birthday, to My Wonderful, Husband, Gerry",
                "referer": "https://www.flickr.com/photos/soniaadammurray/52448052841",
                "album_id": None,
                "datetime": 1666536987,
                "download_folder": "re:Loose Files (Flickr)",
            }
        ],
    ),
    (
        "https://www.flickr.com/photos/bour3/albums/72157641382742025",
        [
            {
                "url": "re:https://live.staticflickr.com/",
                "download_folder": "re:lotus flower pop-up card with led (Flickr)",
            },
        ],
        30,
    ),
]
