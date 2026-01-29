# ruff: noqa: F401
from __future__ import annotations

from cyberdrop_dl import env

from ._chevereto import CheveretoCrawler
from .anontransfer import AnonTransferCrawler
from .anysex import AnySexCrawler
from .archivebate import ArchiveBateCrawler
from .ashemaletube import AShemaleTubeCrawler
from .bandcamp import BandcampCrawler
from .beeg import BeegComCrawler
from .box_dot_com import BoxDotComCrawler
from .bunkrr import BunkrrCrawler
from .bunkrr_albums_io import BunkrAlbumsIOCrawler
from .buzzheavier import BuzzHeavierCrawler
from .camwhores_dot_tv import CamwhoresTVCrawler
from .catbox import CatboxCrawler
from .cloudflare_stream import CloudflareStreamCrawler
from .coomer import CoomerCrawler
from .crawler import Crawler
from .cyberdrop import CyberdropCrawler
from .cyberfile import CyberfileCrawler
from .desivideo import DesiVideoCrawler
from .dirtyship import DirtyShipCrawler
from .discourse import DISCOURSE_CRAWLERS, DiscourseCrawler
from .doodstream import DoodStreamCrawler
from .dropbox import DropboxCrawler
from .e621 import E621Crawler
from .efukt import EfuktCrawler
from .ehentai import EHentaiCrawler
from .eightmuses import EightMusesCrawler
from .eporner import EpornerCrawler
from .erome import EromeCrawler, EromeFanCrawler
from .fapello import FapelloCrawler
from .fileditch import FileditchCrawler
from .files_vc import FilesVcCrawler
from .flugel_anime import FlugelAnimeCrawler
from .fourchan import FourChanCrawler
from .fsiblog import FSIBlogCrawler
from .fucking_fast import FuckingFastCrawler
from .fuxxx import FuXXXCrawler
from .generic import GenericCrawler
from .girlsreleased import GirlsReleasedCrawler
from .gofile import GoFileCrawler
from .google_drive import GoogleDriveCrawler
from .google_photos import GooglePhotosCrawler
from .hclips import HClipsCrawler
from .hdzog import HDZogCrawler
from .hianime import HiAnimeCrawler
from .hitomi_la import HitomiLaCrawler
from .hotleak_vip import HotLeakVipCrawler
from .hotleaks_dot_tv import HotLeaksTVCrawler
from .hotmovs import HotMovsCrawler
from .hotpic import HotPicCrawler
from .iceyfile import IceyFileCrawler
from .imagebam import ImageBamCrawler
from .imagepond import ImagePondCrawler
from .imgbb import ImgBBCrawler
from .imgbox import ImgBoxCrawler
from .imglike import ImgLikeCrawler
from .imgur import ImgurCrawler
from .imx_to import ImxToCrawler
from .incestflix import IncestflixCrawler
from .influencer_bitches import InfluencerBitchesCrawler
from .inporn import InPornCrawler
from .invision import INVISION_CRAWLERS
from .jpg5 import JPG5Crawler
from .kemono import KemonoCrawler
from .koofr import KooFrCrawler
from .leakedzone import LeakedZoneCrawler
from .luscious import LusciousCrawler
from .luxuretv import LuxureTVCrawler
from .masahub import MasahubCrawler
from .mediafire import MediaFireCrawler
from .mega_nz import MegaNzCrawler
from .megacloud import MegaCloudCrawler
from .missav import MissAVCrawler
from .mixdrop import MixDropCrawler
from .motherless import MotherlessCrawler
from .mydesi import MyDesiCrawler
from .nekohouse import NekohouseCrawler
from .nhentai import NHentaiCrawler
from .noodle_magazine import NoodleMagazineCrawler
from .nsfw_xxx import NsfwXXXCrawler
from .nudostartv import NudoStarTVCrawler
from .odnoklassniki import OdnoklassnikiCrawler
from .omegascans import OmegaScansCrawler
from .onedrive import OneDriveCrawler
from .pcloud import PCloudCrawler
from .pimp_bunny import PimpBunnyCrawler
from .pimpandhost import PimpAndHostCrawler
from .pixeldrain import PixelDrainCrawler
from .pixhost import PixHostCrawler
from .pkmncards import PkmncardsCrawler
from .pmvhaven import PMVHavenCrawler
from .pornhub import PornHubCrawler
from .pornpics import PornPicsCrawler
from .porntrex import PorntrexCrawler
from .pornzog import PornZogCrawler
from .postimg import PostImgCrawler
from .ranoz import RanozCrawler, RootzCrawler
from .realbooru import RealBooruCrawler
from .redgifs import RedGifsCrawler
from .rule34vault import Rule34VaultCrawler
from .rule34video import Rule34VideoCrawler
from .rule34xxx import Rule34XXXCrawler
from .rule34xyz import Rule34XYZCrawler
from .rumble import RumbleCrawler
from .safe_soul import SafeSoulCrawler
from .scrolller import ScrolllerCrawler
from .send_now import SendNowCrawler
from .sendvid import SendVidCrawler
from .sex_dot_com import SexDotComCrawler
from .spankbang import SpankBangCrawler
from .streamable import StreamableCrawler
from .streamtape import StreamtapeCrawler
from .thisvid import ThisVidCrawler
from .thothub import ThotHubCrawler
from .tiktok import TikTokCrawler
from .tnaflix import TNAFlixCrawler
from .tokyomotion import TokioMotionCrawler
from .toonily import ToonilyCrawler
from .tranny_one import TrannyOneCrawler
from .transfer_it import TransferItCrawler
from .transflix import TransflixCrawler
from .tubepornclassic import TubePornClassicCrawler
from .turbovid import TurboVidCrawler
from .twitch import TwitchCrawler
from .twitter import TwitterCrawler
from .twitter_images import TwimgCrawler
from .twpornstars import TwPornstarsCrawler
from .txxx import TXXXCrawler
from .upornia import UPorniaCrawler
from .vbulletin import VBULLETIN_CRAWLERS
from .vipr_dot_im import ViprImCrawler
from .vjav import VJavCrawler
from .voe_sx import VoeSxCrawler
from .voyeurhit import VoyeurHitCrawler
from .vsco import VSCOCrawler
from .vxxx import VXXXCrawler
from .wetransfer import WeTransferCrawler
from .wordpress import WP_CRAWLERS, WordPressHTMLCrawler, WordPressMediaCrawler
from .xasiat import XasiatCrawler
from .xbunkr import XBunkrCrawler
from .xenforo import XF_CRAWLERS, SimpCityCrawler
from .xgroovy import XGroovyCrawler
from .xhamster import XhamsterCrawler
from .xmilf import XMilfCrawler
from .xvideos import XVideosCrawler
from .xxxbunker import XXXBunkerCrawler
from .yandex_disk import YandexDiskCrawler
from .youjizz import YouJizzCrawler

FORUM_CRAWLERS = XF_CRAWLERS.union(INVISION_CRAWLERS, DISCOURSE_CRAWLERS, VBULLETIN_CRAWLERS)
GENERIC_CRAWLERS: set[type[Crawler]] = {WordPressHTMLCrawler, WordPressMediaCrawler, DiscourseCrawler, CheveretoCrawler}
ALL_CRAWLERS: set[type[Crawler]] = {
    crawler for name, crawler in globals().items() if name.endswith("Crawler") and crawler is not Crawler
}
ALL_CRAWLERS.update(WP_CRAWLERS, GENERIC_CRAWLERS, FORUM_CRAWLERS)
DEBUG_CRAWLERS = {SimpCityCrawler, TwitterCrawler}
if env.ENABLE_DEBUG_CRAWLERS == "d396ab8c85fcb1fecd22c8d9b58acf944a44e6d35014e9dd39e42c9a64091eda":
    CRAWLERS = ALL_CRAWLERS
else:
    CRAWLERS = ALL_CRAWLERS - DEBUG_CRAWLERS

WEBSITE_CRAWLERS = CRAWLERS - FORUM_CRAWLERS - {GenericCrawler}
__all__ = ["ALL_CRAWLERS", "CRAWLERS", "DEBUG_CRAWLERS", "FORUM_CRAWLERS", "Crawler"]
