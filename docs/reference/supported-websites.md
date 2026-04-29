---

description: These are the websites supported by Cyberdrop-DL
icon: globe-pointer
---
<!-- markdownlint-disable MD033 MD034 MD041 -->

# Supported Websites

For a full list of all supported sites, see [supported sites](#supported-sites)

## Password Protected Content Hosts

Cyberdrop-DL can download password protected files and folders from these hosts. User must include the password as a query parameter in the input URL, adding `?password=<URL_PASSWORD>` to it.

Example: `https://cyberfile.me/folder/xUGg?password=1234`

| Domain                                              |
| --------------------------------------------------- |
| GoFile                                              |
| Cyberfile                                           |
| Chevereto Sites (`JPG5`, `ImagePond.net`,`ImgLike`) |
| Iceyfile.com                                        |
| Transfer.it                                         |
| Koofr.eu                                            |
| Sites supported by Real-Debrid                      |

## Additional Content Hosts with Real-Debrid

Cyberdrop-DL has integration with Real-Debrid as download service to support additional hosts. In order to enable Real-Debrid, user must provide their API token inside the `authentication.yaml` file. You can get your API token from this URL (you must be logged in): [https://real-debrid.com/apitoken](https://real-debrid.com/apitoken)

Supported domains via Real-Debrid include `rapidgator`, `4shared.com`, `fikper.com`, `k2s`, `etc`. List of all supported domains can be found here (250+): [https://api.real-debrid.com/rest/1.0/hosts/domains](https://api.real-debrid.com/rest/1.0/hosts/domains)

{% hint style="info" %}
CDL will only use Real-Debrid for unsupported sites. To use it for a site that CDL supports, ex: `mega.nz`, you have to disable the `mega.nz` crawler. See: https://script-ware.gitbook.io/cyberdrop-dl/reference/configuration-options/global-settings/general#disable_crawlers
{% endhint %}

## Supported sites

List of sites supported by cyberdrop-dl-patched as of version 9.4.1.dev0

## 4chan

Primary URL: https://boards.4chan.org

Supported Domains: 4chan.*

### Supported paths
- Board: `/<board>`
- Thread: `/<board>/thread/<thread_id>`


## 8Muses

Primary URL: https://comics.8muses.com

Supported Domains: 8muses.*

### Supported paths
- Album: `/comics/album/...`


## AllPornComix

Primary URL: https://forum.allporncomix.com

Supported Domains: allporncomix.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## Anontransfer.com

Primary URL: https://anontransfer.com

Supported Domains: anontransfer.com

### Supported paths
- Direct Link: `/download-direct.php?dir=<file_id>&file=<filename>`,`/uploads/<file_id>/<filename>`
- File: `/d/<file_id>`
- Folder: `/f/<folder_uuid>`


## AnySex

Primary URL: https://anysex.com

Supported Domains: anysex.*

### Supported paths
- Album: `/photos/<album_id>/...`
- Photo Search: `/photos/search/...`
- Search: `/search/...`
- Video: `/video/<video_id>/...`


## ArchiveBate

Primary URL: https://www.archivebate.store

Supported Domains: archivebate.*

### Supported paths
- Video: `/watch/<video_id>`


## aShemaleTube

Primary URL: https://www.ashemaletube.com

Supported Domains: ashemaletube.*

### Supported paths
- Model: `/creators/...`,`/model/...`,`/pornstars/...`
- Playlist: `/playlists/...`
- User: `/profiles/...`
- Video: `/videos/...`


## Bandcamp

Primary URL: https://bandcamp.com

Supported Domains: bandcamp.*

### Supported paths
- Album: `/album/<slug>`
- Song: `/track/<slug>`

### Notes
- You can set 'CDL_BANDCAMP_FORMATS' env var to a comma separated list of formats to download (Ordered by preference) [Default = 'mp3-320,mp3,aac-hi,wav,flac,vorbis,aiff,alas']


## Beeg.com

Primary URL: https://beeg.com

Supported Domains: beeg.com

### Supported paths
- Video: `/<video_id>`,`/video/<video_id>`


## Bellazon

Primary URL: https://www.bellazon.com/main

Supported Domains: bellazon.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Invision


## BestPrettyGirl

Primary URL: https://bestprettygirl.com

Supported Domains: bestprettygirl.com

### Supported paths
- All Posts: `/posts/`
- Category: `/category/<category_slug>`
- Date Range: `...?after=<date>`,`...?before=<date&after=<date>`,`...?before=<date>`
- Post: `/<post_slug>/`
- Tag: `/tag/<tag_slug>`

### Notes
-

        For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

        `Date Range` can be combined with `Category`, `Tag` and `All Posts`.
        ex: To only download categories from a date range: ,
        `/category/<category_slug>?before=<date>`


## Box

Primary URL: https://www.box.com

Supported Domains: app.box.com

### Supported paths
- Embedded File or Folder: `app.box.com/embed/s?sh=<share_code>`,`app.box.com/embed_widget/s?sh=<share_code>`
- File or Folder: `app.box.com/s?sh=<share_code>`


## Bunkr

Primary URL: https://bunkr.site

Supported Domains: bunkr.*

### Supported paths
- Album: `/a/<album_id>`
- Direct Links:
- File: `/<slug>`,`/d/<slug>`,`/f/<slug>`
- Video: `/v/<slug>`


## Bunkr-Albums.io

Primary URL: https://bunkr-albums.io

Supported Domains: bunkr-albums.io

### Supported paths
- Search: `/?search=<query>`


## BuzzHeavier

Primary URL: https://buzzheavier.com

Supported Domains: buzzheavier.com

### Supported paths
- Direct Links:


## Camwhores.tv

Primary URL: https://www.camwhores.tv

Supported Domains: camwhores.tv

### Supported paths
- Category: `/categories/<name>/`
- Search: `/search/<query>/`
- Tag: `/tags/<name>/`
- Video: `/videos/<id>/<slug>`


## Catbox

Primary URL: https://catbox.moe

Supported Domains: files.catbox.moe, litter.catbox.moe

### Supported paths
- Direct Links:


## CelebForum

Primary URL: https://celebforum.to

Supported Domains: celebforum.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## Chevereto

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths
- Album: `/a/<id>`,`/a/<name>.<id>`,`/album/<id>`,`/album/<name>.<id>`
- Category: `/category/<name>`
- Direct Links:
- Image: `/image/<id>`,`/image/<name>.<id>`,`/img/<id>`,`/img/<name>.<id>`
- Profile: `/<user_name>`
- Video: `/video/<id>`,`/video/<name>.<id>`,`/videos/<id>`,`/videos/<name>.<id>`


## cloud.mail.ru

Primary URL: https://cloud.mail.ru

Supported Domains: cloud.mail.ru

### Supported paths
- Public files / folders: `/public/<web_path>`


## CloudflareStream

Primary URL: https://cloudflarestream.com

Supported Domains: cloudflarestream.com, videodelivery.net

### Supported paths
- Public Video: `/<video_uid>`,`/<video_uid>/iframe`,`/<video_uid>/watch`,`/embed/___.js?video=<video_uid>`
- Restricted Access Video: `/<jwt_access_token>`,`/<jwt_access_token>/iframe`,`/<jwt_access_token>/watch`,`/embed/___.js?video=<jwt_access_token>`


## Coomer

Primary URL: https://coomer.st

Supported Domains: coomer.party, coomer.st, coomer.su

### Supported paths
- Direct links: `/data/...`,`/thumbnail/...`
- Favorites: `/account/favorites/posts\|artists`,`/favorites?type=post\|artist`
- Individual Post: `/<service>/user/<user_id>/post/<post_id>`
- Model: `/<service>/user/<user_id>`
- Search: `/search?q=...`


## Cyberdrop

Primary URL: https://cyberdrop.cr

Supported Domains: cyberdrop.*, cyberdrop.cr, cyberdrop.me, cyberdrop.to, k1-cd.cdn.gigachad-cdn.ru

### Supported paths
- Album: `/a/<album_id>`
- Direct links: `/api/file/d/<file_id>`
- File: `/e/<file_id>`,`/f/<file_id>`


## Cyberfile

Primary URL: https://cyberfile.me

Supported Domains: cyberfile.*

### Supported paths
- Files: `/<file_id>`,`/<file_id>/<file_name>`
- Public Folders: `/folder/<folder_id>`,`/folder/<folder_id>/<folder_name>`
- Shared folders: `/shared/<share_key>`


## DesiVideo

Primary URL: https://desivideo.net

Supported Domains: desivideo.net

### Supported paths
- Search: `/search?s=<query>`
- Video: `/videos/<video_id>/...`


## DirectHttpFile

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths


## DirtyShip

Primary URL: https://dirtyship.com

Supported Domains: dirtyship.*

### Supported paths
- Category: `/category/<name>`
- Tag: `/tag/<name>`
- Video: `/<slug>`


## Discourse

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths
- Attachments: `/uploads/...`
- Topic: `/t/<topic_name>/<topic_id>`,`/t/<topic_name>/<topic_id>/<post_number>`

### Notes
- If the URL includes <post_number>, posts with a number lower that it won't be scraped


## DoodStream

Primary URL: https://doodstream.com

Supported Domains: all3do.com, d000d.com, do7go.com, dood.re, dood.yt, doodcdn.*, doodstream.*, doodstream.co, myvidplay.com, playmogo.com, vidply.com

### Supported paths
- Video: `/e/<video_id>`


## Dropbox

Primary URL: https://www.dropbox.com

Supported Domains: dropbox.*

### Supported paths
- File: `/s/...`,`/scl/fi/<link_key>?rlkey=...`,`/scl/fo/<link_key>/<secure_hash>?preview=<filename>&rlkey=...`
- Folder: `/scl/fo/<link_key>/<secure_hash>?rlkey=...`,`/sh/...`


## E-Hentai

Primary URL: https://e-hentai.org

Supported Domains: e-hentai.*

### Supported paths
- Album: `/g/...`
- File: `/s/...`


## E621

Primary URL: https://e621.net

Supported Domains: e621.net

### Supported paths
- Pools: `/pools/...`
- Post: `/posts/...`
- Tags: `/posts?tags=...`


## eFukt

Primary URL: https://efukt.com

Supported Domains: efukt.com

### Supported paths
- Gif: `/view.gif.php?id=<id>`
- Homepage: `/`
- Photo: `/pics/....`
- Series: `/series/<series_name>`
- Video: `/...`


## ePorner

Primary URL: https://www.eporner.com

Supported Domains: eporner.*

### Supported paths
- Categories: `/cat/...`
- Channels: `/channel/...`
- Gallery: `/gallery/...`
- Photo: `/photo/...`
- Pornstar: `/pornstar/...`
- Profile: `/profile/...`
- Search: `/search/...`
- Search Photos: `/search-photos/...`
- Video: `/<video_name>-<video-id>`,`/embed/<video_id>`,`/hd-porn/<video_id>`


## Erome

Primary URL: https://www.erome.com

Supported Domains: erome.*

### Supported paths
- Album: `/a/<album_id>`
- Profile: `/<name>`
- Search: `/search?q=<query>`


## Erome.fan

Primary URL: https://erome.fan

Supported Domains: erome.fan

### Supported paths
- Album: `/a/<album_id>`
- Profile: `/a/category/<name>`
- Search: `/search/<query>`


## EveriaClub

Primary URL: https://everia.club

Supported Domains: everia.club

### Supported paths
- All Posts: `/posts/`
- Category: `/category/<category_slug>`
- Date Range: `...?after=<date>`,`...?before=<date&after=<date>`,`...?before=<date>`
- Post: `/<post_slug>/`
- Tag: `/tag/<tag_slug>`

### Notes
-

        For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

        `Date Range` can be combined with `Category`, `Tag` and `All Posts`.
        ex: To only download categories from a date range: ,
        `/category/<category_slug>?before=<date>`


## F95Zone

Primary URL: https://f95zone.to

Supported Domains: f95zone.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## Fapello

Primary URL: https://fapello.su

Supported Domains: fapello.*

### Supported paths
- Individual Post: `/.../...`
- Model: `/...`


## Fileditch

Primary URL: https://fileditchfiles.me

Supported Domains: fileditch.*

### Supported paths
- Direct Links:


## Filester

Primary URL: https://filester.me

Supported Domains: filester.*

### Supported paths
- File: `/d/<slug>`
- Folder: `/f/<slug>`


## FilesVC

Primary URL: https://files.vc

Supported Domains: files.vc

### Supported paths
- Direct Links:


## Flickr

Primary URL: https://www.flickr.com

Supported Domains: flickr.*

### Supported paths
- Album: `/photos/<user_nsid>/albums/<photoset_id>/...`
- Photo: `/photos/<user_nsid>/<photo_id>/...`


## Forums.plex.tv

Primary URL: https://forums.plex.tv

Supported Domains: forums.plex.tv

### Supported paths
- Attachments: `/uploads/...`
- Topic: `/t/<topic_name>/<topic_id>`,`/t/<topic_name>/<topic_id>/<post_number>`

### Notes
- If the URL includes <post_number>, posts with a number lower that it won't be scraped


## FSIBlog

Primary URL: https://fsiblog5.com

Supported Domains: fsiblog.club, fsiblog.com, fsiblog1.club, fsiblog1.com, fsiblog2.club, fsiblog2.com, fsiblog3.club, fsiblog3.com, fsiblog4.club, fsiblog4.com, fsiblog5.club, fsiblog5.com

### Supported paths
- Posts: `/<category>/<title>`
- Search: `?s=<query>`


## FuckingFast

Primary URL: https://fuckingfast.co

Supported Domains: fuckingfast.co

### Supported paths
- Direct links: `/<file_id>`


## FuXXX

Primary URL: https://fuxxx.com

Supported Domains: fuxxx.com, fuxxx.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## Giphy

Primary URL: https://giphy.com

Supported Domains: giphy.*

### Supported paths
- Direct Link: `https://media*.giphy.com/media/<gif_id>`
- Gif: `/gifs/<slug>-<gif-id>`


## GirlsReleased

Primary URL: https://www.girlsreleased.com

Supported Domains: girlsreleased.*

### Supported paths
- Model: `/model/<model_id>/<model_name>`
- Set: `/set/<set_id>`
- Site: `/site/<site>`


## GoFile

Primary URL: https://gofile.io

Supported Domains: gofile.*

### Supported paths
- Direct link: `/download/<content_id>/<filename>`,`/download/web/<content_id>/<filename>`
- Folder / File: `/d/<content_id>`

### Notes
- Use `password` as a query param to download password protected folders
- ex: https://gofile.io/d/ABC654?password=1234


## GoogleDrive

Primary URL: https://drive.google.com

Supported Domains: docs.google, drive.google, drive.usercontent.google.com

### Supported paths
- Docs: `/document/d/<file_id>`
- Files: `/file/d/<file_id>`
- Folders: `/drive/folders/<folder_id>`,`/embeddedfolderview/<folder_id>`
- Sheets: `/spreadsheets/d/<file_id>`
- Slides: `/presentation/d/<file_id>`

### Notes
- You can download sheets, slides and docs in a custom format by using it as a query param.
ex: https://docs.google.com/document/d/1ZzEzJbemBMPm46O2q5VcGNoPbqDu9AhhUc2djQbvbTY?format=ods
Valid Formats:

document:
  - docx (default)
  - epub
  - md
  - odt
  - pdf
  - rtf
  - txt
  - zip

presentation:
  - odp
  - pptx (default)

spreadsheets:
  - csv
  - html
  - ods
  - tsv
  - xslx (default)


## GooglePhotos

Primary URL: https://photos.google.com

Supported Domains: photos.app.goo.gl, photos.google.com

### Supported paths
- Album: `/share/<album_id>`
- Photo: `/album/<album_id>/photo/<photo_id>`

### Notes
- Only downloads 'optimized' images, NOT original quality
- Can NOT download videos


## GUpload

Primary URL: https://gupload.xyz

Supported Domains: gupload.*

### Supported paths
- Video: `/data/e/<video_id>`


## HClips

Primary URL: https://hclips.com

Supported Domains: hclips.com, hclips.tube, privatehomeclips.com, privatehomeclips.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## HDZog

Primary URL: https://hdzog.com

Supported Domains: hdzog.com, hdzog.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## Hianime

Primary URL: https://hianime.to

Supported Domains: aniwatch.to, aniwatchtv.to, hianime.to, zoro.to

### Supported paths
- Anime: `/<name>-<anime_id>`
- Episode: `/<name>-<anime_id>?ep=<episode_id>`,`/watch/<name>-<anime_id>?ep=<episode_id>`

### Notes
- You can select the language to be downloaded by using a 'lang' query param. Valid options: 'sub' or 'dub'. Default: 'sub'If the chosen language is not available, CDL will use the first one available


## Hitomi.la

Primary URL: https://hitomi.la

Supported Domains: hitomi.la

### Supported paths
- Collection: `/artist/...`,`/character/...`,`/group/...`,`/series/...`,`/tag/...`,`/type/...`
- Gallery: `/anime/...`,`/cg/...`,`/doujinshi/...`,`/galleries/...`,`/gamecg/...`,`/imageset/...`,`/manga/...`,`/reader/...`
- Search: `/search.html?<query>`


## HotLeaksTV

Primary URL: https://hotleaks.tv

Supported Domains: hotleaks.tv

### Supported paths
- Model: `/<model_id>`
- Video: `/<model_id>/video/<video_id>`


## HotLeakVip

Primary URL: https://hotleak.vip

Supported Domains: hotleak.vip

### Supported paths
- Model: `/<model_id>`
- Video: `/<model_id>/video/<video_id>`


## HotMovs

Primary URL: https://hotmovs.com

Supported Domains: hotmovs.com, hotmovs.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## HotPic

Primary URL: https://hotpic.cc

Supported Domains: 2385290.xyz, hotpic.*

### Supported paths
- Album: `/album/...`
- Image: `/i/...`


## Iceyfile

Primary URL: https://iceyfile.com

Supported Domains: iceyfile.*

### Supported paths
- Files: `/<file_id>`,`/<file_id>/<file_name>`
- Public Folders: `/folder/<folder_id>`,`/folder/<folder_id>/<folder_name>`
- Shared folders: `/shared/<share_key>`


## ImageBam

Primary URL: https://www.imagebam.com

Supported Domains: imagebam.*

### Supported paths
- Gallery: `/gallery/<id>`
- Gallery or Image: `/view/<id>`
- Image: `/image/<id>`,`images<x>.imagebam.com/<id>`
- Thumbnails: `thumbs<x>.imagebam.com/<id>`


## ImagePond

Primary URL: https://imagepond.net

Supported Domains: imagepond.net

### Supported paths
- Album: `/a/<slug>`
- Direct links: `/media/<slug>`
- Image / Video / Archive: `/i/<slug>`,`/image/<slug>`,`/img/<slug>`,`/video/<slug>`,`/videos/<slug>`
- User: `/<user_name>`,`/user/<user_name>`


## ImageVenue

Primary URL: https://www.imagevenue.com

Supported Domains: imagevenue.*

### Supported paths
- Image: `/<image_id>`,`/img.php?image=<image_id>`,`/view/o?i=<image_id>`
- Thumbnail: `cdn-thumbs.imagevenue.com/.../<image_id>_t.jpg`


## ImgBB

Primary URL: https://ibb.co

Supported Domains: ibb.co, imgbb.co

### Supported paths
- Album: `/album/<album_id>`
- Image: `/<image_id>`
- Profile: `<user_name>.imgbb.co/`


## ImgBox

Primary URL: https://imgbox.com

Supported Domains: imgbox.*

### Supported paths
- Album: `/g/...`
- Direct Links:
- Image: `/...`


## ImgLike

Primary URL: https://imglike.com

Supported Domains: imglike.com

### Supported paths
- Album: `/a/<id>`,`/a/<name>.<id>`,`/album/<id>`,`/album/<name>.<id>`
- Category: `/category/<name>`
- Direct Links:
- Image: `/image/<id>`,`/image/<name>.<id>`,`/img/<id>`,`/img/<name>.<id>`
- Profile: `/<user_name>`
- Video: `/video/<id>`,`/video/<name>.<id>`,`/videos/<id>`,`/videos/<name>.<id>`


## Imgur

Primary URL: https://imgur.com

Supported Domains: imgur.*

### Supported paths
- Album: `/a/<album_id>`
- Direct links: `https://i.imgur.com/<image_id>.<ext>`
- Gallery: `/gallery/<slug>-<album_id>`
- Image: `/<image_id>`,`/download/<image_id>`


## Imx.to

Primary URL: https://imx.to

Supported Domains: imx.to

### Supported paths
- Gallery: `/g/<gallery_id>`
- Image: `/i/...`,`/u/i/...`
- Thumbnail: `/t/...`,`/u/t/`


## IncestFlix

Primary URL: https://www.incestflix.com

Supported Domains: incestflix.*

### Supported paths
- Tag: `/tag/...`
- Video: `/watch/...`


## InPorn

Primary URL: https://inporn.com

Supported Domains: inporn.com, inporn.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## JPG5

Primary URL: https://jpg6.su

Supported Domains: host.church, jpeg.pet, jpg.church, jpg.fish, jpg.fishing, jpg.homes, jpg.pet, jpg1.su, jpg2.su, jpg3.su, jpg4.su, jpg5.su, jpg6.su, jpg7.cr, selti-delivery.ru

### Supported paths
- Album: `/a/<id>`,`/a/<name>.<id>`,`/album/<id>`,`/album/<name>.<id>`
- Category: `/category/<name>`
- Direct Links:
- Image: `/image/<id>`,`/image/<name>.<id>`,`/img/<id>`,`/img/<name>.<id>`
- Profile: `/<user_name>`


## Kemono

Primary URL: https://kemono.cr

Supported Domains: kemono.cr, kemono.party, kemono.su

### Supported paths
- Direct links: `/data/...`,`/thumbnail/...`
- Discord Server: `/discord/<server_id>`
- Discord Server Channel: `/discord/server/<server_id>/<channel_id>#...`
- Favorites: `/account/favorites/posts\|artists`,`/favorites?type=post\|artist`
- Individual Post: `/<service>/user/<user_id>/post/<post_id>`
- Model: `/<service>/user/<user_id>`
- Search: `/search?q=...`


## Koofr

Primary URL: https://koofr.eu

Supported Domains: k00.fr, koofr.eu, koofr.net

### Supported paths
- Public Share: `/links/<content_id>`,`https://k00.fr/<short_id>`


## LeakedModels

Primary URL: https://leakedmodels.com/forum

Supported Domains: leakedmodels.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## LeakedZone

Primary URL: https://leakedzone.com

Supported Domains: leakedzone.*

### Supported paths
- Model: `/<model_id>`
- Video: `/<model_id>/video/<video_id>`


## Luscious

Primary URL: https://members.luscious.net

Supported Domains: luscious.*

### Supported paths
- Album: `/albums/...`


## LuxureTV

Primary URL: https://luxuretv.com

Supported Domains: luxuretv.*

### Supported paths
- Search: `/searchgate/videos/<search>/...`
- Video: `/videos/<name>-<id>.html`


## Masahub

Primary URL: https://masahub.com

Supported Domains: lol49.com, masa49.com, masafun.net, masahub.com, masahub2.com, vido99.com

### Supported paths
- Search: `?s=<query>`
- Videos: `/title`


## Mediafire

Primary URL: https://www.mediafire.com

Supported Domains: mediafire.*

### Supported paths
- File: `/file/<quick_key>`,`?<quick_key>`
- Folder: `/folder/<folder_key>`


## Megacloud

Primary URL: https://megacloud.blog

Supported Domains: megacloud.*

### Supported paths
- Embed v3: `/embed-2/v3`


## MegaNz

Primary URL: https://mega.nz

Supported Domains: mega.co.nz, mega.io, mega.nz

### Supported paths
- File: `/!#<file_id>!<share_key>`,`/file/<file_id>#<share_key>`,`/folder/<folder_id>#<share_key>/file/<file_id>`
- Folder: `/F!#<folder_id>!<share_key>`,`/folder/<folder_id>#<share_key>`
- Subfolder: `/folder/<folder_id>#<share_key>/folder/<subfolder_id>`

### Notes
- Downloads can not be resumed. Partial downloads will always be deleted and new downloads will start over


## MissAV

Primary URL: https://missav.ws

Supported Domains: missav.*

### Supported paths
- Genres: `/genres/<genre>`
- Labels: `/labels/<label>`
- Makers: `/makers/<maker>`
- Search: `/search/<search>`
- Tags: `/tags/<tag>`
- Video: `/...`


## MixDrop

Primary URL: https://mixdrop.sb

Supported Domains: m1xdrop.*, mixdrop.*, mxdrop.*

### Supported paths
- File: `/e/<file_id>`,`/f/<file_id>`


## Motherless

Primary URL: https://motherless.com

Supported Domains: motherless.*

### Supported paths
- Group: `/g/<group_name>`,`/gi/<image>`,`/gv/<video>`
- Image: `/...`
- User: `/f/...`,`/u/...`
- Video: `pending`

### Notes
- Galleries are NOT supported


## MyDesi

Primary URL: https://lolpol.com

Supported Domains: fry99.com, lolpol.com, mydesi.net

### Supported paths
- Search: `/search/<query>`
- Videos: `/title`


## Nekohouse

Primary URL: https://nekohouse.su

Supported Domains: nekohouse.*

### Supported paths
- Direct links: `/(data|thumbnails)/...`
- Individual Post: `/<service>/user/<user_id>/post/<post_id>`
- Model: `/<service>/user/<user_id>`


## nHentai

Primary URL: https://nhentai.net

Supported Domains: nhentai.net

### Supported paths
- Collections: `artist`,`character`,`favorites`,`group`,`parody`,`search`,`tag`
- Gallery: `/g/<gallery_id>`


## NoodleMagazine

Primary URL: https://noodlemagazine.com

Supported Domains: noodlemagazine.*

### Supported paths
- Search: `/video/<search_query>`
- Video: `/watch/<video_id>`


## nsfw.xxx

Primary URL: https://nsfw.xxx

Supported Domains: nsfw.xxx

### Supported paths
- Category: `/category/<name>`
- Post: `/post/<id>`
- Search: `/search?q=<query>`
- Subreddit: `/r/<subreddit>`
- User: `/user/<username>`


## NudoStar

Primary URL: https://nudostar.com/forum

Supported Domains: nudostar.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## NudoStarTV

Primary URL: https://nudostar.tv

Supported Domains: nudostar.tv

### Supported paths
- Model: `/models/...`


## ok.ru

Primary URL: https://ok.ru

Supported Domains: odnoklassniki.ru, ok.ru

### Supported paths
- Channel: `/profile/<username>/c<channel_id>`,`/video/c<channel_id>`
- Video: `/video/<video_id>`


## OmegaScans

Primary URL: https://omegascans.org

Supported Domains: omegascans.*

### Supported paths
- Chapter: `/series/.../...`
- Direct Links:
- Series: `/series/...`


## OneDrive

Primary URL: https://onedrive.com

Supported Domains: 1drv.ms, onedrive.live.com

### Supported paths
- Access Link: `https://onedrive.live.com/?authkey=<KEY>&id=<ID>&cid=<CID>`
- Share Link (anyone can access): `https://1drv.ms/b/<KEY>`,`https://1drv.ms/f/<KEY>`,`https://1drv.ms/t/<KEY>`,`https://1drv.ms/u/<KEY>`


## OnePace

Primary URL: https://onepace.net

Supported Domains: onepace.net

### Supported paths
- All episodes: `/watch`


## OwnCloud

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths
- Public Share: `/s/<share_token>`


## Patreon

Primary URL: https://www.patreon.com

Supported Domains: patreon.*

### Supported paths
- Creator: `/<creator>`,`/cw/<creator>`
- Post: `/posts/<slug>`


## pCloud

Primary URL: https://www.pcloud.com

Supported Domains: e.pc.cd, pc.cd, pcloud.*

### Supported paths
- Public File or folder: `?code=<share_code>`,`e.pc.cd/<short_code>`,`u.pc.cd/<short_code>`


## PimpAndHost

Primary URL: https://pimpandhost.com

Supported Domains: pimpandhost.*

### Supported paths
- Album: `/album/...`
- Image: `/image/...`


## PimpBunny

Primary URL: https://pimpbunny.com

Supported Domains: pimpbunny.com

### Supported paths
- Album: `/albums/<album_name>`
- Category: `/categories/<category>`
- Model Albums: `/albums/models/<model_name>`
- Models: `/onlyfans-models/<model_name>`
- Tag: `/tags/<tag>`
- Videos: `/videos/...`


## PixelDrain

Primary URL: https://pixeldrain.com

Supported Domains: pd.1drv.eu.org, pd.cybar.xyz, pixeldra.in, pixeldrain.biz, pixeldrain.com, pixeldrain.dev, pixeldrain.net, pixeldrain.nl, pixeldrain.tech

### Supported paths
- File: `/api/file/<file_id>`,`/l/<list_id>#item=<file_index>`,`/u/<file_id>`
- Filesystem: `/api/filesystem/<path>...`,`/d/<id>`
- Folder: `/api/list/<list_id>`,`/l/<list_id>`

### Notes
- text files will not be downloaded but their content will be parsed for URLs


## PixHost

Primary URL: https://pixhost.to

Supported Domains: pixhost.org, pixhost.to

### Supported paths
- Gallery: `/gallery/<gallery_id>`
- Image: `/show/<image_id>`
- Thumbnail: `/thumbs/..`


## Pkmncards

Primary URL: https://pkmncards.com

Supported Domains: pkmncards.*

### Supported paths
- Card: `/card/...`
- Series: `/series/...`
- Set: `/set/...`


## PMVHaven

Primary URL: https://pmvhaven.com

Supported Domains: pmvhaven.*

### Supported paths
- Playlist: `/playlists/...`
- Search results: `/search/...`
- Users: `/profile/...`,`/users/...`
- Video: `/video/...`


## PornHub

Primary URL: https://www.pornhub.com

Supported Domains: pornhub.*

### Supported paths
- Album: `/album/...`
- Channel: `/channel/...`
- Gif: `/gif/...`
- Photo: `/photo/...`
- Playlist: `/playlist/...`
- Profile: `/model/...`,`/pornstar/...`,`/user/...`
- Video: `/embed/<video_id>`,`/view_video.php?viewkey=<video_id>`


## PornPics

Primary URL: https://pornpics.com

Supported Domains: pornpics.*

### Supported paths
- Categories: `/categories/....`
- Channels: `/channels/...`
- Direct Links:
- Gallery: `/galleries/...`
- Pornstars: `/pornstars/...`
- Search: `/?q=<query>`
- Tags: `/tags/...`


## Porntrex

Primary URL: https://www.porntrex.com

Supported Domains: porntrex.*

### Supported paths
- Album: `/albums/...`
- Category: `/categories/...`
- Model: `/models/...`
- Playlist: `/playlists/...`
- Search: `/search/...`
- Tag: `/tags/...`
- User: `/members/...`
- Video: `/video/...`


## PornZog

Primary URL: https://pornzog.com

Supported Domains: pornzog.*

### Supported paths
- Video: `/video/...`


## PostImg

Primary URL: https://postimg.cc

Supported Domains: postimages.org, postimg.cc, postimg.org

### Supported paths
- Album: `/gallery/<album_id>/...`
- Direct links: `i.postimg.cc/<image_id>/...`
- Image: `/<image_id>/...`


## Ranoz.gg

Primary URL: https://ranoz.gg

Supported Domains: qiwi.gg, ranoz.gg

### Supported paths
- File: `/d/<file_id>`,`/file/<file_id>`


## RealBooru

Primary URL: https://realbooru.com

Supported Domains: realbooru.*

### Supported paths
- File: `?id=...`
- Tags: `?tags=...`


## RealDebrid

Primary URL: https://real-debrid.com

Supported Domains: real-debrid.*

### Supported paths


## RedGifs

Primary URL: https://www.redgifs.com

Supported Domains: redgifs.*

### Supported paths
- Embeds: `/ifr/<gif_id>`
- Gif: `/watch/<gif_id>`
- Image: `/i/<image_id>`
- User: `/users/<user>`


## Rootz.so

Primary URL: https://www.rootz.so

Supported Domains: rootz.so

### Supported paths
- File: `/d/<file_id>`,`/file/<file_id>`


## Rule34Vault

Primary URL: https://rule34vault.com

Supported Domains: rule34vault.*

### Supported paths
- Playlist: `/playlists/view/...`
- Post: `/post/...`
- Tag: `/...`


## Rule34Video

Primary URL: https://rule34video.com

Supported Domains: rule34video.*

### Supported paths
- Category: `/categories/<name>`
- Members: `/members/<member_id>`
- Model: `/models/<name>`
- Search: `/search/<query>`
- Tag: `/tags/<name>`
- Video: `/video/<id>/<slug>`


## Rule34XXX

Primary URL: https://rule34.xxx

Supported Domains: rule34.xxx

### Supported paths
- File: `?id=...`
- Tag: `?tags=...`


## Rule34XYZ

Primary URL: https://rule34.xyz

Supported Domains: rule34.xyz

### Supported paths
- Playlist: `/playlists/view/...`
- Post: `/post/...`
- Tag: `/...`


## Rumble

Primary URL: https://rumble.com

Supported Domains: rumble.*

### Supported paths
- Channel: `/c/<name>`
- Embed: `/embed/<video_id>`
- User: `/user/<name>`
- Video: `<video_id>-<video-title>.html`


## Scrolller

Primary URL: https://scrolller.com

Supported Domains: scrolller.*

### Supported paths
- Subreddit: `/r/...`


## SendNow

Primary URL: https://send.now

Supported Domains: send.now

### Supported paths
- Direct Links:


## SendVid

Primary URL: https://sendvid.com

Supported Domains: sendvid.*

### Supported paths
- Direct Links:
- Embeds: `/embed/...`
- Videos: `/...`


## Sex.com

Primary URL: https://sex.com

Supported Domains: sex.*

### Supported paths
- Shorts Profiles: `/shorts/<profile>`


## SocialMediaGirls

Primary URL: https://forums.socialmediagirls.com

Supported Domains: socialmediagirls.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## SpankBang

Primary URL: https://spankbang.com

Supported Domains: spankbang.*

### Supported paths
- Playlist: `/<playlist_id>/playlist/...`
- Profile: `/profile/<user>`,`/profile/<user>/videos`
- Video: `/<video_id>/embed`,`/<video_id>/video`,`/play/<video_id>`,`<playlist_id>-<video_id>/playlist/...`


## Streamable

Primary URL: https://streamable.com

Supported Domains: streamable.*

### Supported paths
- Video: `/...`


## Streamtape

Primary URL: https://streamtape.com

Supported Domains: streamtape.com

### Supported paths
- Player: `/e/<video_id>`
- Videos: `/v/<video_id>`


## TabooTube

Primary URL: https://www.tabootube.xxx

Supported Domains: tabootube.*

### Supported paths
- Video: `/video/...`


## ThisVid

Primary URL: https://thisvid.com

Supported Domains: thisvid.*

### Supported paths
- Albums: `/albums/<album_name>`
- Categories: `/categories/<name>`
- Image: `/albums/<album_name>/<image_name>`
- Members: `/members/<member_id>`
- Search: `/search/?q=<query>`
- Tags: `/tags/<name>`
- Videos: `/videos/<slug>`


## ThotHub

Primary URL: https://thothub.to

Supported Domains: thothub.*

### Supported paths
- Album: `/albums/<id>/<name>`
- Image: `/get_image/...`
- Video: `/videos/<id>/<slug>`


## TikTok

Primary URL: https://www.tiktok.com

Supported Domains: tiktok.*

### Supported paths
- Photo: `/@<user>/photo/<photo_id>`
- User: `/@<user>`
- Video: `/@<user>/video/<video_id>`


## TitsInTops

Primary URL: https://titsintops.com/phpBB2

Supported Domains: titsintops.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## TNAFlix

Primary URL: https://www.tnaflix.com

Supported Domains: tnaflix.*

### Supported paths
- Channel: `/channel/...`
- Profile: `/profile/...`
- Search: `/search?what=<query>`
- Video: `/<category>/<title>/video<video_id>`


## Tokyomotion

Primary URL: https://www.tokyomotion.net

Supported Domains: tokyomotion.*

### Supported paths
- Albums: `/album/<album_id>`,`/user/<user>/albums/`
- Photo: `/photo/<photo_id>`,`/user/<user>/favorite/photos`
- Playlist: `/user/<user>/favorite/videos`
- Profiles: `/user/<user>`
- Search Results: `/search?...`
- Video: `/video/<video_id>`


## Toonily

Primary URL: https://toonily.com

Supported Domains: toonily.*

### Supported paths
- Chapter: `/serie/<name>/chapter-<chapter-id>`
- Serie: `/serie/<name>`


## Tranny.One

Primary URL: https://www.tranny.one

Supported Domains: tranny.one

### Supported paths
- Album: `/pics/album/<album_id>`
- Pornstars: `/pornstar/<model_id>/<model_name>`
- Search: `/search/<search_query>`
- Video: `/view/<video_id>`


## Transfer.it

Primary URL: https://transfer.it

Supported Domains: transfer.it

### Supported paths
- Transfer: `/t/<transfer_id>`


## TransFlix

Primary URL: https://transflix.net

Supported Domains: transflix.*

### Supported paths
- Search: `/search/?q=<query>`
- Video: `/video/<name>-<video_id>`


## TubePornClassic

Primary URL: https://tubepornclassic.com

Supported Domains: tubepornclassic.com, tubepornclassic.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## TurboVid

Primary URL: https://turbovid.cr

Supported Domains: saint.to, saint2.cr, saint2.su, turbo.cr, turbovid.cr

### Supported paths
- Album: `/a/<album_id>`
- Direct links: `/data/...`
- Search: `library?q=<query>`
- Video: `/d/<file_id>`,`/embed/<file_id>`,`/v/<file_id>`


## Twitch

Primary URL: https://www.twitch.tv

Supported Domains: twitch.*

### Supported paths
- Clip: `/<user>/clip/<slug>`,`/embed?clip=<slug>`,`https://clips.twitch.tv/<slug>`
- Collection: `/collections/<collection_id>`
- VOD: `/<user>/v/<vod_id>`,`/video/<vod_id>`,`/videos/<vod_id>`,`?video=<vod_id>`


## Twitter

Primary URL: https://x.com

Supported Domains: twitter.com, x.com

### Supported paths
- Tweet: `/<handle>/status/<tweet_id>`


## TwitterImages

Primary URL: https://twimg.com

Supported Domains: twimg.*

### Supported paths
- Photo: `/...`


## TWPornStars

Primary URL: https://www.twpornstars.com

Supported Domains: indiantw.com, twanal.com, twgaymuscle.com, twgays.com, twlesbian.com, twmilf.com, twonfans.com, twpornstars.com, twteens.com, twtiktoks.com

### Supported paths
- Photo: `/...`


## TXXX

Primary URL: https://txxx.com

Supported Domains: txxx.com, txxx.tube, videotxxx.com, videotxxx.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## Upload.ee

Primary URL: https://www.upload.ee

Supported Domains: upload.ee

### Supported paths
- File: `/files/<file_id>`


## UPornia

Primary URL: https://upornia.com

Supported Domains: upornia.com, upornia.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## Vidara

Primary URL: https://vidara.to

Supported Domains: stmix.io, streamix.so, vidara.so, vidara.to, xca.cymru

### Supported paths
- Video: `/e/<video_id>`


## ViperGirls

Primary URL: https://vipergirls.to

Supported Domains: viper.click, vipergirls.to

### Supported paths
- Threads: `/goto/<post_id>`,`/posts/<post_id>`,`/threads/<thread_name>`


## Vipr.im

Primary URL: https://vipr.im

Supported Domains: vipr.im

### Supported paths
- Direct Image: `/i/.../<slug>`
- Image: `/<id>`
- Thumbnail: `/th/.../<slug>`


## VJav

Primary URL: https://vjav.com

Supported Domains: vjav.com, vjav.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## Voe.sx

Primary URL: https://voe.sx

Supported Domains: alejandrocenturyoil.com, diananatureforeign.com, heatherwholeinvolve.com, jennifercertaindevelopment.com, jilliandescribecompany.com, jonathansociallike.com, mariatheserepublican.com, maxfinishseveral.com, nathanfromsubject.com, richardsignfish.com, robertordercharacter.com, sarahnewspaperbeat.com, voe.sx

### Supported paths
- Embed: `/e/video_id`


## VoyeurHit

Primary URL: https://voyeurhit.com

Supported Domains: voyeurhit.com, voyeurhit.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## VSCO

Primary URL: https://vsco.co

Supported Domains: vsco.*

### Supported paths
- Gallery: `/<user>/gallery`
- Media: `/<user>/media/<media_id>`,`/<user>/video/<media_id>`


## VXXX

Primary URL: https://vxxx.com

Supported Domains: vxxx.com, vxxx.tube

### Supported paths
- Video: `/video-<video-id>`


## WeTransfer

Primary URL: https://wetransfer.com

Supported Domains: we.tl, wetransfer.com

### Supported paths
- Direct links: `download.wetransfer.com/...`
- Public link: `wetransfer.com/downloads/<file_id>/<security_hash>`
- Share Link: `wetransfer.com/downloads/<file_id>/<recipient_id>/<security_hash>`
- Short Link: `we.tl/<short_file_id>`


## WordPressHTML

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths
- All Posts: `/posts/`
- Category: `/category/<category_slug>`
- Date Range: `...?after=<date>`,`...?before=<date&after=<date>`,`...?before=<date>`
- Post: `/<post_slug>/`
- Tag: `/tag/<tag_slug>`

### Notes
-

        For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

        `Date Range` can be combined with `Category`, `Tag` and `All Posts`.
        ex: To only download categories from a date range: ,
        `/category/<category_slug>?before=<date>`


## WordPressMedia

Primary URL: ::GENERIC CRAWLER::

Supported Domains:

### Supported paths
- All Posts: `/posts/`
- Category: `/category/<category_slug>`
- Date Range: `...?after=<date>`,`...?before=<date&after=<date>`,`...?before=<date>`
- Post: `/<post_slug>/`
- Tag: `/tag/<tag_slug>`

### Notes
-

        For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

        `Date Range` can be combined with `Category`, `Tag` and `All Posts`.
        ex: To only download categories from a date range: ,
        `/category/<category_slug>?before=<date>`


## Xasiat

Primary URL: https://www.xasiat.com

Supported Domains: xasiat.*

### Supported paths
- Album: `/albums/<id>/<name>`
- Images: `/get_image/...`
- Videos: `/videos/<id>/<name>`


## XBunker

Primary URL: https://xbunker.nu

Supported Domains: xbunker.*

### Supported paths
- Attachments: `/(attachments\|data\|uploads)/...`
- Threads: `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`,`/goto/<post_id>`,`/posts/<post_id>`

### Notes
- base crawler: Xenforo


## XGroovy

Primary URL: https://xgroovy.com

Supported Domains: xgroovy.*

### Supported paths
- Channel: `/<category>/channels/...`,`/channels/...`
- Gif: `/<category>/gifs/<gif_id>/...`,`/gifs/<gif_id>/...`
- Images: `/<category>/photos/<photo_id>/...`,`/photos/<photo_id>/...`
- Pornstar: `/<category>/pornstars/<pornstar_id>/...`,`/pornstars/<pornstar_id>/...`
- Search: `/<category>/search/...`,`/search/...`
- Tag: `/<category>/tags/...`,`/tags/...`
- Video: `/<category>/videos/<video_id>/...`,`/videos/<video_id>/...`


## xHamster

Primary URL: https://xhamster.com

Supported Domains: xhamster.*

### Supported paths
- Creator: `/creators/<creator_name>`
- Creator Galleries: `/creators/<creator_name>/photos`
- Creator Videos: `/creators/<creator_name>/exclusive`
- Gallery: `/photos/gallery/<gallery_name_or_id>`
- User: `/users/<user_name>`,`/users/profiles/<user_name>`
- User Galleries: `/users/<user_name>/photos`
- User Videos: `/users/<user_name>/videos`
- Video: `/videos/<title>`


## XMegaDrive

Primary URL: https://www.xmegadrive.com

Supported Domains: xmegadrive.*

### Supported paths
- Albums: `/albums/<album_name>`
- Categories: `/categories/<name>`
- Image: `/albums/<album_name>/<image_name>`
- Members: `/members/<member_id>`
- Search: `/search/?q=<query>`
- Tags: `/tags/<name>`
- Videos: `/videos/<slug>`


## XMilf

Primary URL: https://xmilf.com

Supported Domains: xmilf.com, xmilf.tube

### Supported paths
- Video: `/embed/<video_id>/...`,`/videos/<video_id>/...`


## xVideos

Primary URL: https://www.xvideos.com

Supported Domains: xv-ru.com, xvideos-ar.com, xvideos-india.com, xvideos.com, xvideos.es

### Supported paths
- Account: `/<channel_name>`,`/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>`
- Account Photos: `/<channel_name>#_tabPhotos`,`/<channel_name>/photos/...`,`/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#_tabPhotos`,`/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>/photos/...`
- Account Quickies: `/<channel_name>#quickies`,`/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#quickies`
- Account Videos: `/<channel_name>#_tabVideos`,`/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#_tabVideos`
- Video: `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles#quickies/(a\|h\|v)/<video_id>`,`/video.<encoded_id>/<title>`,`/video<id>/<title>`


## XXXBunker

Primary URL: https://xxxbunker.com

Supported Domains: xxxbunker.*

### Supported paths
- Category: `/categories/<category>`
- Search: `/search/<video_id>`
- User Favorites: `/<username>/favoritevideos`
- Video: `/<video_id>`


## YandexDisk

Primary URL: https://disk.yandex.com.tr

Supported Domains: disk.yandex, yadi.sk

### Supported paths
- File: `/d/<folder_id>/<file_name>`,`/i/<file_id>`
- Folder: `/d/<folder_id>`

### Notes
- Does NOT support nested folders


## YouJizz

Primary URL: https://www.youjizz.com

Supported Domains: youjizz.*

### Supported paths
- Video: `/videos/<video_name>`,`/videos/embed/<video_id>`


<!-- END_SUPPORTED_SITES-->
