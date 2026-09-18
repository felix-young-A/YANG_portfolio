---
name: media-link-resolver
description: |
  社媒平台媒体直链解析与嗅探。将国内 25+ / 海外 15+ 平台（小红书、微博、抖音、Instagram、Bilibili、YouTube、百度、Pinterest、Reddit、Facebook 等 44+ 项规则）的 CDN 链接、签名链接、短链、网页链接转换为永久直链或最优直链。支持猫抓式页面嗅探（--sniff）从网页中提取媒体直链，支持 M3U8/MPD 流解析。
  媒体类型全覆盖：图片(Image)、GIF、动图（Animated WebP / APNG / LivePhoto 动态）、视频(Video)、音频(Audio)、流媒体(Stream)，通过 URL 特征 + HTTP 魔数探测 + 响应头三重识别，静态图片与动图不混淆。
  使用场景：(1) 需要永久直链写入 records (2) 签名过期链接需要转换 (3) 批量解析多平台链接 (4) 从网页中嗅探提取所有媒体 (5) 小红书 sns-webpic 转 ci.xiaohongshu.com 永久链接 (6) 微博无水印原图 (7) Obsidian Records Manager 渲染前直链升级 (8) 抖音/带签名媒体 --save 永久化落盘 (9) 小红书/微博笔记页浏览器拦截 API 解析 (10) M3U8 master 选最高清档 (11) 抖音 slides/视频作品 video_id → 永久转播入口链（免 Referer / 无签名，长期可引用）
---
# Media Link Resolver v4.8
社媒平台媒体直链解析器，**44+ 条规则，覆盖国内 25+ / 海外 15+ 平台，优先返回永久直链**。

**v4.8 修正（2026-09-17）抖音 vid 提取回退（实测踩坑）：**
- 部分 slides 详情响应中 `images[i].video.uri` **为空**，真实 vid 在 `images[i].video.play_addr.uri`（形如 `v0200fg10000dal8p1vog65thq9b1jo0`）。v4.8 起新增 `_douyin_vid()`，按 `video.uri → play_addr.uri → play_addr_h264/lowbr → bit_rate[].play_addr.uri` 顺序回退提取，且**只接受纯 id 形态**（不含 `http`、不含 `/`），避免把 BGM mp3 URL 误当 vid 生成废链。
- 实测案例（aweme_id `7686110919500390729`，slides 5 片）：仅第 1 片有视频流且 `video.uri` 为空 → 回退 `play_addr.uri` 后成功生成永久入口链（实测 200 video/mp4，642015 字节）。**slides 可"图 + 视频"混合，并非每片都有入口链**，v4.8 输出会附"作品共 N 片 / M 片带视频流"说明。

**v4.7 新增（2026-09-16）抖音【永久转播入口链】：**
- **作品类型判定（v4.8 增强）**：`aweme_detail` 能解析出 vid（`video.uri`，为空回退 `play_addr.uri`）= 有视频流；slides（幻灯片/图集带视频流）作品每片 `images[i].video.uri`（为空回退 `play_addr.uri`）即该片 vid；纯图文 note 无 video 字段。
- **永久入口链**：`https://aweme.snssdk.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0`——免 Referer、无签名、每次请求 302 到新签名的 douyinvod（实测 200 video/mp4），**可长期引用**；备用主机 `www.douyin.com`、`api.amemv.com`。
- **适用面**：slides 每片视频与普通视频作品均可用 `video.uri` 生成入口链；**图片直链仍强制签名（约 30 天）**，长期保存仍需 `--save` 落盘。
- **新增 CLI**：`--play-entry <vid>` 直接把 video_id 转永久入口链（支持多值 / 逗号分隔，`--json` 输出备用入口）。
- **更正**：抖音图片直链的 Referer **可省略**（`x-signature` 等签名参数必带）——此前文档标注"需 Referer"过于严格。v4.3 新增：抖音官方 play 中转链接识别（可渲染视频）、BGM 音频直链提取（无防盗链）、抖音 CDN 有效期实测（douyinvod 约 14 天 / 中转链接滚动签名）。**v4.4 新增：抖音图文 `img_bitrate` 高清档位、jpeg 副档、`download_url_list` 水印版排除、SSR `_ROUTER_DATA` 深度解析、高清/永久化自动探测。** **v4.5 新增：抖音新版客户端渲染分享页 detail API + Playwright 浏览器兜底、`--save` 永久化落盘、签名过期时间输出、动图误判修正。**

**v4.6 新增（逆向 CatCatch 猫抓 v2.7.2 + DataTool 智Tool v3.0.0 浏览器扩展）：**
- **完整媒体扩展名 + MIME 类型表**（猫抓 init.js）：47 种扩展名（补 hlv/f4v/m4s/mpeg/divx/vid/asf/weba/opus 等）+ 9 类 MIME（audio/*、video/*、各类 mpegurl、dash+xml、m4s），嗅探判定更全。
- **响应头嗅探**（猫抓 findMedia 三重判断思路）：扩展名/魔数无法判定的 URL，按 Content-Type / Content-Length / Content-Range / Content-Disposition 判定媒体类型与大小。
- **M3U8 master 选最高清档**（猫抓 hls.js 思路）：解析 `#EXT-X-STREAM-INF` 的 BANDWIDTH/RESOLUTION，按带宽从高到低排序输出（最高清档在前）。
- **平台 CDN 域名识别**（智Tool manifest host_permissions）：9 大平台 CDN 域名清单（douyinvod/douyinpic/byteimg、xhscdn、sinaimg、toutiaovod、bilivideo、yximgs 等），嗅探结果自动标注平台。
- **小红书笔记页解析**（智Tool API map：`/api/sns/h5/v1/note_info` + `/api/sns/web/v1/feed`）：浏览器拦截详情 API 提取视频（h264 master_url / origin_video_key）与图片（url_default/url_pre/url_720w），有登录墙时明确提示。
- **微博详情页解析**（智Tool API map：`/ajax/statuses/show` + `/tv/api/component`）：浏览器拦截提取图片（oslarge 无水印永久）与视频（mp4_720p/mp4_hd 等）。
- **通用浏览器拦截器 `_browser_intercept_api`**：打开页面 → 拦截页面自身 JSON API 响应（页面已自带签名/登录态），解决签名类反爬。

## 快速使用
```bash
# 单条 URL 解析
python3 scripts/resolve_media_links.py "https://sns-webpic-qc.xhscdn.com/..."
# 批量解析（文件每行一个 URL）
python3 scripts/resolve_media_links.py --batch urls.txt
# JSON 输出
python3 scripts/resolve_media_links.py --json "url1" "url2"
# 猫抓式页面嗅探（从网页提取所有媒体直链，自动按 CDN 标注平台）
python3 scripts/resolve_media_links.py --sniff "https://weibo.com/abc/xxx"
# 【v4.5】抖音等带签名媒体永久化落盘（下载到本地，永久保存）
python3 scripts/resolve_media_links.py --save /path/to/vault/attachments "https://v.douyin.com/xxxx"
# 【v4.6】小红书/微博笔记页 → 浏览器拦截详情 API 提取视频/图片
python3 scripts/resolve_media_links.py "https://www.xiaohongshu.com/explore/{note_id}"
python3 scripts/resolve_media_links.py "https://weibo.com/{uid}/{status_id}"
# 【v4.7】抖音 video_id（video.uri / slides 每片 uri）→ 永久转播入口链
python3 scripts/resolve_media_links.py --play-entry v0200f1a2b3c
python3 scripts/resolve_media_links.py --play-entry "vid1,vid2" --json
# 抖音分享页解析（自动识别 slides 作品并输出每片永久入口链）
python3 scripts/resolve_media_links.py "https://v.douyin.com/xxxx/"
# 列表全部平台
python3 scripts/resolve_media_links.py --platforms
```
> 依赖：抖音/小红书/微博浏览器兜底需要 `playwright` + chromium（默认 `/usr/local/bin/chromium`，可用环境变量 `DOUYIN_CHROME` 覆盖）。小红书/微博详情页有登录墙，需在已登录浏览器会话中解析。其余平台仅需 `requests`。

## 工作流程
### 模式 A：直链解析（resolve_url）
1. **识别平台**：URL 域名匹配 PLATFORM_RULES（44 项规则表）
2. **转换直链**：调用平台解析器，优先输出永久直链
3. **标注时效**：permanent=True/False/None + 时效提示 + **v4.5 签名过期时间**
4. **媒体类型**：猫抓式扩展名 + CDN 特征双重识别（image/gif/animated/video/audio/stream），动图（Animated WebP/APNG）通过 HTTP 魔数探测识别（**v4.5：需 ANIM+ANMF 帧才算动图**）
5. **永久化落盘**：`--save <DIR>` 时把 `permanent=False` 的媒体全部下载到本地目录
### 模式 B：页面嗅探（sniff_page，猫抓式 + DataTool 式）
1. **请求页面**：模拟浏览器 UA（支持 mobile UA 切换）
2. **平台解析器优先**：短链/分享页先走平台规则（如抖音 v.douyin.com → 302 → SSR → **detail API + 浏览器兜底**）
3. **HTML 提取**：img/video/audio/source 标签 src + meta og: + 内嵌 JSON（display_url, videoUrl, playAddr 等）
4. **动图/视频探测**：对 .webp/.png/无扩展名等无法静态判定的 URL，HTTP 拉取文件头做魔数探测（GIF8 / RIFF+WEBP+ANIM+ANMF / PNG+acTL / ftyp / ID3 / #EXTM3U）
5. **流媒体解析**：M3U8 播放列表 → 提取分片/最高码率流；MPD → BaseURL 提取
6. **递归解析**：对提取到的媒体 URL 再走一遍模式 A 的直链解析

## 媒体类型识别（6 类）
| 类型 | 内部标识 | URL 特征 | HTTP 魔数探测 |
|------|---------|---------|--------------|
| 图片 | image | .jpg/.jpeg/.png/.webp 等 + CDN 特征 | JPEG `FFD8FF` / PNG `89504E47` / WebP 无 ANIM+ANMF |
| GIF | gif | .gif / f=gif / soogif | `GIF87a` / `GIF89a` |
| 动图 | animated | .gifv / animated / livephoto / webm | Animated WebP `RIFF+WEBP+ANIM+ANMF` / APNG `PNG+acTL` |
| 视频 | video | .mp4/.mov/.webm + /video/tos/ + douyinvod | MP4 `ftyp` / WebM `1A45DFA3` |
| 音频 | audio | .mp3/.m4a/.flac 等 | ID3 / `FFFB` |
| 流媒体 | stream | .m3u8/.mpd | `#EXTM3U` / MPD BaseURL |
> 判定优先级（v4.6 三重识别）：**扩展名 + CDN 特征（detect_media_type）→ HTTP 魔数探测（probe_media_type）→ 响应头嗅探（sniff_media_headers：Content-Type/Content-Length/Content-Range/Content-Disposition）**。嗅探结果自动按 CDN 域名标注平台（智Tool manifest 域名清单）。
> 注意：抖音图片 CDN 的部分 WebP 带 VP8X 扩展头（含 ICCP/ALPH 等元数据）但**没有 ANIM+ANMF 帧 = 静态图**，v4.5 不再误判为动图。

## 核心规则（44 条，按优先级）
| 分类 | 覆盖平台 | 永久化策略 |
|------|---------|-----------|
| 国内图床 | 小红书/微博/百度/搜狐/腾讯/堆糖/花瓣/Soogif/OPPO/100VR/数英/Doooor | 去签名 / 域名替换，永久 |
| 海外图床 | Pinterest/Reddit(i.redd.it)/Imgur | 原样保留，永久 |
| 视频嵌入 | Bilibili/YouTube/Vimeo/Dailymotion | 官方播放器嵌入链接，永久 |
| 国内社交 | 知乎/微信公众号/简书/CSDN/掘金/微博 | 图床永久，页面链接直出 |
| 有时效 | 抖音/TikTok/Instagram/Facebook/X(Twitter)/爱给/摄图/必应/Google | 无法永久 → **--save 落盘本地**或重新提取 |
| 需嗅探 | Notion/SoundCloud/VK/Niconico | 页面嗅探提取媒体 |
| 无公开直链 | 爱奇艺/优酷/腾讯视频/斗鱼/虎牙/Twitch | 仅页面链接，注明限制 |

## 抖音专项（v4.7 完整链路）
```
v.douyin.com 短链 ──302──▶ iesdouyin.com/share/note/<id>（新版=客户端渲染，SSR 无图）
                                    │
          ┌─────────────────────────┴──────────────────────────┐
          ▼                                                     ▼
    SSR _ROUTER_DATA（旧版/视频页有效）                    detail API（aweme/v1/web/aweme/detail）
    img_bitrate ~q80 原图直出                                     │
          │                                           纯 requests 被反爬拦截时
          ▼                                                    ▼
    提取 url_list[0] ──────────────┐              Playwright 无头浏览器兜底
                                   │              （douyin.com+分享页拿cookie/msToken
                                   ▼               → APIRequestContext 调 detail）
          ├─ 纯图文：图片直链（带 x-signature，30天）＋ --save 永久化落盘
          └─ slides / 视频作品：video.uri / images[i].video.uri → 永久转播入口链（v4.7）
```
- **永久性实测（2026-09-02）**：`p3-pc-sign.douyinpic.com` 等图片 URL 的 `x-signature` 为 HMAC 强制签名；去签名 / 换 `p3.douyinpic.com` 无 sign 域名 / 去模板 / 换模板一律 400/403；签名有效期 `aweme_images` ≈ 30 天（`x-expires`），reflow 类 ≈ 4 天。
- **视频**：`douyin.com/aweme/v1/play/` 官方中转 302 滚动签名，无固定过期，可直接嵌入；`douyinvod.com` 原链约 14 天。
- **BGM 音频**：`douyinstatic.com` music 域无防盗链，永久可播。

### 作品类型判定（v4.7，先判类型再取链）
| 判据 | 类型 | 取链策略 |
|------|------|---------|
| 顶层能解析出 vid（`video.uri`，为空回退 `play_addr.uri`） | 视频作品 | **永久入口链**（首选）；`play_addr` CDN 直链仅作回退 |
| `images[i]` 能解析出 vid（`video.uri`，为空回退 `play_addr.uri`） | slides 幻灯片 / 图集带视频流 | 每片 vid → 各生成一条**永久入口链**（一片一条，顺序即播放顺序）；**仅"带视频流"的片有链**，纯图片片只给图片直链 |
| 仅 `images[i].uri`，无 video 字段 | 纯图文 note | **无 play 入口链**；图片直链带 x-signature（约 30 天）→ 需 `--save` 落盘 |

### 永久转播入口链（v4.7 实测，2026-09-16）
```
https://aweme.snssdk.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0
```
- `vid` = 作品可解析出的 video_id：视频作品取顶层 `video.uri`；slides 每片取 `images[i].video.uri`，**为空则回退** `video.play_addr.uri`（v4.8 实测：多数 slides 片 `uri` 为空、必须在 `play_addr.uri` 里取，一处作品可产出多条 vid）。
- 特性：**免 Referer、无签名参数**，每次请求 302 到新签名的 douyinvod 地址，实测返回 200 `video/mp4`——**无固定过期，可长期引用**（与"签名直链必过期"结论互补：入口链靠 video_id 换签名，图片 CDN 无此机制）。
- 备用主机（主入口异常时依次回退）：`https://www.douyin.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0`、`https://api.amemv.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0`。
- CLI：`--play-entry <vid>` 直接生成；解析分享页时脚本已自动对 slides / 视频作品输出入口链（SSR 与 detail API 两条通路均覆盖）。
- 渲染：可嵌入 `<video>` / `<audio>`（无防盗链，无需 Referer 头）；避免抽干式高频调用（风控）。

## 猫抓式嗅探详解
参考 [CatCatch 猫抓扩展](https://blog.csdn.net/gitblog_00290/article/details/159747143) 资源嗅探引擎思路：
1. **请求拦截**：模拟浏览器网络请求（fetch_page）
2. **MIME 识别**：Content-Type 判断（video/mp4, audio/mpeg 等），通过 URL 特征（mime_type 参数、CDN 路径）识别
3. **URL 模式匹配**：文件扩展名（mp4/m3u8/mpd/mp3）+ 流媒体协议（m3u8/mpd/DASH）
4. **HTML 提取**：img/video/audio/source 标签 + meta og: + 内嵌 JSON（window.__INITIAL_STATE__、__NEXT_DATA__ 等）
5. **流解析**：M3U8 解析分片列表和最高码率流；MPD 提取 Representation
6. **防重复/黑名单**：自动去重，排除广告/小文件

## 参考：浏览器扩展逆向分析（v4.6，2026-09）
### CatCatch 猫抓 v2.7.2（Edge 扩展 oohmdefbjalncfplafanlagojlakmjci）
- **机制**：网络层嗅探器。`webRequest` 全站监听（`*://*/*`），`findMedia()` 三重判断：URL 扩展名（32 种）→ Content-Type（9 类）→ 浏览器资源类型 `media`，辅以 Content-Length/Content-Range 大小过滤 + 站点级正则规则表。
- **可移植能力**：完整扩展名/MIME 表（已并入 `CATCATCH_EXTENSIONS`/`CATCATCH_MIME`）、响应头嗅探（已并入 `sniff_media_headers`）、M3U8 按 BANDWIDTH 选最高档（已并入 `parse_m3u8`）。
- **局限**：纯浏览器运行时方案（需 webRequest 权限实时监听网络），无法直接服务端化；对带签名 CDN 只"抓到"不改写。

### DataTool 智Tool v3.0.0（Edge 扩展 fnojafohdfhmnkbjonengkcfclhkbkcm）
- **机制**：平台专项下载器。页面注入 content script 拦截平台自身 API 响应（fetch/XHR hook，页面已自带签名/登录态）→ 提取媒体 URL；商业版上传 `api.datatool.vip` 解析。
- **API 端点映射**（已并入 skill 文档与解析器）：
  - 抖音 15 个 web API（feed/post/profile/related/detail/search/favorite/music）
  - TikTok 23 个（/api/item/detail/、/api/post/item_list/）+ tiktok_ads 29 个
  - 小红书 6 个（/api/sns/h5/v1/note_info、/api/sns/web/v1/feed、homefeed、user_posted）
  - 微博 7 个（/ajax/statuses/show、/tv/api/component）
  - 头条 3 个（/api/pc/list/feed、vod.bytedanceapi.com GetPlayInfo）
  - B站 18 个（/x/web-interface/wbi/...、/x/player/wbi/playurl）
  - 快手 3 个（/graphql、/rest/v/photo/...）、Instagram 6 个（/api/v1/media/）、X 2 个（/i/api/graphql）、YouTube 7 个（/youtubei/v1/player）
- **可移植能力**：平台 API 端点清单（已用于小红书/微博浏览器拦截解析器 `_browser_intercept_api`）、CDN 域名白名单（已并入 `PLATFORM_CDN_DOMAINS`）。
- **局限**：需要页面加载 + 登录态（小红书/微博有登录墙）；核心解析依赖其付费后端。

## 不要做
- 不要对永久化平台返回带签名参数的原始 URL（优先输出永久直链）
- 不要将过期 CDN 链接（如 sns-webpic、cdninstagram）当作永久链接写入 records
- 不要编造不存在的视频直链；无法提取时明确返回"需要请求页面嗅探提取"
- 不要跳过 fileId 路径前缀（`spectrum/`、`notes_pre_post/`），否则 404
- 不要猜测需要登录的平台（OnlyFans 等）的直链，明确提示需要登录态
- **不要笼统说抖音"没有任何永久链"**（v4.7 更正）：**视频流**已有 `video_id` 永久转播入口链（slides 与视频作品通用，免 Referer、无签名、可长期引用）；**图片流**才强制签名（约 30 天），必须 `--save` 落盘本地或转存自有图床才算永久。判定顺序：先用 `_douyin_vid()` 看能否解析出 vid（`video.uri` 为空时回退 `play_addr.uri`）。
- 不要把 slides 作品当"纯图文"只输出图片直链——能解析出 vid 的片必须先输出每片永久入口链，再附图片直链。
- **不要只查 `video.uri` 就判定"无视频流"**（v4.8 踩坑）：`uri` 为空 ≠ 无视频，必须回退 `play_addr.uri`；同时注意 slides 顶层 `video.play_addr.uri` 可能是 BGM mp3 URL，**回退值须做纯 id 校验**（不含 `http` / `/`）后再拼入口链。
