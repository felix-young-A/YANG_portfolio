# 平台 API 端点参考（逆向自 DataTool 智Tool v3.0.0，2026-09）

> 来源：Edge 扩展 `fnojafohdfhmnkbjonengkcfclhkbkcm`（智Tool，v3.0.0）的 `inject.6070000c.js` 中 `getApiMap()` 端点映射表 + `manifest.json` 的 host_permissions CDN 域名白名单。
> 用途：skill 深度扩展"获取直链及媒体"的参考。多数端点需要浏览器会话（页面自带签名/登录态），服务端直连会被反爬拦截，应走 `_browser_intercept_api`（Playwright 拦截页面自身 API 响应）。

## 一、各平台 API 端点

### 抖音（douyin，15 个 web API）
| 端点 | api_name | 用途 |
|------|---------|------|
| `/aweme/v1/web/aweme/detail/` | detail | **作品详情（图片/视频直链）** |
| `/aweme/v1/web/module/feed/` | discover | 发现页推荐流 |
| `/aweme/v2/web/module/feed/` | discover | 发现页推荐流 v2 |
| `/aweme/v1/web/aweme/post/` | recommend | 作者主页作品列表 |
| `/aweme/v1/web/user/profile/other/` | user_profile | 用户主页信息 |
| `/aweme/v1/web/aweme/related/` | related | 相关推荐 |
| `/aweme/v1/web/danmaku/get_v2/` | danmaku | 弹幕 |
| `/aweme/v1/web/tab/feed/` | tab_feed | 底部 tab 流 |
| `/aweme/v1/web/search/item` | search_video | 搜索视频 |
| `/aweme/v1/web/discover/search` | search_user | 搜索用户 |
| `/aweme/v1/web/general/search/single` | search_keyword | 关键词搜索 |
| `/aweme/v1/web/aweme/favorite` | favorite | 点赞列表 |
| `/aweme/v1/web/aweme/listcollection` | listcollection | 收藏列表 |
| `/aweme/v1/web/history/read` | history-read | 浏览历史 |
| `/aweme/v1/web/music/aweme` | music | 音乐作品 |

### TikTok（23 个）+ TikTok Ads（29 个）
关键：`/api/item/detail/`（作品详情）、`/api/post/item_list/`（作者作品）、`/api/user/list`（粉丝）、`/api/comment/list/`、`/api/search/item/full/`、`/api/music/item_list`、`/api/challenge/item_list` 等。
Ads 端：`/creative_radar_api/v1/script/...`、`/popular_trend/...`（创意雷达，广告素材分析）。

### 小红书（xhs，6 个）
| 端点 | 用途 |
|------|------|
| `/api/sns/h5/v1/note_info?note_id=` | **笔记详情（H5，登录墙）** |
| `/api/sns/web/v1/feed` | 笔记详情/信息流（需 X-S 签名） |
| `/api/sns/web/v1/homefeed` | 首页推荐 |
| `/api/sns/web/v1/user_posted` | 作者笔记列表 |
| `/api/sns/web/v1/search/notes` | 笔记搜索 |
| `/api/sns/web/v2/search/notes` | 笔记搜索 v2 |

### 微博（weibo，7 个）
| 端点 | 用途 |
|------|------|
| `/ajax/statuses/show?id=` | **微博详情（图片/视频）** |
| `/ajax/statuses/mymblog` | 博主微博列表 |
| `/ajax/feed/*` | 信息流（unread/group/hot/friendstimeline） |
| `/tv/api/component` | 微博视频播放信息 |

### 头条（toutiao，3 个）
| 端点 | 用途 |
|------|------|
| `/api/pc/list/feed` | 信息流 |
| `/api/pc/list/user/feed` | 用户视频列表 |
| `vod.bytedanceapi.com/?Action=GetPlayInfo` | **视频播放信息（需签名参数）** |

### B站（bilibili，18 个）
关键：`/x/web-interface/wbi/view/detail`（视频详情）、`/x/player/wbi/playurl`（**播放地址，wbi 签名时效**）、`/x/player/wbi/v2`、`/pgc/player/web/v2/playurl`（番剧）、`/x/web-interface/wbi/search/type`（搜索）、`/x/space/wbi/arc/search`（UP 主视频）。

### 其他平台
- **快手**：`/graphql`、`/rest/v/photo/comment/list`、`/rest/v/photo/comment/sublist`
- **Instagram**：`/api/v1/media/`、`/graphql/query`、`/api/v1/discover/web/explore_grid`、`/api/v1/fbsearch/web/top_serp/`
- **X/Twitter**：`/i/api/graphql`（TweetResultByRestId）
- **YouTube**：`/youtubei/v1/player`（播放信息）、`/youtubei/v1/browse`、`/youtubei/v1/next`、`/youtubei/v1/search`
- **Facebook**：`/api/graphql`
- **新片场**：`mod-api.xinpianchang.com/mod/api/v2/media`
- **OnlyFans**：`/api2/v2/`

## 二、平台 CDN 域名白名单（manifest host_permissions）
```
抖音/TikTok:  *.douyinvod.com  *.byteimg.com  *.ibyteimg.com  *.douyinpic.com
头条:        *.toutiaoimg.com *.toutiaovod.com *.toutiaostatic.com  vod.bytedanceapi.com
微博:        *.sinaimg.cn *.weibocdn.com
小红书:      *.xhscdn.com *.xhslink.com
淘宝:        *.aliyuncs.com（oss.datatool.vip / cn-datatool.oss-cn-hangzhou.aliyuncs.com）
```

## 三、CatCatch 猫抓 v2.7.2 嗅探配置参考（Edge 扩展 oohmdefbjalncfplafanlagojlakmjci）
- **扩展名表（Ext）**：flv hlv f4v mp4 mp3 wma wav m4a ts webm ogg ogv acc mov mkv m4s m3u8 m3u mpeg avi wmv asf movie divx mpeg4 vid aac mpd weba opus srt vtt
- **MIME 表（Type）**：audio/* video/* application/ogg application/vnd.apple.mpegurl application/x-mpegurl application/mpegurl application/octet-stream-m3u8 application/dash+xml application/m4s
- **判定函数**：`fileNameParse`（URL pathname 末段取扩展名）→ `CheckExtension`（表查+大小过滤）→ `CheckType`（Content-Type 表查）→ `data.type=="media"`（浏览器资源类型必抓）
- **响应头**：Content-Length / Content-Range（`bytes */total`）取大小；Content-Disposition filename 取文件名扩展名
- **站点正则规则表**：可配置 URL 正则（如 bilibili live-bvc m4s 黑名单、Instagram bytestart 分段去重等）
- **M3U8**：hls.js 解析 master（按 BANDWIDTH 选最高档）+ EXT-X-KEY 解密 + EXT-X-MAP init segment
