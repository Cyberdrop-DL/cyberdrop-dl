from __future__ import annotations

import time
from typing import Any

from cyberdrop_dl.clients.flaresolverr import Solution, _parse_cookies
from cyberdrop_dl.clients.response import _FlareSolverrResponse, _infer_content_type_from_body

# ---------------------------------------------------------------------------
# Fixtures: example FlareSolverr JSON responses
# ---------------------------------------------------------------------------

FLARESOLVERR_RESPONSE_EMPTY_HEADERS: dict[str, Any] = {
    "status": "ok",
    "message": "Challenge solved!",
    "solution": {
        "url": "https://1337x.to/cat/Movies/1/",
        "status": 200,
        "cookies": [
            {
                "domain": ".1337x.to",
                "expiry": 1808054295,
                "httpOnly": True,
                "name": "cf_clearance",
                "path": "/",
                "sameSite": "None",
                "secure": True,
                "value": "KKW9gSBPiS8pWkenAaGd82lMQZwcCqSEALdTvs13Tf7QIdxHRN4NKdwhnut21rKA",
            }
        ],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "headers": {},
        "response": '<html><head>\n<meta charset="utf></html>',
    },
    "startTimestamp": 1776518283422,
    "endTimestamp": 1776518297487,
    "version": "3.4.6",
}

FLARESOLVER_RESP_JSON_WRAPPED_IN_HTML: dict[str, Any] = {
    "status": "ok",
    "message": "Challenge solved!",
    "solution": {
        "url": "https://www.tikwm.com/api/user/posts?unique_id=user_embongngo&count=50&cursor=0",
        "status": 200,
        "cookies": [
            {
                "domain": ".tikwm.com",
                "expiry": 1819086364,
                "httpOnly": True,
                "name": "cf_clearance",
                "path": "/",
                "sameSite": "None",
                "secure": True,
                "value": "uOF3vEc7QtZfPUB28qZfCy.GKmByEgAyDpoyO9EYfSU-1787550364-1.2.1.1-HzZDz",
            }
        ],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36",
        "headers": {},
        "response": '<html><head><meta name="color-scheme" content="light dark"><meta charset="utf-8"></head><body><pre>{"code":0,"msg":"success","processed_time":0.4496,"data":{"videos":[{"video_id":"7656417069000314119","region":"VN","title":"\\u1eb1m \\u1eb1m","content_desc":[],"cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oYPsaIBws0DowvEBJYAIDiVqbyBBBasEaOkAi~tplv-tiktokx-cropcenter-q:300:400:q70.jpeg?dr=9232&amp;refresh_token=02b9737c&amp;x-expires=1787634000&amp;x-signature=nGPQ54JR%2FNyxjJhBKpXS3qiKVKo%3D&amp;t=bacd0480&amp;ps=933b5bde&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=cover&amp;biz_tag=tt_video&amp;s=PUBLISH","ai_dynamic_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oABEbABVIAsDxi0BHY8EsABi6vakaqIOzsPBB~tplv-tiktokx-origin.image?dr=9229&amp;refresh_token=2159655c&amp;x-expires=1787634000&amp;x-signature=uZmf%2Bbkqb5Hr0poPGvXWkgowf60%3D&amp;t=bacd0480&amp;ps=4f5296ae&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=dynamic_cover","origin_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oksPsIsAqIYT3BVp0nTOaABiBkbEaBDsiBBEB~tplv-tiktokx-shrink-aq:360:360:q75.webp?dr=13023&amp;refresh_token=4a83699b&amp;x-expires=1787634000&amp;x-signature=NYrI4%2Fq7u49abWyzVtcHE6G1gQ0%3D&amp;t=bacd0480&amp;ps=d97f9a4f&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=feed_cover","duration":29,"play":"https:\\/\\/v19.tiktokcdn-eu.com\\/71b37c037867243b0fab0d7bac628b48\\/6a8d2c3a\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/oQ0RpQEJ2EVRCBUtEY6wDCgQDfAvFBgCCBfqQI\\/?a=1233&amp;bti=OTg7QGozQHM6OjZALTAzYCMucCMxNDNg&amp;&amp;bt=702&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=NThmMzgzNjlmMzhkOTxlM0BpMzRmZW45cmZqPDMzODczNEAzMjU0YC0tX2IxNWJhYTAxYSNhLzBpMmQ0cS1hLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","wmplay":"https:\\/\\/v19.tiktokcdn-eu.com\\/71b37c037867243b0fab0d7bac628b48\\/6a8d2c3a\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/oQ0RpQEJ2EVRCBUtEY6wDCgQDfAvFBgCCBfqQI\\/?a=1233&amp;bti=OTg7QGozQHM6OjZALTAzYCMucCMxNDNg&amp;&amp;bt=702&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=NThmMzgzNjlmMzhkOTxlM0BpMzRmZW45cmZqPDMzODczNEAzMjU0YC0tX2IxNWJhYTAxYSNhLzBpMmQ0cS1hLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","size":2607494,"wm_size":0,"music":"https:\\/\\/sf19-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646718711990176528.mp3","music_info":{"id":"7628076282494421768","title":"original sound - _emnhochih_210","play":"https:\\/\\/sf19-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646718711990176528.mp3","cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/0b5bd04922a2d5e79636ee74edf721c3~tplv-tiktokx-cropcenter-q:1080:1080:q70.webp?dr=9608&amp;refresh_token=d7430bba&amp;x-expires=1787634000&amp;x-signature=uFJ%2FDjk7O%2B4KmBiXUfTvTL29pIY%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH","author":"em H\\u1ed5 \\ud83d\\udc2f","original":true,"duration":28,"album":""},"play_count":1495,"digg_count":141,"comment_count":29,"share_count":14,"download_count":0,"collect_count":11,"create_time":1782648522,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"is_top":0},{"video_id":"7654183763471043847","region":"VN","title":"\\ud83e\\udd19\\ud83c\\udffb","content_desc":[],"cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oEQyQDDJjPvcAeDUQFBlfr1kiegIXEBAopjzCh~tplv-tiktokx-cropcenter-q:300:400:q70.jpeg?dr=9232&amp;refresh_token=31a3324b&amp;x-expires=1787634000&amp;x-signature=o1ejH%2BzWys1jJkuEpPXoEsZThh8%3D&amp;t=bacd0480&amp;ps=933b5bde&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=cover","ai_dynamic_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oAHEaixBg1pBXf0if5qRBAAwII5S5OIURLxgCU~tplv-tiktokx-origin.image?dr=9229&amp;refresh_token=f6eca6fd&amp;x-expires=1787634000&amp;x-signature=8pRhRgOp1S73lSl99ftGpgsyAV0%3D&amp;t=bacd0480&amp;ps=4f5296ae&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=dynamic_cover","origin_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/ocxfYAUBqBHw1s0iiDMRCAIIEBX5fOsgSRI5AL~tplv-tiktokx-shrink-aq:360:360:q75.webp?dr=13023&amp;refresh_token=f9e83259&amp;x-expires=1787634000&amp;x-signature=BMoqSW9z9srl0siFDD1XKFMnMuk%3D&amp;t=bacd0480&amp;ps=d97f9a4f&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=feed_cover","duration":13,"play":"https:\\/\\/v19.tiktokcdn-eu.com\\/b5b53c308b5049234f6f3c19e0153cb5\\/6a8d2c2a\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/oQUAosyQXCrQjAFjgDpIk0fcJcIvA1fRzePDEi\\/?a=1233&amp;bti=M0BzOTg7QGo6OjZALnAjLTAzYCMxNDNg&amp;&amp;bt=536&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=PGQ0ZGZkODNkNGhmZGk4NUBpam95N2o5cjhrOzMzODczNEBfNV5eLzMyNmAxLzMwYDUtYSNsNmYxMmRzc3BhLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","wmplay":"https:\\/\\/v19.tiktokcdn-eu.com\\/b5b53c308b5049234f6f3c19e0153cb5\\/6a8d2c2a\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/oQUAosyQXCrQjAFjgDpIk0fcJcIvA1fRzePDEi\\/?a=1233&amp;bti=M0BzOTg7QGo6OjZALnAjLTAzYCMxNDNg&amp;&amp;bt=536&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=PGQ0ZGZkODNkNGhmZGk4NUBpam95N2o5cjhrOzMzODczNEBfNV5eLzMyNmAxLzMwYDUtYSNsNmYxMmRzc3BhLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","size":922114,"wm_size":0,"music":"","music_info":{"id":"7650389509992958727","title":"","play":"","cover":"","author":"","original":true,"duration":13,"album":""},"play_count":1998,"digg_count":93,"comment_count":20,"share_count":5,"download_count":0,"collect_count":8,"create_time":1782128538,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"is_top":0},{"video_id":"7644070339776924946","region":"VN","title":"\\u201cKho\\u1ea3nh kh\\u1eafc ngu ng\\u1ed1c nh\\u1ea5t c\\u1ee7a con ng\\u01b0\\u1eddi, \\u0111\\u00f3 ch\\u00ednh l\\u00e0 t\\u00ecnh y\\u00eau ch\\u01b0a k\\u1ecbp l\\u1edbn \\u0111\\u00e3 v\\u1ed9i \\u0111em khoe\\u201d","content_desc":[],"cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/c34ead70966647b08d7d9dbc4cb6ce02~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=a3087ec0&amp;x-expires=1788843600&amp;x-signature=QsGLJteq6HEhLpWrvoziZ7rg604%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","ai_dynamic_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/c34ead70966647b08d7d9dbc4cb6ce02~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=a3087ec0&amp;x-expires=1788843600&amp;x-signature=QsGLJteq6HEhLpWrvoziZ7rg604%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","origin_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/c34ead70966647b08d7d9dbc4cb6ce02~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=a3087ec0&amp;x-expires=1788843600&amp;x-signature=QsGLJteq6HEhLpWrvoziZ7rg604%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","duration":0,"play":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7646916762797345553.mp3","wmplay":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7646916762797345553.mp3","size":0,"wm_size":0,"music":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7646916762797345553.mp3","music_info":{"id":"7640409692435008263","title":"original sound - nhinccbamay188","play":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7646916762797345553.mp3","cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/ba621f0313ea7bb0037ac93becd800a4~tplv-tiktokx-cropcenter-q:1080:1080:q70.webp?dr=9608&amp;refresh_token=04a78e9f&amp;x-expires=1787634000&amp;x-signature=puhOATxq5CBSm7wAnPMWALBEn2M%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH","author":"Ekenn","original":true,"duration":18,"album":""},"play_count":784637,"digg_count":53984,"comment_count":127,"share_count":39030,"download_count":89,"collect_count":4878,"create_time":1779773825,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"images":["https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/c34ead70966647b08d7d9dbc4cb6ce02~tplv-photomode-image-v1:q70.webp?dr=1334&amp;refresh_token=7d595540&amp;x-expires=1788843600&amp;x-signature=A03ZesNB6S8GJhr5RDMmjY7p%2FJc%3D&amp;t=5897f7ec&amp;ps=b40d0ec8&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=image"],"is_top":0},{"video_id":"7643006700609408264","region":"VN","title":"\\ud83e\\ude76","content_desc":[],"cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oIYlP5dIAhoiAqF6Ea5HhAa3iADPRYAwBErAB~tplv-tiktokx-cropcenter-q:300:400:q70.jpeg?dr=9232&amp;refresh_token=8872ff8c&amp;x-expires=1787634000&amp;x-signature=6owL26SrumdBmn5bmN1C1onzfNk%3D&amp;t=bacd0480&amp;ps=933b5bde&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=cover","ai_dynamic_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/oIYlP5dIAhoiAqF6Ea5HhAa3iADPRYAwBErAB~tplv-tiktokx-origin.image?dr=9229&amp;refresh_token=266a2d51&amp;x-expires=1787634000&amp;x-signature=HawBfp1PdNUoknacfSFlFGXBetM%3D&amp;t=bacd0480&amp;ps=4f5296ae&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=dynamic_cover","origin_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-p-0037\\/ow8vLIFAiIYCQAVMzgrqtAoiBhnFaBahiYTER~tplv-tiktokx-shrink-aq:360:360:q75.webp?dr=13023&amp;refresh_token=99521b48&amp;x-expires=1787634000&amp;x-signature=eP%2F7fuvcmMiKe2LvmDD%2BCmUaegA%3D&amp;t=bacd0480&amp;ps=d97f9a4f&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;biz_tag=tt_video&amp;s=PUBLISH&amp;sc=feed_cover","duration":21,"play":"https:\\/\\/v19.tiktokcdn-eu.com\\/49bda222408a194fb7d5d7bf19ad86e7\\/6a8d2c32\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/ogIiqiEzEiiFAtVcAaQFnYrTssBWLYRaRhBvB\\/?a=1233&amp;bti=M0BzOTg7QGo6OjZALnAjLTAzYCMxNDNg&amp;&amp;bt=478&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=ZGQ2ODpnOjo5NzY4O2loNkBpanJ3NW05cjhwOzMzODczNEBgMy8tYDVfXjExNDNeX2FjYSNqM3BlMmRraDVhLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","wmplay":"https:\\/\\/v19.tiktokcdn-eu.com\\/49bda222408a194fb7d5d7bf19ad86e7\\/6a8d2c32\\/video\\/tos\\/alisg\\/tos-alisg-pve-0037c001\\/ogIiqiEzEiiFAtVcAaQFnYrTssBWLYRaRhBvB\\/?a=1233&amp;bti=M0BzOTg7QGo6OjZALnAjLTAzYCMxNDNg&amp;&amp;bt=478&amp;ft=g~Ocz728Qj_u9wwR7R5Cn.Cd8UGoZcA~z.hn5H6KJE&amp;mime_type=video_mp4&amp;rc=ZGQ2ODpnOjo5NzY4O2loNkBpanJ3NW05cjhwOzMzODczNEBgMy8tYDVfXjExNDNeX2FjYSNqM3BlMmRraDVhLS1kMTFzcw%3D%3D&amp;vvpl=1&amp;l=20260824134605441691BDF71FA4BB3B80&amp;btag=e00078000","size":1338795,"wm_size":0,"music":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7574349488857418513.mp3","music_info":{"id":"7574349480238107393","title":"original sound - vkhai.34","play":"https:\\/\\/sf16-ies-music-sg.tiktokcdn.com\\/obj\\/tiktok-obj\\/7574349488857418513.mp3","cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/defca9b2c6bdf9250acb930337bf4893~tplv-tiktokx-cropcenter-q:1080:1080:q70.webp?dr=9608&amp;refresh_token=ce673714&amp;x-expires=1787634000&amp;x-signature=wnRZNUnK4viip5VVoNHx1OUdYWQ%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH","author":".","original":true,"duration":21,"album":""},"play_count":37173,"digg_count":3896,"comment_count":38,"share_count":415,"download_count":0,"collect_count":183,"create_time":1779526174,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"is_top":0},{"video_id":"7640911599011728658","region":"VN","title":"\\ud83d\\ude16","content_desc":[],"cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/8e6260c807cc45d4ae665da25a6c75f5~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=8b73f2f4&amp;x-expires=1788843600&amp;x-signature=mIxa4zduDFM%2BnkgaUB37SroGSw4%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;sc=cover&amp;biz_tag=tt_photomode","ai_dynamic_cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/8e6260c807cc45d4ae665da25a6c75f5~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=8b73f2f4&amp;x-expires=1788843600&amp;x-signature=mIxa4zduDFM%2BnkgaUB37SroGSw4%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;sc=cover&amp;biz_tag=tt_photomode","origin_cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/8e6260c807cc45d4ae665da25a6c75f5~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=8b73f2f4&amp;x-expires=1788843600&amp;x-signature=mIxa4zduDFM%2BnkgaUB37SroGSw4%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;sc=cover&amp;biz_tag=tt_photomode","duration":0,"play":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646797532051311376.mp3","wmplay":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646797532051311376.mp3","size":0,"wm_size":0,"music":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646797532051311376.mp3","music_info":{"id":"7637489228137515784","title":"original sound - thoanh003","play":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7646797532051311376.mp3","cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/06ef075cf933c0a8b361abfe54189dd9~tplv-tiktokx-cropcenter-q:1080:1080:q70.webp?dr=9608&amp;refresh_token=e41d0123&amp;x-expires=1787634000&amp;x-signature=rGwD3lTXsQfmjk%2F3rmlbYFvpysI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH","author":"@X\\u00edu \\ud83d\\ude0d","original":true,"duration":28,"album":""},"play_count":45473,"digg_count":4673,"comment_count":14,"share_count":1074,"download_count":0,"collect_count":260,"create_time":1779038372,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"images":["https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/8e6260c807cc45d4ae665da25a6c75f5~tplv-photomode-image-v1:q70.webp?dr=1334&amp;refresh_token=fec0ff5b&amp;x-expires=1788843600&amp;x-signature=JMdPLMAtfXCT%2FGI9GligDAJMlDo%3D&amp;t=5897f7ec&amp;ps=b40d0ec8&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=image"],"is_top":0},{"video_id":"7637448834540424456","region":"VN","title":":&gt;","content_desc":[],"cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/97c8f456ff1f437e861174ea12aabe34~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=154fb488&amp;x-expires=1788843600&amp;x-signature=EwOCyl0UU8xAmD4rHwu2020Ba2A%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","ai_dynamic_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/97c8f456ff1f437e861174ea12aabe34~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=154fb488&amp;x-expires=1788843600&amp;x-signature=EwOCyl0UU8xAmD4rHwu2020Ba2A%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","origin_cover":"https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/97c8f456ff1f437e861174ea12aabe34~tplv-photomode-image-cover:480:0:q70.webp?dr=1350&amp;refresh_token=154fb488&amp;x-expires=1788843600&amp;x-signature=EwOCyl0UU8xAmD4rHwu2020Ba2A%3D&amp;t=5897f7ec&amp;ps=d5b8ac02&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;biz_tag=tt_photomode&amp;sc=cover","duration":0,"play":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7672249520744385288.mp3","wmplay":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7672249520744385288.mp3","size":0,"wm_size":0,"music":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7672249520744385288.mp3","music_info":{"id":"7600024906511731476","title":"original sound - chinguu102","play":"https:\\/\\/sf16-music.tiktokcdn-eu.com\\/obj\\/tiktok-obj\\/7672249520744385288.mp3","cover":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/81785fcaa2d164e3f091f5ee8649d87d~tplv-tiktokx-cropcenter-q:1080:1080:q70.webp?dr=9608&amp;refresh_token=522346d1&amp;x-expires=1787634000&amp;x-signature=pgkl2opfs8FpSoqQ0wj5QCXe22c%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH","author":"chingu102","original":true,"duration":45,"album":""},"play_count":235887,"digg_count":34318,"comment_count":65,"share_count":8128,"download_count":0,"collect_count":2268,"create_time":1778232133,"anchors":null,"anchors_extras":"","is_ad":false,"commerce_info":{"adv_promotable":false,"auction_ad_invited":false,"branded_content_type":0,"is_diversion_ad":0,"organic_log_extra":"{\\"req_id\\":\\"20260824134605441691BDF71FA4BB3B80\\"}","with_comment_filter_words":false},"commercial_video_info":"","item_comment_settings":0,"mentioned_users":"","author":{"id":"7549519262734943239","unique_id":"user_embongngo","nickname":"Hoai Thuong","avatar":"https:\\/\\/p19-common-sign.tiktokcdn-eu.com\\/tos-alisg-avt-0068\\/34c93ce3a261ba769293c58e9d06c423~tplv-tiktokx-cropcenter-q:300:300:q70.webp?dr=9605&amp;refresh_token=e75b09f4&amp;x-expires=1787634000&amp;x-signature=vIg8mQvcOpydh69YfyTJ0YYwcJI%3D&amp;t=223449c4&amp;ps=87d6e48a&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;sc=avatar&amp;s=PUBLISH"},"is_nff_or_nr":false,"images":["https:\\/\\/p16-common-sign.tiktokcdn-eu.com\\/tos-alisg-i-photomode-sg\\/97c8f456ff1f437e861174ea12aabe34~tplv-photomode-image-v1:q70.webp?dr=1334&amp;refresh_token=f09f82c8&amp;x-expires=1788843600&amp;x-signature=nUEpOaS1yTxjpNnWKaGuy6Jw0zI%3D&amp;t=5897f7ec&amp;ps=b40d0ec8&amp;shp=d05b14bd&amp;shcp=1d1a97fc&amp;idc=useast2b&amp;s=PUBLISH&amp;sc=image&amp;biz_tag=tt_photomode"],"is_top":0}],"cursor":"1778232132928","hasMore":false}}</pre><div class="json-formatter-container"></div></body></html>',
    },
    "startTimestamp": 1787550355291,
    "endTimestamp": 1787550367316,
    "version": "3.4.6",
}

FLARESOLVER_RESP_JSON: dict[str, Any] = {
    "status": "ok",
    "message": "Challenge not detected!",
    "solution": {
        "url": "https://www.tikwm.com/api/user/posts?unique_id=kittyasmr2&count=50&cursor=0",
        "status": 200,
        "response": {
            "code": 0,
            "msg": "success",
            "processed_time": 0.9642,
            "data": {
                "videos": [
                    {
                        "video_id": "7637253304178740500",
                        "region": "CL",
                        "title": "Esa amiga que solo hace videollamada para admirarse 🐥 créditos: jimenita #humor #comedia #Viral #kdramas #paratii ",
                        "content_desc": [
                            "Esa amiga que solo hace videollamada para admirarse 🐥 créditos: jimenita #humor #comedia #Viral #kdramas",
                            "#paratii ",
                        ],
                        "duration": 16,
                    }
                ],
                "cursor": "1745723767416",
                "hasMore": False,
            },
        },
        "headers": {
            "access-control-allow-credentials": "true",
            "access-control-allow-headers": "Content-Type,Content-Length,Accept-Encoding,X-Requested-with, Origin",
            "access-control-allow-methods": "POST,GET,OPTIONS,DELETE",
            "access-control-allow-origin": "*",
            "cf-cache-status": "DYNAMIC",
            "cf-ray": "9f8a6e819968f0-MIA",
            "content-encoding": "br",
            "content-type": "application/json",
            "date": "Fri, 08 May 2026 18:12:17 GMT",
            "nel": '{"report_to":"cf-nel","success_fraction":0.0,"max_age":604800}',
            "server": "cloudflare",
            "x-limit-request-remaining": "9995",
            "x-limit-request-reset": "20864",
        },
        "cookies": [
            {
                "name": "cf_clearance",
                "value": "m5B4ZLfY9b1yGWFI0mQHveDo7Jnb4e",
                "domain": ".tikwm.com",
                "path": "/",
                "expires": 1809798658.438918,
                "size": 417,
                "httpOnly": True,
                "secure": True,
                "session": False,
                "sameSite": "None",
                "priority": "Medium",
                "sameParty": False,
                "sourceScheme": "Secure",
                "sourcePort": 443,
                "partitionKey": "https://tikwm.com",
            }
        ],
        "userAgent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    },
    "startTimestamp": 1778263936203,
    "endTimestamp": 1778263939479,
    "version": "3.3.21",
}


def test_infer_content_type_html() -> None:
    assert _infer_content_type_from_body("<html>test</html>") == "text/html"


def test_infer_content_type_html_with_leading_whitespace() -> None:
    assert _infer_content_type_from_body("  \n <html>") == "text/html"


def test_infer_content_type_json_object() -> None:
    assert _infer_content_type_from_body('{"key": "value"}') == "application/json"


def test_infer_content_type_json_array() -> None:
    assert _infer_content_type_from_body("[1, 2, 3]") == "application/json"


def test_infer_content_type_empty_string() -> None:
    assert _infer_content_type_from_body("") == ""


def test_infer_content_type_only_whitespace() -> None:
    assert _infer_content_type_from_body("   \n\t  ") == ""


def test_parse_cookies_complete_cookie() -> None:
    cookies = [
        {
            "domain": ".example.com",
            "name": "session",
            "path": "/",
            "value": "abc123",
            "secure": True,
            "expires": int(time.time()) + 3600,
        }
    ]
    result = _parse_cookies(cookies)
    assert "session" in result
    assert result["session"].value == "abc123"
    assert result["session"]["domain"] == ".example.com"
    assert result["session"]["secure"] == "TRUE"
    assert int(result["session"]["max-age"]) > 0


def test_parse_cookies_missing_secure_and_expires() -> None:
    """Cookie without 'secure' and 'expires' must not raise KeyError."""
    cookies = [
        {
            "domain": ".example.com",
            "name": "test",
            "path": "/",
            "value": "xyz",
        }
    ]
    result = _parse_cookies(cookies)
    assert "test" in result
    assert result["test"].value == "xyz"
    assert result["test"]["secure"] == ""
    assert result["test"]["max-age"] == ""


def test_parse_cookies_secure_false() -> None:
    cookies = [
        {
            "domain": ".example.com",
            "name": "nosec",
            "path": "/",
            "value": "val",
            "secure": False,
        }
    ]
    result = _parse_cookies(cookies)
    assert result["nosec"]["secure"] == ""


def test_parse_cookies_expired_cookie() -> None:
    """An already-expired cookie should have max-age = 0."""
    cookies = [
        {
            "domain": ".example.com",
            "name": "old",
            "path": "/",
            "value": "stale",
            "expires": 1000000000,
        }
    ]
    result = _parse_cookies(cookies)
    assert result["old"]["max-age"] == "0"


def test_parse_cookies_empty_list() -> None:
    result = _parse_cookies([])
    assert len(result) == 0


# ---------------------------------------------------------------------------
# Solution.from_dict
# ---------------------------------------------------------------------------


def test_solution_from_dict_with_empty_headers() -> None:
    """Parsing the full FlareSolverr solution dict must not raise."""
    solution_data = FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"]
    solution = Solution.from_dict(solution_data)
    assert solution.status == 200
    assert str(solution.url) == "https://1337x.to/cat/Movies/1/"
    assert solution.content == '<html><head>\n<meta charset="utf></html>'
    assert len(solution.headers) == 0
    assert "cf_clearance" in solution.cookies


def test_solution_from_dict_cookies_parsed_correctly() -> None:
    solution_data = FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"]
    solution = Solution.from_dict(solution_data)
    morsel = solution.cookies["cf_clearance"]
    assert morsel.value == "KKW9gSBPiS8pWkenAaGd82lMQZwcCqSEALdTvs13Tf7QIdxHRN4NKdwhnut21rKA"
    assert morsel["domain"] == ".1337x.to"
    assert morsel["path"] == "/"
    assert morsel["secure"] == "TRUE"


def test_solution_from_dict_json_resp() -> None:
    solution = Solution.from_dict(FLARESOLVER_RESP_JSON["solution"])
    assert type(solution.content) is dict


async def test_flaresolverr_response_infers_html_from_empty_headers() -> None:
    """When FlareSolverr returns empty headers, content-type should be inferred from the body."""
    solution = Solution.from_dict(FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"])
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == "text/html"
    assert response.status == 200
    assert response.location is None


async def test_flaresolverr_response_reads_text() -> None:
    solution = Solution.from_dict(FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"])
    response = _FlareSolverrResponse.create(solution)
    text = await response.text()
    assert "<html>" in text


async def test_flaresolverr_response_from_json_resp() -> None:
    solution = Solution.from_dict(FLARESOLVER_RESP_JSON["solution"])
    response = _FlareSolverrResponse.create(solution)
    assert not response._text
    assert response.content_type == "application/json"
    assert response._get_content() == solution.content
    assert await response.json() == solution.content
    assert await response.text() == ""


async def test_flaresolverr_response_with_explicit_content_type() -> None:
    """When headers contain Content-Type, it should be used instead of inference."""
    solution_data = {
        **FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"],
        "headers": {"Content-Type": "application/json"},
        "response": '{"data": True}',
    }
    solution = Solution.from_dict(solution_data)
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == "application/json"


async def test_flaresolverr_response_empty_body_and_empty_headers() -> None:
    """Empty body + empty headers should result in empty content-type string."""
    solution_data = {
        **FLARESOLVERR_RESPONSE_EMPTY_HEADERS["solution"],
        "response": "",
    }
    solution = Solution.from_dict(solution_data)
    response = _FlareSolverrResponse.create(solution)
    assert response.content_type == ""


async def test_flaresolverr_response_from_json_resp_wrapped_in_html() -> None:
    solution = Solution.from_dict(FLARESOLVER_RESP_JSON_WRAPPED_IN_HTML["solution"])
    resp = _FlareSolverrResponse.create(solution)
    assert resp._text
    assert resp.content_type == "text/html"
    assert type(solution.content) is str
    data = await resp.json()
    assert type(data) is dict
    assert resp.content_type == "application/json"
    assert data == await resp.json()
    assert data is not await resp.json()
    assert type(solution.content) is dict
    del data["data"]
    assert data == {"code": 0, "msg": "success", "processed_time": 0.4496}
    assert data != await resp.json()
