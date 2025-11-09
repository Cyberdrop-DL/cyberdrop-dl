import re

DOMAIN = "transfer.it"
TEST_CASES = [
    (
        "https://transfer.it/t/yhWbjogXxRLL",
        [
            {
                "url": "https://transfer.it/t/yhWbjogXxRLL#qgxVBD5D",
                "filename": "start_linux.sh",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#qgxVBD5D",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test/Cyberdrop-DL.v8.4.0"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
                "debrid_link": "ANY",
            },
            {
                "url": "https://transfer.it/t/yhWbjogXxRLL#7lhHmJga",
                "filename": "start_windows.bat",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#7lhHmJga",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test/Cyberdrop-DL.v8.4.0"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
            },
            {
                "url": "https://transfer.it/t/yhWbjogXxRLL#OxwHBbaa",
                "filename": "Cyberdrop-DL.v8.4.0.zip",
                "referer": "https://transfer.it/t/yhWbjogXxRLL#OxwHBbaa",
                "download_folder": "re:" + re.escape("CDL test transfer (Transfer.it)/test"),
                "datetime": 1762696355,
                "album_id": "yhWbjogXxRLL",
            },
        ],
    ),
]
