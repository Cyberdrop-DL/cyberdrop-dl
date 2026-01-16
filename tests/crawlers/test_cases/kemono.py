DOMAIN = "kemono"
TEST_CASES = [
    (
        "https://kemono.cr/patreon/user/27174868/post/133667042",
        [
            {
                "url": "https://kemono.cr/data/0d/c3/0dc3ecec556918b882674c5dd63f8fa1867867157ce1ca675b0bf79e6b73fb04.jpg?f=Birthday_Kim.jpg",
                "filename": "Birthday_Kim.jpg",
                "referer": "https://kemono.cr/patreon/user/27174868/post/133667042",
                "album_id": "27174868",
                "datetime": 1752004344,
            }
        ],
    ),
    (
        "https://kemono.cr/data/49/83/49830d8d281ad9a508f88b081b3a112aa4011a1af3bb2539f88f4e635edf98a1.png?f=june_Schedule.png",
        [
            {
                "url": "https://kemono.cr/data/49/83/49830d8d281ad9a508f88b081b3a112aa4011a1af3bb2539f88f4e635edf98a1.png?f=june_Schedule.png",
                "filename": "june_Schedule.png",
                "referer": "https://kemono.cr/data/49/83/49830d8d281ad9a508f88b081b3a112aa4011a1af3bb2539f88f4e635edf98a1.png?f=june_Schedule.png",
                "album_id": None,
                "datetime": None,
            },
        ],
    ),
    (
        "https://kemono.cr/discord/server/794379082535927828/921981855706796032",
        [
            {
                "url": "https://kemono.cr/data/49/83/49830d8d281ad9a508f88b081b3a112aa4011a1af3bb2539f88f4e635edf98a1.png?f=june_Schedule.png",
                "filename": "june_Schedule.png",
                "referer": "https://kemono.cr/discord/server/794379082535927828/921981855706796032#1257906262025175090",
                "download_folder": r"re:Schpicy-s server \[discord\] \(Kemono\)\/\#schedule",
                "album_id": "794379082535927828",
                "datetime": 1719996623,
            },
        ],
        3,
    ),
    (
        "https://kemono.cr/patreon/user/16573132",
        [
            {
                "url": "https://kemono.cr/data/01/1e/011e7a27eca93eba99ab223553d6079495a55c87106fa0e36efb8810048da92f.jpg?f=httpswww.patreon.commedia-uZ0FBQUFBQmdWWnhiV0xoYnpvV0Nnd0ZvMnM5UnkyTVF1LXd4MEpNYmVRWGNMNEZhUE1wWWJreVBqS1F2UzB3R2lYaXpDaXBWUy14M2l1WGtITWJBX0Q4ZDRoQzBtOG5nd3JIYThERTRWNDIxeUY4RHBXaERxWkRJNS1xRXRPS2lFM3pLSEVTSW5oNVRzeU9yc21SMmo5MkJrYXVXVzFCVUtRPT0",
                "filename": "011e7a27eca93eba99ab223553d6079495a55c87106fa0e36efb8810048da92f.jpg",
                "referer": "https://kemono.cr/patreon/user/16573132/post/42836761",
                "download_folder": r"re:EUNSONGS \(Kemono\)",
                "album_id": "16573132",
                "datetime": 1602954002,
            }
        ],
        199,
    ),
    (
        "https://kemono.cr/posts?q=dandadan%20s2%20episode%208%20reaction",
        [
            {
                "url": "ANY",
                "download_folder": r"re:dandadan s2 episode 8 reaction \[search\] \(Kemono\)",
            }
        ],
        41,
    ),
    (
        "https://kemono.cr/patreon/user/47101380/post/128071303",
        [
            {
                "url": "https://kemono.cr/data/83/66/8366796e0d9fadd5e22ae8f8ea32d1b539d54e25e9da19f906fa36d1cf973cc2.jpg?f=461372899.jpg",
                "filename": "461372899.jpg",
                "referer": "https://kemono.cr/patreon/user/47101380/post/128071303",
                "download_folder": r"re:Emma_Ruby \(Kemono\)",
            },
            {
                "url": "re:pcloud",
                "filename": "ASMR ~ Girl Next Door ~ Patreon EXCLUSIVE.mp4",
                "download_folder": r"re:Emma_Ruby \(Kemono\)/Loose Files \(pCloud\)",
                "referer": "https://u.pcloud.link/publink/show?code=XZDlYb5ZlyjdRy0vl0bJWMbT2L2cp5RbUCFX",
            },
        ],
    ),
]
