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

### 4chan

**Primary URL**: [https://boards.4chan.org](https://boards.4chan.org)

**Supported Domains**: `4chan.*`

**Supported Paths**:

- Board:
  - `/<board>`
- Thread:
  - `/<board>/thread/<thread_id>`


### 8Muses

**Primary URL**: [https://comics.8muses.com](https://comics.8muses.com)

**Supported Domains**: `8muses.*`

**Supported Paths**:

- Album:
  - `/comics/album/...`


### AllPornComix

**Primary URL**: [https://forum.allporncomix.com](https://forum.allporncomix.com)

**Supported Domains**: `allporncomix.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### Anontransfer.com

**Primary URL**: [https://anontransfer.com](https://anontransfer.com)

**Supported Domains**: `anontransfer.com`

**Supported Paths**:

- Direct Link:
  - `/download-direct.php?dir=<file_id>&file=<filename>`
  - `/uploads/<file_id>/<filename>`
- File:
  - `/d/<file_id>`
- Folder:
  - `/f/<folder_uuid>`


### AnySex

**Primary URL**: [https://anysex.com](https://anysex.com)

**Supported Domains**: `anysex.*`

**Supported Paths**:

- Album:
  - `/photos/<album_id>/...`
- Photo Search:
  - `/photos/search/...`
- Search:
  - `/search/...`
- Video:
  - `/video/<video_id>/...`


### ArchiveBate

**Primary URL**: [https://www.archivebate.store](https://www.archivebate.store)

**Supported Domains**: `archivebate.*`

**Supported Paths**:

- Video:
  - `/watch/<video_id>`


### aShemaleTube

**Primary URL**: [https://www.ashemaletube.com](https://www.ashemaletube.com)

**Supported Domains**: `ashemaletube.*`

**Supported Paths**:

- Model:
  - `/creators/...`
  - `/model/...`
  - `/pornstars/...`
- Playlist:
  - `/playlists/...`
- User:
  - `/profiles/...`
- Video:
  - `/videos/...`


### Bandcamp

**Primary URL**: [https://bandcamp.com](https://bandcamp.com)

**Supported Domains**: `bandcamp.*`

**Supported Paths**:

- Album:
  - `/album/<slug>`
- Song:
  - `/track/<slug>`


**Notes**

- You can set 'CDL_BANDCAMP_FORMATS' env var to a comma separated list of formats to download (Ordered by preference) [Default = 'mp3-320,mp3,aac-hi,wav,flac,vorbis,aiff,alas']


### Beeg.com

**Primary URL**: [https://beeg.com](https://beeg.com)

**Supported Domains**: `beeg.com`

**Supported Paths**:

- Video:
  - `/<video_id>`
  - `/video/<video_id>`


### Bellazon

**Primary URL**: [https://www.bellazon.com/main](https://www.bellazon.com/main)

**Supported Domains**: `bellazon.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Invision


### BestPrettyGirl

**Primary URL**: [https://bestprettygirl.com](https://bestprettygirl.com)

**Supported Domains**: `bestprettygirl.com`

**Supported Paths**:

- All Posts:
  - `/posts/`
- Category:
  - `/category/<category_slug>`
- Date Range:
  - `...?after=<date>`
  - `...?before=<date&after=<date>`
  - `...?before=<date>`
- Post:
  - `/<post_slug>/`
- Tag:
  - `/tag/<tag_slug>`


**Notes**

- For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

`Date Range` can be combined with `Category`, `Tag` and `All Posts`.
ex: To only download categories from a date range: ,
`/category/<category_slug>?before=<date>`


### Box

**Primary URL**: [https://www.box.com](https://www.box.com)

**Supported Domains**: `app.box.com`

**Supported Paths**:

- Embedded File or Folder:
  - `app.box.com/embed/s?sh=<share_code>`
  - `app.box.com/embed_widget/s?sh=<share_code>`
- File or Folder:
  - `app.box.com/s?sh=<share_code>`


### Bunkr

**Primary URL**: [https://bunkr.site](https://bunkr.site)

**Supported Domains**: `bunkr.*`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Direct Links:
- File:
  - `/<slug>`
  - `/d/<slug>`
  - `/f/<slug>`
- Video:
  - `/v/<slug>`


### Bunkr-Albums.io

**Primary URL**: [https://bunkr-albums.io](https://bunkr-albums.io)

**Supported Domains**: `bunkr-albums.io`

**Supported Paths**:

- Search:
  - `/?search=<query>`


### BuzzHeavier

**Primary URL**: [https://buzzheavier.com](https://buzzheavier.com)

**Supported Domains**: `buzzheavier.com`

**Supported Paths**:

- Direct Links:


### Camwhores.tv

**Primary URL**: [https://www.camwhores.tv](https://www.camwhores.tv)

**Supported Domains**: `camwhores.tv`

**Supported Paths**:

- Category:
  - `/categories/<name>/`
- Search:
  - `/search/<query>/`
- Tag:
  - `/tags/<name>/`
- Video:
  - `/videos/<id>/<slug>`


### Catbox

**Primary URL**: [https://catbox.moe](https://catbox.moe)

**Supported Domains**: `files.catbox.moe`, `litter.catbox.moe`

**Supported Paths**:

- Direct Links:


### CelebForum

**Primary URL**: [https://celebforum.to](https://celebforum.to)

**Supported Domains**: `celebforum.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### Chevereto

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:

- Album:
  - `/a/<id>`
  - `/a/<name>.<id>`
  - `/album/<id>`
  - `/album/<name>.<id>`
- Category:
  - `/category/<name>`
- Direct Links:
- Image:
  - `/image/<id>`
  - `/image/<name>.<id>`
  - `/img/<id>`
  - `/img/<name>.<id>`
- Profile:
  - `/<user_name>`
- Video:
  - `/video/<id>`
  - `/video/<name>.<id>`
  - `/videos/<id>`
  - `/videos/<name>.<id>`


### cloud.mail.ru

**Primary URL**: [https://cloud.mail.ru](https://cloud.mail.ru)

**Supported Domains**: `cloud.mail.ru`

**Supported Paths**:

- Public files / folders:
  - `/public/<web_path>`


### CloudflareStream

**Primary URL**: [https://cloudflarestream.com](https://cloudflarestream.com)

**Supported Domains**: `cloudflarestream.com`, `videodelivery.net`

**Supported Paths**:

- Public Video:
  - `/<video_uid>`
  - `/<video_uid>/iframe`
  - `/<video_uid>/watch`
  - `/embed/___.js?video=<video_uid>`
- Restricted Access Video:
  - `/<jwt_access_token>`
  - `/<jwt_access_token>/iframe`
  - `/<jwt_access_token>/watch`
  - `/embed/___.js?video=<jwt_access_token>`


### Coomer

**Primary URL**: [https://coomer.st](https://coomer.st)

**Supported Domains**: `coomer.party`, `coomer.st`, `coomer.su`

**Supported Paths**:

- Direct links:
  - `/data/...`
  - `/thumbnail/...`
- Favorites:
  - `/account/favorites/posts\|artists`
  - `/favorites?type=post\|artist`
- Individual Post:
  - `/<service>/user/<user_id>/post/<post_id>`
- Model:
  - `/<service>/user/<user_id>`
- Search:
  - `/search?q=...`


### Cyberdrop

**Primary URL**: [https://cyberdrop.cr](https://cyberdrop.cr)

**Supported Domains**: `cyberdrop.*`, `cyberdrop.cr`, `cyberdrop.me`, `cyberdrop.to`, `k1-cd.cdn.gigachad-cdn.ru`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Direct links:
  - `/api/file/d/<file_id>`
- File:
  - `/e/<file_id>`
  - `/f/<file_id>`


### Cyberfile

**Primary URL**: [https://cyberfile.me](https://cyberfile.me)

**Supported Domains**: `cyberfile.*`

**Supported Paths**:

- Files:
  - `/<file_id>`
  - `/<file_id>/<file_name>`
- Public Folders:
  - `/folder/<folder_id>`
  - `/folder/<folder_id>/<folder_name>`
- Shared folders:
  - `/shared/<share_key>`


### DesiVideo

**Primary URL**: [https://desivideo.net](https://desivideo.net)

**Supported Domains**: `desivideo.net`

**Supported Paths**:

- Search:
  - `/search?s=<query>`
- Video:
  - `/videos/<video_id>/...`


### DirectHttpFile

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:



### DirtyShip

**Primary URL**: [https://dirtyship.com](https://dirtyship.com)

**Supported Domains**: `dirtyship.*`

**Supported Paths**:

- Category:
  - `/category/<name>`
- Tag:
  - `/tag/<name>`
- Video:
  - `/<slug>`


### Discourse

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:

- Attachments:
  - `/uploads/...`
- Topic:
  - `/t/<topic_name>/<topic_id>`
  - `/t/<topic_name>/<topic_id>/<post_number>`


**Notes**

- If the URL includes <post_number>, posts with a number lower that it won't be scraped


### DoodStream

**Primary URL**: [https://doodstream.com](https://doodstream.com)

**Supported Domains**: `all3do.com`, `d000d.com`, `do7go.com`, `dood.re`, `dood.yt`, `doodcdn.*`, `doodstream.*`, `doodstream.co`, `myvidplay.com`, `playmogo.com`, `vidply.com`

**Supported Paths**:

- Video:
  - `/e/<video_id>`


### Dropbox

**Primary URL**: [https://www.dropbox.com](https://www.dropbox.com)

**Supported Domains**: `dropbox.*`

**Supported Paths**:

- File:
  - `/s/...`
  - `/scl/fi/<link_key>?rlkey=...`
  - `/scl/fo/<link_key>/<secure_hash>?preview=<filename>&rlkey=...`
- Folder:
  - `/scl/fo/<link_key>/<secure_hash>?rlkey=...`
  - `/sh/...`


### E-Hentai

**Primary URL**: [https://e-hentai.org](https://e-hentai.org)

**Supported Domains**: `e-hentai.*`

**Supported Paths**:

- Album:
  - `/g/...`
- File:
  - `/s/...`


### E621

**Primary URL**: [https://e621.net](https://e621.net)

**Supported Domains**: `e621.net`

**Supported Paths**:

- Pools:
  - `/pools/...`
- Post:
  - `/posts/...`
- Tags:
  - `/posts?tags=...`


### eFukt

**Primary URL**: [https://efukt.com](https://efukt.com)

**Supported Domains**: `efukt.com`

**Supported Paths**:

- Gif:
  - `/view.gif.php?id=<id>`
- Homepage:
  - `/`
- Photo:
  - `/pics/....`
- Series:
  - `/series/<series_name>`
- Video:
  - `/...`


### ePorner

**Primary URL**: [https://www.eporner.com](https://www.eporner.com)

**Supported Domains**: `eporner.*`

**Supported Paths**:

- Categories:
  - `/cat/...`
- Channels:
  - `/channel/...`
- Gallery:
  - `/gallery/...`
- Photo:
  - `/photo/...`
- Pornstar:
  - `/pornstar/...`
- Profile:
  - `/profile/...`
- Search:
  - `/search/...`
- Search Photos:
  - `/search-photos/...`
- Video:
  - `/<video_name>-<video-id>`
  - `/embed/<video_id>`
  - `/hd-porn/<video_id>`


### Erome

**Primary URL**: [https://www.erome.com](https://www.erome.com)

**Supported Domains**: `erome.*`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Profile:
  - `/<name>`
- Search:
  - `/search?q=<query>`


### Erome.fan

**Primary URL**: [https://erome.fan](https://erome.fan)

**Supported Domains**: `erome.fan`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Profile:
  - `/a/category/<name>`
- Search:
  - `/search/<query>`


### EveriaClub

**Primary URL**: [https://everia.club](https://everia.club)

**Supported Domains**: `everia.club`

**Supported Paths**:

- All Posts:
  - `/posts/`
- Category:
  - `/category/<category_slug>`
- Date Range:
  - `...?after=<date>`
  - `...?before=<date&after=<date>`
  - `...?before=<date>`
- Post:
  - `/<post_slug>/`
- Tag:
  - `/tag/<tag_slug>`


**Notes**

- For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

`Date Range` can be combined with `Category`, `Tag` and `All Posts`.
ex: To only download categories from a date range: ,
`/category/<category_slug>?before=<date>`


### F95Zone

**Primary URL**: [https://f95zone.to](https://f95zone.to)

**Supported Domains**: `f95zone.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### Fapello

**Primary URL**: [https://fapello.su](https://fapello.su)

**Supported Domains**: `fapello.*`

**Supported Paths**:

- Individual Post:
  - `/.../...`
- Model:
  - `/...`


### Fileditch

**Primary URL**: [https://fileditchfiles.me](https://fileditchfiles.me)

**Supported Domains**: `fileditch.*`

**Supported Paths**:

- Direct Links:


### Filester

**Primary URL**: [https://filester.me](https://filester.me)

**Supported Domains**: `filester.*`

**Supported Paths**:

- File:
  - `/d/<slug>`
- Folder:
  - `/f/<slug>`


### FilesVC

**Primary URL**: [https://files.vc](https://files.vc)

**Supported Domains**: `files.vc`

**Supported Paths**:

- Direct Links:


### Flickr

**Primary URL**: [https://www.flickr.com](https://www.flickr.com)

**Supported Domains**: `flickr.*`

**Supported Paths**:

- Album:
  - `/photos/<user_nsid>/albums/<photoset_id>/...`
- Photo:
  - `/photos/<user_nsid>/<photo_id>/...`


### Forums.plex.tv

**Primary URL**: [https://forums.plex.tv](https://forums.plex.tv)

**Supported Domains**: `forums.plex.tv`

**Supported Paths**:

- Attachments:
  - `/uploads/...`
- Topic:
  - `/t/<topic_name>/<topic_id>`
  - `/t/<topic_name>/<topic_id>/<post_number>`


**Notes**

- If the URL includes <post_number>, posts with a number lower that it won't be scraped


### FSIBlog

**Primary URL**: [https://fsiblog5.com](https://fsiblog5.com)

**Supported Domains**: `fsiblog.club`, `fsiblog.com`, `fsiblog1.club`, `fsiblog1.com`, `fsiblog2.club`, `fsiblog2.com`, `fsiblog3.club`, `fsiblog3.com`, `fsiblog4.club`, `fsiblog4.com`, `fsiblog5.club`, `fsiblog5.com`

**Supported Paths**:

- Posts:
  - `/<category>/<title>`
- Search:
  - `?s=<query>`


### FuckingFast

**Primary URL**: [https://fuckingfast.co](https://fuckingfast.co)

**Supported Domains**: `fuckingfast.co`

**Supported Paths**:

- Direct links:
  - `/<file_id>`


### FuXXX

**Primary URL**: [https://fuxxx.com](https://fuxxx.com)

**Supported Domains**: `fuxxx.com`, `fuxxx.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### Giphy

**Primary URL**: [https://giphy.com](https://giphy.com)

**Supported Domains**: `giphy.*`

**Supported Paths**:

- Direct Link:
  - `https://media*.giphy.com/media/<gif_id>`
- Gif:
  - `/gifs/<slug>-<gif-id>`


### GirlsReleased

**Primary URL**: [https://www.girlsreleased.com](https://www.girlsreleased.com)

**Supported Domains**: `girlsreleased.*`

**Supported Paths**:

- Model:
  - `/model/<model_id>/<model_name>`
- Set:
  - `/set/<set_id>`
- Site:
  - `/site/<site>`


### GoFile

**Primary URL**: [https://gofile.io](https://gofile.io)

**Supported Domains**: `gofile.*`

**Supported Paths**:

- Direct link:
  - `/download/<content_id>/<filename>`
  - `/download/web/<content_id>/<filename>`
- Folder / File:
  - `/d/<content_id>`


**Notes**

- Use `password` as a query param to download password protected folders
- ex: https://gofile.io/d/ABC654?password=1234


### GoogleDrive

**Primary URL**: [https://drive.google.com](https://drive.google.com)

**Supported Domains**: `docs.google`, `drive.google`, `drive.usercontent.google.com`

**Supported Paths**:

- Docs:
  - `/document/d/<file_id>`
- Files:
  - `/file/d/<file_id>`
- Folders:
  - `/drive/folders/<folder_id>`
  - `/embeddedfolderview/<folder_id>`
- Sheets:
  - `/spreadsheets/d/<file_id>`
- Slides:
  - `/presentation/d/<file_id>`


**Notes**

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


### GooglePhotos

**Primary URL**: [https://photos.google.com](https://photos.google.com)

**Supported Domains**: `photos.app.goo.gl`, `photos.google.com`

**Supported Paths**:

- Album:
  - `/share/<album_id>`
- Photo:
  - `/album/<album_id>/photo/<photo_id>`


**Notes**

- Only downloads 'optimized' images, NOT original quality
- Can NOT download videos


### GUpload

**Primary URL**: [https://gupload.xyz](https://gupload.xyz)

**Supported Domains**: `gupload.*`

**Supported Paths**:

- Video:
  - `/data/e/<video_id>`


### HClips

**Primary URL**: [https://hclips.com](https://hclips.com)

**Supported Domains**: `hclips.com`, `hclips.tube`, `privatehomeclips.com`, `privatehomeclips.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### HDZog

**Primary URL**: [https://hdzog.com](https://hdzog.com)

**Supported Domains**: `hdzog.com`, `hdzog.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### Hianime

**Primary URL**: [https://hianime.to](https://hianime.to)

**Supported Domains**: `aniwatch.to`, `aniwatchtv.to`, `hianime.to`, `zoro.to`

**Supported Paths**:

- Anime:
  - `/<name>-<anime_id>`
- Episode:
  - `/<name>-<anime_id>?ep=<episode_id>`
  - `/watch/<name>-<anime_id>?ep=<episode_id>`


**Notes**

- You can select the language to be downloaded by using a 'lang' query param. Valid options: 'sub' or 'dub'. Default: 'sub'If the chosen language is not available, CDL will use the first one available


### Hitomi.la

**Primary URL**: [https://hitomi.la](https://hitomi.la)

**Supported Domains**: `hitomi.la`

**Supported Paths**:

- Collection:
  - `/artist/...`
  - `/character/...`
  - `/group/...`
  - `/series/...`
  - `/tag/...`
  - `/type/...`
- Gallery:
  - `/anime/...`
  - `/cg/...`
  - `/doujinshi/...`
  - `/galleries/...`
  - `/gamecg/...`
  - `/imageset/...`
  - `/manga/...`
  - `/reader/...`
- Search:
  - `/search.html?<query>`


### HotLeaksTV

**Primary URL**: [https://hotleaks.tv](https://hotleaks.tv)

**Supported Domains**: `hotleaks.tv`

**Supported Paths**:

- Model:
  - `/<model_id>`
- Video:
  - `/<model_id>/video/<video_id>`


### HotLeakVip

**Primary URL**: [https://hotleak.vip](https://hotleak.vip)

**Supported Domains**: `hotleak.vip`

**Supported Paths**:

- Model:
  - `/<model_id>`
- Video:
  - `/<model_id>/video/<video_id>`


### HotMovs

**Primary URL**: [https://hotmovs.com](https://hotmovs.com)

**Supported Domains**: `hotmovs.com`, `hotmovs.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### HotPic

**Primary URL**: [https://hotpic.cc](https://hotpic.cc)

**Supported Domains**: `2385290.xyz`, `hotpic.*`

**Supported Paths**:

- Album:
  - `/album/...`
- Image:
  - `/i/...`


### Iceyfile

**Primary URL**: [https://iceyfile.com](https://iceyfile.com)

**Supported Domains**: `iceyfile.*`

**Supported Paths**:

- Files:
  - `/<file_id>`
  - `/<file_id>/<file_name>`
- Public Folders:
  - `/folder/<folder_id>`
  - `/folder/<folder_id>/<folder_name>`
- Shared folders:
  - `/shared/<share_key>`


### ImageBam

**Primary URL**: [https://www.imagebam.com](https://www.imagebam.com)

**Supported Domains**: `imagebam.*`

**Supported Paths**:

- Gallery:
  - `/gallery/<id>`
- Gallery or Image:
  - `/view/<id>`
- Image:
  - `/image/<id>`
  - `images<x>.imagebam.com/<id>`
- Thumbnails:
  - `thumbs<x>.imagebam.com/<id>`


### ImagePond

**Primary URL**: [https://imagepond.net](https://imagepond.net)

**Supported Domains**: `imagepond.net`

**Supported Paths**:

- Album:
  - `/a/<slug>`
- Direct links:
  - `/media/<slug>`
- Image / Video / Archive:
  - `/i/<slug>`
  - `/image/<slug>`
  - `/img/<slug>`
  - `/video/<slug>`
  - `/videos/<slug>`
- User:
  - `/<user_name>`
  - `/user/<user_name>`


### ImageVenue

**Primary URL**: [https://www.imagevenue.com](https://www.imagevenue.com)

**Supported Domains**: `imagevenue.*`

**Supported Paths**:

- Image:
  - `/<image_id>`
  - `/img.php?image=<image_id>`
  - `/view/o?i=<image_id>`
- Thumbnail:
  - `cdn-thumbs.imagevenue.com/.../<image_id>_t.jpg`


### ImgBB

**Primary URL**: [https://ibb.co](https://ibb.co)

**Supported Domains**: `ibb.co`, `imgbb.co`

**Supported Paths**:

- Album:
  - `/album/<album_id>`
- Image:
  - `/<image_id>`
- Profile:
  - `<user_name>.imgbb.co/`


### ImgBox

**Primary URL**: [https://imgbox.com](https://imgbox.com)

**Supported Domains**: `imgbox.*`

**Supported Paths**:

- Album:
  - `/g/...`
- Direct Links:
- Image:
  - `/...`


### ImgLike

**Primary URL**: [https://imglike.com](https://imglike.com)

**Supported Domains**: `imglike.com`

**Supported Paths**:

- Album:
  - `/a/<id>`
  - `/a/<name>.<id>`
  - `/album/<id>`
  - `/album/<name>.<id>`
- Category:
  - `/category/<name>`
- Direct Links:
- Image:
  - `/image/<id>`
  - `/image/<name>.<id>`
  - `/img/<id>`
  - `/img/<name>.<id>`
- Profile:
  - `/<user_name>`
- Video:
  - `/video/<id>`
  - `/video/<name>.<id>`
  - `/videos/<id>`
  - `/videos/<name>.<id>`


### Imgur

**Primary URL**: [https://imgur.com](https://imgur.com)

**Supported Domains**: `imgur.*`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Direct links:
  - `https://i.imgur.com/<image_id>.<ext>`
- Gallery:
  - `/gallery/<slug>-<album_id>`
- Image:
  - `/<image_id>`
  - `/download/<image_id>`


### Imx.to

**Primary URL**: [https://imx.to](https://imx.to)

**Supported Domains**: `imx.to`

**Supported Paths**:

- Gallery:
  - `/g/<gallery_id>`
- Image:
  - `/i/...`
  - `/u/i/...`
- Thumbnail:
  - `/t/...`
  - `/u/t/`


### IncestFlix

**Primary URL**: [https://www.incestflix.com](https://www.incestflix.com)

**Supported Domains**: `incestflix.*`

**Supported Paths**:

- Tag:
  - `/tag/...`
- Video:
  - `/watch/...`


### InPorn

**Primary URL**: [https://inporn.com](https://inporn.com)

**Supported Domains**: `inporn.com`, `inporn.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### JPG5

**Primary URL**: [https://jpg6.su](https://jpg6.su)

**Supported Domains**: `host.church`, `jpeg.pet`, `jpg.church`, `jpg.fish`, `jpg.fishing`, `jpg.homes`, `jpg.pet`, `jpg1.su`, `jpg2.su`, `jpg3.su`, `jpg4.su`, `jpg5.su`, `jpg6.su`, `jpg7.cr`, `selti-delivery.ru`

**Supported Paths**:

- Album:
  - `/a/<id>`
  - `/a/<name>.<id>`
  - `/album/<id>`
  - `/album/<name>.<id>`
- Category:
  - `/category/<name>`
- Direct Links:
- Image:
  - `/image/<id>`
  - `/image/<name>.<id>`
  - `/img/<id>`
  - `/img/<name>.<id>`
- Profile:
  - `/<user_name>`


### Kemono

**Primary URL**: [https://kemono.cr](https://kemono.cr)

**Supported Domains**: `kemono.cr`, `kemono.party`, `kemono.su`

**Supported Paths**:

- Direct links:
  - `/data/...`
  - `/thumbnail/...`
- Discord Server:
  - `/discord/<server_id>`
- Discord Server Channel:
  - `/discord/server/<server_id>/<channel_id>#...`
- Favorites:
  - `/account/favorites/posts\|artists`
  - `/favorites?type=post\|artist`
- Individual Post:
  - `/<service>/user/<user_id>/post/<post_id>`
- Model:
  - `/<service>/user/<user_id>`
- Search:
  - `/search?q=...`


### Koofr

**Primary URL**: [https://koofr.eu](https://koofr.eu)

**Supported Domains**: `k00.fr`, `koofr.eu`, `koofr.net`

**Supported Paths**:

- Public Share:
  - `/links/<content_id>`
  - `https://k00.fr/<short_id>`


### LeakedModels

**Primary URL**: [https://leakedmodels.com/forum](https://leakedmodels.com/forum)

**Supported Domains**: `leakedmodels.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### LeakedZone

**Primary URL**: [https://leakedzone.com](https://leakedzone.com)

**Supported Domains**: `leakedzone.*`

**Supported Paths**:

- Model:
  - `/<model_id>`
- Video:
  - `/<model_id>/video/<video_id>`


### Luscious

**Primary URL**: [https://members.luscious.net](https://members.luscious.net)

**Supported Domains**: `luscious.*`

**Supported Paths**:

- Album:
  - `/albums/...`


### LuxureTV

**Primary URL**: [https://luxuretv.com](https://luxuretv.com)

**Supported Domains**: `luxuretv.*`

**Supported Paths**:

- Search:
  - `/searchgate/videos/<search>/...`
- Video:
  - `/videos/<name>-<id>.html`


### Masahub

**Primary URL**: [https://masahub.com](https://masahub.com)

**Supported Domains**: `lol49.com`, `masa49.com`, `masafun.net`, `masahub.com`, `masahub2.com`, `vido99.com`

**Supported Paths**:

- Search:
  - `?s=<query>`
- Videos:
  - `/title`


### Mediafire

**Primary URL**: [https://www.mediafire.com](https://www.mediafire.com)

**Supported Domains**: `mediafire.*`

**Supported Paths**:

- File:
  - `/file/<quick_key>`
  - `?<quick_key>`
- Folder:
  - `/folder/<folder_key>`


### Megacloud

**Primary URL**: [https://megacloud.blog](https://megacloud.blog)

**Supported Domains**: `megacloud.*`

**Supported Paths**:

- Embed v3:
  - `/embed-2/v3`


### MegaNz

**Primary URL**: [https://mega.nz](https://mega.nz)

**Supported Domains**: `mega.co.nz`, `mega.io`, `mega.nz`

**Supported Paths**:

- File:
  - `/!#<file_id>!<share_key>`
  - `/file/<file_id>#<share_key>`
  - `/folder/<folder_id>#<share_key>/file/<file_id>`
- Folder:
  - `/F!#<folder_id>!<share_key>`
  - `/folder/<folder_id>#<share_key>`
- Subfolder:
  - `/folder/<folder_id>#<share_key>/folder/<subfolder_id>`


**Notes**

- Downloads can not be resumed. Partial downloads will always be deleted and new downloads will start over


### MissAV

**Primary URL**: [https://missav.ws](https://missav.ws)

**Supported Domains**: `missav.*`

**Supported Paths**:

- Genres:
  - `/genres/<genre>`
- Labels:
  - `/labels/<label>`
- Makers:
  - `/makers/<maker>`
- Search:
  - `/search/<search>`
- Tags:
  - `/tags/<tag>`
- Video:
  - `/...`


### MixDrop

**Primary URL**: [https://mixdrop.sb](https://mixdrop.sb)

**Supported Domains**: `m1xdrop.*`, `mixdrop.*`, `mxdrop.*`

**Supported Paths**:

- File:
  - `/e/<file_id>`
  - `/f/<file_id>`


### Motherless

**Primary URL**: [https://motherless.com](https://motherless.com)

**Supported Domains**: `motherless.*`

**Supported Paths**:

- Group:
  - `/g/<group_name>`
  - `/gi/<image>`
  - `/gv/<video>`
- Image:
  - `/...`
- User:
  - `/f/...`
  - `/u/...`
- Video:
  - `pending`


**Notes**

- Galleries are NOT supported


### MyDesi

**Primary URL**: [https://lolpol.com](https://lolpol.com)

**Supported Domains**: `fry99.com`, `lolpol.com`, `mydesi.net`

**Supported Paths**:

- Search:
  - `/search/<query>`
- Videos:
  - `/title`


### Nekohouse

**Primary URL**: [https://nekohouse.su](https://nekohouse.su)

**Supported Domains**: `nekohouse.*`

**Supported Paths**:

- Direct links:
  - `/(data|thumbnails)/...`
- Individual Post:
  - `/<service>/user/<user_id>/post/<post_id>`
- Model:
  - `/<service>/user/<user_id>`


### nHentai

**Primary URL**: [https://nhentai.net](https://nhentai.net)

**Supported Domains**: `nhentai.net`

**Supported Paths**:

- Collections:
  - `artist`
  - `character`
  - `favorites`
  - `group`
  - `parody`
  - `search`
  - `tag`
- Gallery:
  - `/g/<gallery_id>`


### NoodleMagazine

**Primary URL**: [https://noodlemagazine.com](https://noodlemagazine.com)

**Supported Domains**: `noodlemagazine.*`

**Supported Paths**:

- Search:
  - `/video/<search_query>`
- Video:
  - `/watch/<video_id>`


### nsfw.xxx

**Primary URL**: [https://nsfw.xxx](https://nsfw.xxx)

**Supported Domains**: `nsfw.xxx`

**Supported Paths**:

- Category:
  - `/category/<name>`
- Post:
  - `/post/<id>`
- Search:
  - `/search?q=<query>`
- Subreddit:
  - `/r/<subreddit>`
- User:
  - `/user/<username>`


### NudoStar

**Primary URL**: [https://nudostar.com/forum](https://nudostar.com/forum)

**Supported Domains**: `nudostar.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### NudoStarTV

**Primary URL**: [https://nudostar.tv](https://nudostar.tv)

**Supported Domains**: `nudostar.tv`

**Supported Paths**:

- Model:
  - `/models/...`


### ok.ru

**Primary URL**: [https://ok.ru](https://ok.ru)

**Supported Domains**: `odnoklassniki.ru`, `ok.ru`

**Supported Paths**:

- Channel:
  - `/profile/<username>/c<channel_id>`
  - `/video/c<channel_id>`
- Video:
  - `/video/<video_id>`


### OmegaScans

**Primary URL**: [https://omegascans.org](https://omegascans.org)

**Supported Domains**: `omegascans.*`

**Supported Paths**:

- Chapter:
  - `/series/.../...`
- Direct Links:
- Series:
  - `/series/...`


### OneDrive

**Primary URL**: [https://onedrive.com](https://onedrive.com)

**Supported Domains**: `1drv.ms`, `onedrive.live.com`

**Supported Paths**:

- Access Link:
  - `https://onedrive.live.com/?authkey=<KEY>&id=<ID>&cid=<CID>`
- Share Link (anyone can access):
  - `https://1drv.ms/b/<KEY>`
  - `https://1drv.ms/f/<KEY>`
  - `https://1drv.ms/t/<KEY>`
  - `https://1drv.ms/u/<KEY>`


### OnePace

**Primary URL**: [https://onepace.net](https://onepace.net)

**Supported Domains**: `onepace.net`

**Supported Paths**:

- All episodes:
  - `/watch`


### OwnCloud

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:

- Public Share:
  - `/s/<share_token>`


### Patreon

**Primary URL**: [https://www.patreon.com](https://www.patreon.com)

**Supported Domains**: `patreon.*`

**Supported Paths**:

- Creator:
  - `/<creator>`
  - `/cw/<creator>`
- Post:
  - `/posts/<slug>`


### pCloud

**Primary URL**: [https://www.pcloud.com](https://www.pcloud.com)

**Supported Domains**: `e.pc.cd`, `pc.cd`, `pcloud.*`

**Supported Paths**:

- Public File or folder:
  - `?code=<share_code>`
  - `e.pc.cd/<short_code>`
  - `u.pc.cd/<short_code>`


### PimpAndHost

**Primary URL**: [https://pimpandhost.com](https://pimpandhost.com)

**Supported Domains**: `pimpandhost.*`

**Supported Paths**:

- Album:
  - `/album/...`
- Image:
  - `/image/...`


### PimpBunny

**Primary URL**: [https://pimpbunny.com](https://pimpbunny.com)

**Supported Domains**: `pimpbunny.com`

**Supported Paths**:

- Album:
  - `/albums/<album_name>`
- Category:
  - `/categories/<category>`
- Model Albums:
  - `/albums/models/<model_name>`
- Models:
  - `/onlyfans-models/<model_name>`
- Tag:
  - `/tags/<tag>`
- Videos:
  - `/videos/...`


### PixelDrain

**Primary URL**: [https://pixeldrain.com](https://pixeldrain.com)

**Supported Domains**: `pd.1drv.eu.org`, `pd.cybar.xyz`, `pixeldra.in`, `pixeldrain.biz`, `pixeldrain.com`, `pixeldrain.dev`, `pixeldrain.net`, `pixeldrain.nl`, `pixeldrain.tech`

**Supported Paths**:

- File:
  - `/api/file/<file_id>`
  - `/l/<list_id>#item=<file_index>`
  - `/u/<file_id>`
- Filesystem:
  - `/api/filesystem/<path>...`
  - `/d/<id>`
- Folder:
  - `/api/list/<list_id>`
  - `/l/<list_id>`


**Notes**

- text files will not be downloaded but their content will be parsed for URLs


### PixHost

**Primary URL**: [https://pixhost.to](https://pixhost.to)

**Supported Domains**: `pixhost.org`, `pixhost.to`

**Supported Paths**:

- Gallery:
  - `/gallery/<gallery_id>`
- Image:
  - `/show/<image_id>`
- Thumbnail:
  - `/thumbs/..`


### Pkmncards

**Primary URL**: [https://pkmncards.com](https://pkmncards.com)

**Supported Domains**: `pkmncards.*`

**Supported Paths**:

- Card:
  - `/card/...`
- Series:
  - `/series/...`
- Set:
  - `/set/...`


### PMVHaven

**Primary URL**: [https://pmvhaven.com](https://pmvhaven.com)

**Supported Domains**: `pmvhaven.*`

**Supported Paths**:

- Playlist:
  - `/playlists/...`
- Search results:
  - `/search/...`
- Users:
  - `/profile/...`
  - `/users/...`
- Video:
  - `/video/...`


### PornHub

**Primary URL**: [https://www.pornhub.com](https://www.pornhub.com)

**Supported Domains**: `pornhub.*`

**Supported Paths**:

- Album:
  - `/album/...`
- Channel:
  - `/channel/...`
- Gif:
  - `/gif/...`
- Photo:
  - `/photo/...`
- Playlist:
  - `/playlist/...`
- Profile:
  - `/model/...`
  - `/pornstar/...`
  - `/user/...`
- Video:
  - `/embed/<video_id>`
  - `/view_video.php?viewkey=<video_id>`


### PornPics

**Primary URL**: [https://pornpics.com](https://pornpics.com)

**Supported Domains**: `pornpics.*`

**Supported Paths**:

- Categories:
  - `/categories/....`
- Channels:
  - `/channels/...`
- Direct Links:
- Gallery:
  - `/galleries/...`
- Pornstars:
  - `/pornstars/...`
- Search:
  - `/?q=<query>`
- Tags:
  - `/tags/...`


### Porntrex

**Primary URL**: [https://www.porntrex.com](https://www.porntrex.com)

**Supported Domains**: `porntrex.*`

**Supported Paths**:

- Album:
  - `/albums/...`
- Category:
  - `/categories/...`
- Model:
  - `/models/...`
- Playlist:
  - `/playlists/...`
- Search:
  - `/search/...`
- Tag:
  - `/tags/...`
- User:
  - `/members/...`
- Video:
  - `/video/...`


### PornZog

**Primary URL**: [https://pornzog.com](https://pornzog.com)

**Supported Domains**: `pornzog.*`

**Supported Paths**:

- Video:
  - `/video/...`


### PostImg

**Primary URL**: [https://postimg.cc](https://postimg.cc)

**Supported Domains**: `postimages.org`, `postimg.cc`, `postimg.org`

**Supported Paths**:

- Album:
  - `/gallery/<album_id>/...`
- Direct links:
  - `i.postimg.cc/<image_id>/...`
- Image:
  - `/<image_id>/...`


### Ranoz.gg

**Primary URL**: [https://ranoz.gg](https://ranoz.gg)

**Supported Domains**: `qiwi.gg`, `ranoz.gg`

**Supported Paths**:

- File:
  - `/d/<file_id>`
  - `/file/<file_id>`


### RealBooru

**Primary URL**: [https://realbooru.com](https://realbooru.com)

**Supported Domains**: `realbooru.*`

**Supported Paths**:

- File:
  - `?id=...`
- Tags:
  - `?tags=...`


### RealDebrid

**Primary URL**: [https://real-debrid.com](https://real-debrid.com)

**Supported Domains**: `real-debrid.*`

**Supported Paths**:



### RedGifs

**Primary URL**: [https://www.redgifs.com](https://www.redgifs.com)

**Supported Domains**: `redgifs.*`

**Supported Paths**:

- Embeds:
  - `/ifr/<gif_id>`
- Gif:
  - `/watch/<gif_id>`
- Image:
  - `/i/<image_id>`
- User:
  - `/users/<user>`


### Rootz.so

**Primary URL**: [https://www.rootz.so](https://www.rootz.so)

**Supported Domains**: `rootz.so`

**Supported Paths**:

- File:
  - `/d/<file_id>`
  - `/file/<file_id>`


### Rule34Vault

**Primary URL**: [https://rule34vault.com](https://rule34vault.com)

**Supported Domains**: `rule34vault.*`

**Supported Paths**:

- Playlist:
  - `/playlists/view/...`
- Post:
  - `/post/...`
- Tag:
  - `/...`


### Rule34Video

**Primary URL**: [https://rule34video.com](https://rule34video.com)

**Supported Domains**: `rule34video.*`

**Supported Paths**:

- Category:
  - `/categories/<name>`
- Members:
  - `/members/<member_id>`
- Model:
  - `/models/<name>`
- Search:
  - `/search/<query>`
- Tag:
  - `/tags/<name>`
- Video:
  - `/video/<id>/<slug>`


### Rule34XXX

**Primary URL**: [https://rule34.xxx](https://rule34.xxx)

**Supported Domains**: `rule34.xxx`

**Supported Paths**:

- File:
  - `?id=...`
- Tag:
  - `?tags=...`


### Rule34XYZ

**Primary URL**: [https://rule34.xyz](https://rule34.xyz)

**Supported Domains**: `rule34.xyz`

**Supported Paths**:

- Playlist:
  - `/playlists/view/...`
- Post:
  - `/post/...`
- Tag:
  - `/...`


### Rumble

**Primary URL**: [https://rumble.com](https://rumble.com)

**Supported Domains**: `rumble.*`

**Supported Paths**:

- Channel:
  - `/c/<name>`
- Embed:
  - `/embed/<video_id>`
- User:
  - `/user/<name>`
- Video:
  - `<video_id>-<video-title>.html`


### Scrolller

**Primary URL**: [https://scrolller.com](https://scrolller.com)

**Supported Domains**: `scrolller.*`

**Supported Paths**:

- Subreddit:
  - `/r/...`


### SendNow

**Primary URL**: [https://send.now](https://send.now)

**Supported Domains**: `send.now`

**Supported Paths**:

- Direct Links:


### SendVid

**Primary URL**: [https://sendvid.com](https://sendvid.com)

**Supported Domains**: `sendvid.*`

**Supported Paths**:

- Direct Links:
- Embeds:
  - `/embed/...`
- Videos:
  - `/...`


### Sex.com

**Primary URL**: [https://sex.com](https://sex.com)

**Supported Domains**: `sex.*`

**Supported Paths**:

- Shorts Profiles:
  - `/shorts/<profile>`


### SocialMediaGirls

**Primary URL**: [https://forums.socialmediagirls.com](https://forums.socialmediagirls.com)

**Supported Domains**: `socialmediagirls.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### SpankBang

**Primary URL**: [https://spankbang.com](https://spankbang.com)

**Supported Domains**: `spankbang.*`

**Supported Paths**:

- Playlist:
  - `/<playlist_id>/playlist/...`
- Profile:
  - `/profile/<user>`
  - `/profile/<user>/videos`
- Video:
  - `/<video_id>/embed`
  - `/<video_id>/video`
  - `/play/<video_id>`
  - `<playlist_id>-<video_id>/playlist/...`


### Streamable

**Primary URL**: [https://streamable.com](https://streamable.com)

**Supported Domains**: `streamable.*`

**Supported Paths**:

- Video:
  - `/...`


### Streamtape

**Primary URL**: [https://streamtape.com](https://streamtape.com)

**Supported Domains**: `streamtape.com`

**Supported Paths**:

- Player:
  - `/e/<video_id>`
- Videos:
  - `/v/<video_id>`


### TabooTube

**Primary URL**: [https://www.tabootube.xxx](https://www.tabootube.xxx)

**Supported Domains**: `tabootube.*`

**Supported Paths**:

- Video:
  - `/video/...`


### ThisVid

**Primary URL**: [https://thisvid.com](https://thisvid.com)

**Supported Domains**: `thisvid.*`

**Supported Paths**:

- Albums:
  - `/albums/<album_name>`
- Categories:
  - `/categories/<name>`
- Image:
  - `/albums/<album_name>/<image_name>`
- Members:
  - `/members/<member_id>`
- Search:
  - `/search/?q=<query>`
- Tags:
  - `/tags/<name>`
- Videos:
  - `/videos/<slug>`


### ThotHub

**Primary URL**: [https://thothub.to](https://thothub.to)

**Supported Domains**: `thothub.*`

**Supported Paths**:

- Album:
  - `/albums/<id>/<name>`
- Image:
  - `/get_image/...`
- Video:
  - `/videos/<id>/<slug>`


### TikTok

**Primary URL**: [https://www.tiktok.com](https://www.tiktok.com)

**Supported Domains**: `tiktok.*`

**Supported Paths**:

- Photo:
  - `/@<user>/photo/<photo_id>`
- User:
  - `/@<user>`
- Video:
  - `/@<user>/video/<video_id>`


### TitsInTops

**Primary URL**: [https://titsintops.com/phpBB2](https://titsintops.com/phpBB2)

**Supported Domains**: `titsintops.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### TNAFlix

**Primary URL**: [https://www.tnaflix.com](https://www.tnaflix.com)

**Supported Domains**: `tnaflix.*`

**Supported Paths**:

- Channel:
  - `/channel/...`
- Profile:
  - `/profile/...`
- Search:
  - `/search?what=<query>`
- Video:
  - `/<category>/<title>/video<video_id>`


### Tokyomotion

**Primary URL**: [https://www.tokyomotion.net](https://www.tokyomotion.net)

**Supported Domains**: `tokyomotion.*`

**Supported Paths**:

- Albums:
  - `/album/<album_id>`
  - `/user/<user>/albums/`
- Photo:
  - `/photo/<photo_id>`
  - `/user/<user>/favorite/photos`
- Playlist:
  - `/user/<user>/favorite/videos`
- Profiles:
  - `/user/<user>`
- Search Results:
  - `/search?...`
- Video:
  - `/video/<video_id>`


### Toonily

**Primary URL**: [https://toonily.com](https://toonily.com)

**Supported Domains**: `toonily.*`

**Supported Paths**:

- Chapter:
  - `/serie/<name>/chapter-<chapter-id>`
- Serie:
  - `/serie/<name>`


### Tranny.One

**Primary URL**: [https://www.tranny.one](https://www.tranny.one)

**Supported Domains**: `tranny.one`

**Supported Paths**:

- Album:
  - `/pics/album/<album_id>`
- Pornstars:
  - `/pornstar/<model_id>/<model_name>`
- Search:
  - `/search/<search_query>`
- Video:
  - `/view/<video_id>`


### Transfer.it

**Primary URL**: [https://transfer.it](https://transfer.it)

**Supported Domains**: `transfer.it`

**Supported Paths**:

- Transfer:
  - `/t/<transfer_id>`


### TransFlix

**Primary URL**: [https://transflix.net](https://transflix.net)

**Supported Domains**: `transflix.*`

**Supported Paths**:

- Search:
  - `/search/?q=<query>`
- Video:
  - `/video/<name>-<video_id>`


### TubePornClassic

**Primary URL**: [https://tubepornclassic.com](https://tubepornclassic.com)

**Supported Domains**: `tubepornclassic.com`, `tubepornclassic.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### TurboVid

**Primary URL**: [https://turbovid.cr](https://turbovid.cr)

**Supported Domains**: `saint.to`, `saint2.cr`, `saint2.su`, `turbo.cr`, `turbovid.cr`

**Supported Paths**:

- Album:
  - `/a/<album_id>`
- Direct links:
  - `/data/...`
- Search:
  - `library?q=<query>`
- Video:
  - `/d/<file_id>`
  - `/embed/<file_id>`
  - `/v/<file_id>`


### Twitch

**Primary URL**: [https://www.twitch.tv](https://www.twitch.tv)

**Supported Domains**: `twitch.*`

**Supported Paths**:

- Clip:
  - `/<user>/clip/<slug>`
  - `/embed?clip=<slug>`
  - `https://clips.twitch.tv/<slug>`
- Collection:
  - `/collections/<collection_id>`
- VOD:
  - `/<user>/v/<vod_id>`
  - `/video/<vod_id>`
  - `/videos/<vod_id>`
  - `?video=<vod_id>`


### Twitter

**Primary URL**: [https://x.com](https://x.com)

**Supported Domains**: `twitter.com`, `x.com`

**Supported Paths**:

- Tweet:
  - `/<handle>/status/<tweet_id>`


### TwitterImages

**Primary URL**: [https://twimg.com](https://twimg.com)

**Supported Domains**: `twimg.*`

**Supported Paths**:

- Photo:
  - `/...`


### TWPornStars

**Primary URL**: [https://www.twpornstars.com](https://www.twpornstars.com)

**Supported Domains**: `indiantw.com`, `twanal.com`, `twgaymuscle.com`, `twgays.com`, `twlesbian.com`, `twmilf.com`, `twonfans.com`, `twpornstars.com`, `twteens.com`, `twtiktoks.com`

**Supported Paths**:

- Photo:
  - `/...`


### TXXX

**Primary URL**: [https://txxx.com](https://txxx.com)

**Supported Domains**: `txxx.com`, `txxx.tube`, `videotxxx.com`, `videotxxx.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### Upload.ee

**Primary URL**: [https://www.upload.ee](https://www.upload.ee)

**Supported Domains**: `upload.ee`

**Supported Paths**:

- File:
  - `/files/<file_id>`


### UPornia

**Primary URL**: [https://upornia.com](https://upornia.com)

**Supported Domains**: `upornia.com`, `upornia.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### Vidara

**Primary URL**: [https://vidara.to](https://vidara.to)

**Supported Domains**: `stmix.io`, `streamix.so`, `vidara.so`, `vidara.to`, `xca.cymru`

**Supported Paths**:

- Video:
  - `/e/<video_id>`


### ViperGirls

**Primary URL**: [https://vipergirls.to](https://vipergirls.to)

**Supported Domains**: `viper.click`, `vipergirls.to`

**Supported Paths**:

- Threads:
  - `/goto/<post_id>`
  - `/posts/<post_id>`
  - `/threads/<thread_name>`


### Vipr.im

**Primary URL**: [https://vipr.im](https://vipr.im)

**Supported Domains**: `vipr.im`

**Supported Paths**:

- Direct Image:
  - `/i/.../<slug>`
- Image:
  - `/<id>`
- Thumbnail:
  - `/th/.../<slug>`


### VJav

**Primary URL**: [https://vjav.com](https://vjav.com)

**Supported Domains**: `vjav.com`, `vjav.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### Voe.sx

**Primary URL**: [https://voe.sx](https://voe.sx)

**Supported Domains**: `alejandrocenturyoil.com`, `diananatureforeign.com`, `heatherwholeinvolve.com`, `jennifercertaindevelopment.com`, `jilliandescribecompany.com`, `jonathansociallike.com`, `mariatheserepublican.com`, `maxfinishseveral.com`, `nathanfromsubject.com`, `richardsignfish.com`, `robertordercharacter.com`, `sarahnewspaperbeat.com`, `voe.sx`

**Supported Paths**:

- Embed:
  - `/e/video_id`


### VoyeurHit

**Primary URL**: [https://voyeurhit.com](https://voyeurhit.com)

**Supported Domains**: `voyeurhit.com`, `voyeurhit.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### VSCO

**Primary URL**: [https://vsco.co](https://vsco.co)

**Supported Domains**: `vsco.*`

**Supported Paths**:

- Gallery:
  - `/<user>/gallery`
- Media:
  - `/<user>/media/<media_id>`
  - `/<user>/video/<media_id>`


### VXXX

**Primary URL**: [https://vxxx.com](https://vxxx.com)

**Supported Domains**: `vxxx.com`, `vxxx.tube`

**Supported Paths**:

- Video:
  - `/video-<video-id>`


### WeTransfer

**Primary URL**: [https://wetransfer.com](https://wetransfer.com)

**Supported Domains**: `we.tl`, `wetransfer.com`

**Supported Paths**:

- Direct links:
  - `download.wetransfer.com/...`
- Public link:
  - `wetransfer.com/downloads/<file_id>/<security_hash>`
- Share Link:
  - `wetransfer.com/downloads/<file_id>/<recipient_id>/<security_hash>`
- Short Link:
  - `we.tl/<short_file_id>`


### WordPressHTML

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:

- All Posts:
  - `/posts/`
- Category:
  - `/category/<category_slug>`
- Date Range:
  - `...?after=<date>`
  - `...?before=<date&after=<date>`
  - `...?before=<date>`
- Post:
  - `/<post_slug>/`
- Tag:
  - `/tag/<tag_slug>`


**Notes**

- For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

`Date Range` can be combined with `Category`, `Tag` and `All Posts`.
ex: To only download categories from a date range: ,
`/category/<category_slug>?before=<date>`


### WordPressMedia

**Primary URL**: [::GENERIC CRAWLER::](::GENERIC CRAWLER::)

**Supported Domains**:

**Supported Paths**:

- All Posts:
  - `/posts/`
- Category:
  - `/category/<category_slug>`
- Date Range:
  - `...?after=<date>`
  - `...?before=<date&after=<date>`
  - `...?before=<date>`
- Post:
  - `/<post_slug>/`
- Tag:
  - `/tag/<tag_slug>`


**Notes**

- For `Date Range`, <date>  must be a valid iso 8601 date, ex: `2022-12-06`.

`Date Range` can be combined with `Category`, `Tag` and `All Posts`.
ex: To only download categories from a date range: ,
`/category/<category_slug>?before=<date>`


### Xasiat

**Primary URL**: [https://www.xasiat.com](https://www.xasiat.com)

**Supported Domains**: `xasiat.*`

**Supported Paths**:

- Album:
  - `/albums/<id>/<name>`
- Images:
  - `/get_image/...`
- Videos:
  - `/videos/<id>/<name>`


### XBunker

**Primary URL**: [https://xbunker.nu](https://xbunker.nu)

**Supported Domains**: `xbunker.*`

**Supported Paths**:

- Attachments:
  - `/(attachments\|data\|uploads)/...`
- Threads:
  - `/(thread\|topic\|tema\|threads\|topics\|temas)/<thread_name_and_id>`
  - `/goto/<post_id>`
  - `/posts/<post_id>`


**Notes**

- base crawler: Xenforo


### XGroovy

**Primary URL**: [https://xgroovy.com](https://xgroovy.com)

**Supported Domains**: `xgroovy.*`

**Supported Paths**:

- Channel:
  - `/<category>/channels/...`
  - `/channels/...`
- Gif:
  - `/<category>/gifs/<gif_id>/...`
  - `/gifs/<gif_id>/...`
- Images:
  - `/<category>/photos/<photo_id>/...`
  - `/photos/<photo_id>/...`
- Pornstar:
  - `/<category>/pornstars/<pornstar_id>/...`
  - `/pornstars/<pornstar_id>/...`
- Search:
  - `/<category>/search/...`
  - `/search/...`
- Tag:
  - `/<category>/tags/...`
  - `/tags/...`
- Video:
  - `/<category>/videos/<video_id>/...`
  - `/videos/<video_id>/...`


### xHamster

**Primary URL**: [https://xhamster.com](https://xhamster.com)

**Supported Domains**: `xhamster.*`

**Supported Paths**:

- Creator:
  - `/creators/<creator_name>`
- Creator Galleries:
  - `/creators/<creator_name>/photos`
- Creator Videos:
  - `/creators/<creator_name>/exclusive`
- Gallery:
  - `/photos/gallery/<gallery_name_or_id>`
- User:
  - `/users/<user_name>`
  - `/users/profiles/<user_name>`
- User Galleries:
  - `/users/<user_name>/photos`
- User Videos:
  - `/users/<user_name>/videos`
- Video:
  - `/videos/<title>`


### XMegaDrive

**Primary URL**: [https://www.xmegadrive.com](https://www.xmegadrive.com)

**Supported Domains**: `xmegadrive.*`

**Supported Paths**:

- Albums:
  - `/albums/<album_name>`
- Categories:
  - `/categories/<name>`
- Image:
  - `/albums/<album_name>/<image_name>`
- Members:
  - `/members/<member_id>`
- Search:
  - `/search/?q=<query>`
- Tags:
  - `/tags/<name>`
- Videos:
  - `/videos/<slug>`


### XMilf

**Primary URL**: [https://xmilf.com](https://xmilf.com)

**Supported Domains**: `xmilf.com`, `xmilf.tube`

**Supported Paths**:

- Video:
  - `/embed/<video_id>/...`
  - `/videos/<video_id>/...`


### xVideos

**Primary URL**: [https://www.xvideos.com](https://www.xvideos.com)

**Supported Domains**: `xv-ru.com`, `xvideos-ar.com`, `xvideos-india.com`, `xvideos.com`, `xvideos.es`

**Supported Paths**:

- Account:
  - `/<channel_name>`
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>`
- Account Photos:
  - `/<channel_name>#_tabPhotos`
  - `/<channel_name>/photos/...`
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#_tabPhotos`
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>/photos/...`
- Account Quickies:
  - `/<channel_name>#quickies`
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#quickies`
- Account Videos:
  - `/<channel_name>#_tabVideos`
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles/<name>#_tabVideos`
- Video:
  - `/amateur\|amateur-channels\|amateurs\|channel\|channel-channels\|channels\|pornstar\|pornstar-channels\|pornstars\|profile\|profile-channels\|profiles#quickies/(a\|h\|v)/<video_id>`
  - `/video.<encoded_id>/<title>`
  - `/video<id>/<title>`


### XXXBunker

**Primary URL**: [https://xxxbunker.com](https://xxxbunker.com)

**Supported Domains**: `xxxbunker.*`

**Supported Paths**:

- Category:
  - `/categories/<category>`
- Search:
  - `/search/<video_id>`
- User Favorites:
  - `/<username>/favoritevideos`
- Video:
  - `/<video_id>`


### YandexDisk

**Primary URL**: [https://disk.yandex.com.tr](https://disk.yandex.com.tr)

**Supported Domains**: `disk.yandex`, `yadi.sk`

**Supported Paths**:

- File:
  - `/d/<folder_id>/<file_name>`
  - `/i/<file_id>`
- Folder:
  - `/d/<folder_id>`


**Notes**

- Does NOT support nested folders


### YouJizz

**Primary URL**: [https://www.youjizz.com](https://www.youjizz.com)

**Supported Domains**: `youjizz.*`

**Supported Paths**:

- Video:
  - `/videos/<video_name>`
  - `/videos/embed/<video_id>`


<!-- END_SUPPORTED_SITES-->
