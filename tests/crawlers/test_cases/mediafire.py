DOMAIN = "mediafire"
TEST_CASES = [
    {
        "url": "https://www.mediafire.com/file/ctppmpm7giofsgv/ADOFAI.vpk/file",
        "results": [
            {
                "url": "https://www.mediafire.com/file/ctppmpm7giofsgv",
                "filename": "ADOFAI.vpk",
                "debrid_url": "NOT_NONE",
                "original_filename": "ADOFAI.vpk",
                "referer": "https://www.mediafire.com/file/ctppmpm7giofsgv",
                "album_id": None,
                "uploaded_at": 1695820138,
                "download_folder": "re:Loose Files (Mediafire)",
                "thumbnail": None,
                "size": None,
                "duration": None,
                "parents": [],
                "metadata": {},
                "extra_info": {},
                "id": ["mediafire", "ctppmpm7giofsgv"],
            }
        ],
        "count": 1,
    },
    {
        "url": "https://www.mediafire.com/?511jd1358yxvf26",
        "results": [
            {
                "url": "https://www.mediafire.com/file/511jd1358yxvf26",
                "filename": "ipwn1x-1.0.iso",
                "debrid_url": "re:https://download",
                "original_filename": "ipwn1x-1.0.iso",
                "referer": "https://www.mediafire.com/file/511jd1358yxvf26",
                "album_id": None,
                "uploaded_at": 1654114657,
                "download_folder": "re:Loose Files (Mediafire)",
                "thumbnail": None,
                "size": None,
                "duration": None,
                "parents": [],
                "metadata": {},
                "extra_info": {},
                "id": ["mediafire", "511jd1358yxvf26"],
            }
        ],
    },
    {
        "url": "https://www.mediafire.com/folder/ixh40veo6hrc5/kcc_samples",
        "results": [
            {
                "url": "re:https://www.mediafire.com/file/",
                "debrid_url": "NOT_NONE",
                "album_id": "ixh40veo6hrc5",
                "download_folder": "re:kcc samples (Mediafire)",
                "metadata": {},
            },
        ],
        "count": 11,
    },
    {
        "url": "https://www.mediafire.com/folder/m3sij67rizpb4/XJTU-SY_Bearing_Datasets",
        "description": "folder with subfolders",
        "results": [],
        "count": 18,
    },
    {
        "url": "https://www.mediafire.com/folder/9a6a91cgbd7m8",
        "description": "folder with subfolders",
        "results": [],
        "count": 36,
    },
    {
        "url": "https://www.mediafire.com/folder/ujs6wzw0cecof/",
        "description": "DMCA folder",
        "fail": 410,
        "results": [],
    },
]
