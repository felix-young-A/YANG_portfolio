# 各平台直链解析方法论（v4.0）

> 依据：用户 records_data.json 实际收录平台分布 + Record_Manager 渲染引擎 PLATFORM_RULES 支持清单 + 猫抓(CatCatch)/DataTool 实现思路。
> 核心原则：**优先永久直链**；无法永久化的平台给出最优直链并提示时效性。
> 版本记录：v4.0（2026-08-07）新增猫抓式页面嗅探模块（M3U8/MPD 流解析 + HTML/内嵌JSON 提取 + MIME 识别）、海外平台（Pinterest/Reddit/Imgur/Facebook/SoundCloud/VK/Niconico）、媒体类型扩展（音频/流媒体/更多格式）。

---

## 0. 平台总览

### 0.1 用户实际数据中的平台（records_data.json，46 条记录）

| 平台 | 条数 | 类型分布 | 域名特征 | 可永久化 |
|------|-----|---------|---------|---------|
| 小红书 | 9 | GIF / Portrait / Landscape | ci.xiaohongshu.com / xhscdn.com | ✅ |
| 百度 | 6 | GIF | pic.rmb.bdstatic.com / hiphotos.baidu.com / img2.baidu.com | ✅ |
| 微博 | 5 | GIF | ww*.sinaimg.cn | ✅ |
| Instagram | 4 | Portrait | scontent-*.cdninstagram.com | ❌（过期） |
| 搜狐 | 4 | GIF | q*.itc.cn / p*.itc.cn | ✅ |
| 抖音 | 3 | Portrait / Video | p*.douyinpic.com | ❌（签名） |
| 爱给网 | 3 | GIF | s1.aigei.com | ❌（token） |
| 堆糖 | 2 | GIF | c-ssl.duitang.com | ✅ |
| 摄图网 | 2 | GIF | wimg.588ku.com | ❌（有时效） |
| Bilibili | 1 | Video | player.bilibili.com | ✅ |
| 必应 | 1 | GIF | ts1.tc.mm.bing.net | ⚠️（还原原图） |
| 数英 | 1 | Portrait | file.digitaling.com | ✅ |
| Doooor | 1 | GIF | img.doooor.com | ✅ |
| 花瓣 | 1 | GIF | gd-hbimg.huaban.com | ✅ |
| 腾讯 | 1 | GIF | inews.gtimg.com | ✅ |
| OPPO | 1 | GIF | imgfs.oppo.cn | ✅ |
| 100VR | 1 | GIF | file.100vr.com | ✅ |
| Soogif | 1 | GIF | img.soogif.com | ✅ |

### 0.2 渲染引擎支持的全部平台（Record_Manager PLATFORM_RULES，38 项）

视频嵌入类：Bilibili / YouTube / Vimeo / Dailymotion / 爱奇艺 / 优酷 / 腾讯视频 / Twitch / 斗鱼 / 虎牙
社交类：X (Twitter) / 知乎 / 微博
受限平台：抖音 / TikTok / 小红书 / Instagram / 快手
内容平台：微信公众号 / 简书 / CSDN / 掘金 / Notion
图床 CDN：微博图床 / 百度 / 腾讯 / Soogif / 花瓣 / 堆糖 / 摄图网 / 爱给网 / 必应 / Google / OPPO / 100VR / 数英 / Doooor

---

## 1. 小红书（永久方案最成熟）

> **v4.6 新增**：笔记页/短链 → 浏览器拦截详情 API（`/api/sns/h5/v1/note_info`、`/api/sns/web/v1/feed`，智Tool API map）提取视频（h264 master_url / origin_video_key）与图片（url_default/url_pre/url_720w）。小红书有**登录墙**（未登录 note_info 返回空 data），需已登录浏览器会话。

### 1.1 链路总览

```
xhslink短链 ──→ 302重定向 ──→ 笔记长链 ──→ GET笔记HTML ──→ 正则提取JSON数据
                                                          │
                    ┌─────────────────────────────────────┼─────────────────────────────────────┐
                    │                                     │                                     │
                    ↓                                     ↓                                     ↓
              图片(fileId)                          Live/视频(stream)                      视频笔记(video)
                    │                                     │                                     │
                    ↓                                     ↓                                     ↓
        ci.xiaohongshu.com                    sns-video-*.xhscdn.com                 originVideoUrl
        无签名 · 永久有效                        sign+t · 30分钟过期                      带签名 · 时效
```

### 1.2 短链还原（必须移动端 UA）

```python
import requests

def resolve_short(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
    }
    resp = requests.get(url, headers=headers, allow_redirects=True, timeout=10)
    return resp.url  # 真实笔记地址
```

### 1.3 图片永久直链（核心方法）

关键规则：**fileId 必须保留完整路径前缀**（`spectrum/` 或 `notes_pre_post/`），只取文件名会 404。

```python
import re

def clean(s: str) -> str:
    return s.replace(r'\u002F', '/').replace(r'\/', '/')

# 提取完整 fileId（含路径前缀）
file_ids = [clean(f) for f in re.findall(r'"fileId"\s*:\s*"([^"]+)"', html)]

# 拼接永久直链
for fid in file_ids:
    webp = f"http://ci.xiaohongshu.com/{fid}!nd_dft_wgth_webp_3"   # WebP ~60KB 永久
    raw  = f"http://ci.xiaohongshu.com/{fid}"                        # 原图 ~650KB 永久
```

- `!nd_dft_wgth_webp_3` 后缀 = WebP 压缩版（渲染首选，体积小）
- 无后缀 = 原始 PNG/JPEG
- `http://` 即可，Obsidian 图片加载会自动尝试 https

### 1.4 Live Photo / 视频（30 分钟时效）

```python
# Live 标志
live_flags = re.findall(r'"livePhoto"\s*:\s*(true|false)', html)
# 视频直链
master_urls = [clean(u) for u in re.findall(r'"masterUrl"\s*:\s*"([^"]+)"', html)]
# 原片
origin_videos = [clean(u) for u in re.findall(r'"originVideoUrl"\s*:\s*"([^"]+)"', html)]
```

画质优先级：`originVideoUrl`（原片）> `videoUrl`（转码）> `stream.masterUrl`（多码率）。
视频链接带 `sign=` + `t=`，约 30 分钟过期，需重新请求笔记页刷新或立即下载。

### 1.5 异常排查

| 现象 | 根因 | 解决 |
|------|------|------|
| 短链 404 | PC UA 被拦截 | 换 iPhone UA |
| 视频 403 | sign 过期 | 重新请求笔记页 |
| 图片 403 | 用了 sns-webpic 域名 | 换 ci.xiaohongshu.com |
| 图片 404 | fileId 丢了前缀 | 保留完整 fileId（spectrum/ 等） |
| 提取 0 条 | 正则不匹配 | 检查 JSON 转义，先 clean() |

### 1.6 关键正则

```python
r'"fileId"\s*:\s*"([^"]+)"'          # 图片 fileId（完整路径）
r'"masterUrl"\s*:\s*"([^"]+)"'       # Live/视频
r'"originVideoUrl"\s*:\s*"([^"]+)"'  # 视频原片
r'"livePhoto"\s*:\s*(true|false)'    # Live 标志
```

---

## 2. 微博（永久方案成熟）

> **v4.6 新增**：详情页 `weibo.com/{uid}/{status_id}` → 浏览器拦截 `/ajax/statuses/show` + `/tv/api/component`（智Tool API map）提取图片（pic_ids → oslarge 无水印永久）与视频（media_info.mp4_720p_mp4 / mp4_hd_url 等）。微博详情需登录态，未登录时明确提示。

### 2.1 URL 结构

```
https://wx4.sinaimg.cn/{size}/{filename}
                 ↑         ↑
             子域(可换)    尺寸标识
```

### 2.2 尺寸替换规则（永久直链）

| 尺寸标识 | 说明 | 优先级 |
|---------|------|-------|
| `oslarge` | 无水印大图 | 🥇 首选 |
| `large` | 原图（无裁剪） | 🥈 |
| `mw690` / `mw1024` | 中等尺寸 | 🥉 |
| `thumb150` | 缩略图 | 仅渲染用 |

```python
def resolve_weibo(url):
    m = re.search(r'(wx\d+|ww\d+|n)\.sinaimg\.cn/(\w+)/(.+\.\w+)', url)
    if m:
        sub, size, filename = m.group(1), m.group(2), m.group(3)
        base = f"https://{sub}.sinaimg.cn"
        return [
            f"{base}/oslarge/{filename}",   # 无水印大图
            f"{base}/large/{filename}",     # 原图
            f"{base}/{size}/{filename}",    # 当前尺寸
        ]
```

注意：新浪图床理论上长期有效，但极老图片可能被清理。

---

## 3. 百度（永久方案成熟）

| 域名 | 永久性 | 处理 |
|------|--------|------|
| `pic.rmb.bdstatic.com` | ✅ 永久 | 去掉 query 参数 |
| `hiphotos.baidu.com/feed/` | ✅ 永久 | 原样保留 |
| `img2.baidu.com/it/u=...` | ⚠️ 签名 | 原样保留（含 fm/app/f 参数） |
| `ts1.tc.mm.bing.net` | ⚠️ 缓存 | 见必应章节 |

```python
if 'pic.rmb.bdstatic.com' in url:
    return [url.split('?')[0]]   # 去签名保留永久
```

---

## 4. Instagram（时效，需重新提取）

### 4.1 CDN 链接特征

```
https://scontent-{region}.cdninstagram.com/v/t51.82787-15/{id}_n.jpg?stp=...&_nc_cat=...&oh=...&oe=...
```

此类链接带 `oh`/`oe` 签名，**几小时到几天内过期**，不可作为永久链接。

### 4.2 重新提取方法

```python
import re

def extract_ig_shortcode(url):
    m = re.search(r'/(p|reel|tv)/([A-Za-z0-9_-]+)', url)
    return (m.group(1), m.group(2)) if m else None
```

拿到 shortcode 后，请求 `https://www.instagram.com/p/{shortcode}/`（PC UA），从 HTML 内嵌 JSON 中提取最新 `display_url` 和 `video_url`。

### 4.3 注意

- 新提取的 CDN 链接同样有时效 → 渲染建议用 `cdninstagram.com` 直链 + `onerror` 兜底
- 最佳实践：**下载到本地 vault**，避免反复失效

---

## 5. 抖音（时效，建议下载 / v4.5 支持 --save 永久化落盘）

| 域名 | 类型 | 时效 |
|------|------|------|
| `p*.douyinpic.com` | 图片 / **动图**（LivePhoto 为 Animated WebP） | 签名过期（`aweme_images` ≈ **30 天**，reflow ≈ 4 天） |
| `*.douyinvod.com` | 视频 | 带 `x-expires`（约 14 天），到期 403 |
| `douyin.com/aweme/v1/play/` | 视频（官方中转） | 每次请求 302 刷新签名，可持续使用 |
| `aweme.snssdk.com/aweme/v1/play/?video_id=<vid>` | 视频 / slides 含视频流的片（**永久转播入口链**，v4.7；vid 提取 v4.8 增强） | **无签名、免 Referer，无固定过期** |
| `*.douyinstatic.com`（music 域） | 音频 BGM | **无防盗链，永久可播** |
| `v.douyin.com` | 短链 | 需请求解析 |
| `iesdouyin.com` | 分享页 | 需请求解析 |

解析方式：短链 → 302 重定向到 `iesdouyin.com/share/note/{id}` → 提取 `images` 数组（每图 url_list[0]）或视频字段（playAddr 等）→ 直链返回并做 HTTP 魔数探测。
**v4.5 关键升级**：抖音**新版客户端渲染分享页**（SSR `_ROUTER_DATA` 只有页面框架、无图片）→ 降级 `aweme/v1/web/aweme/detail` 接口（需 cookie/msToken，纯 requests 会被反爬拦截返回空）→ **Playwright 无头浏览器兜底**（访问 douyin.com + 分享页拿会话 → APIRequestContext 调 detail 接口 → `aweme_detail.images[].url_list`）。
注意：**图文 LivePhoto 的直链是 Animated WebP 动图**（URL 看似 .webp 静态，文件头带 VP8X+ANIM+ANMF）；但普通图文 WebP 可能只有 VP8X 扩展头（ICCP 等）无 ANIM 帧 = **静态图**，v4.5 已修正不误判。

### 永久转播入口链（v4.7 实测，2026-09-16）
**slides / 视频作品有永久入口链，图片流没有**：
- **作品判定（v4.8 增强）**：能解析出 vid（顶层 `video.uri`，**为空回退 `play_addr.uri`**）= 视频作品；`images[i]` 能解析出 vid（`video.uri` → 为空回退 `play_addr.uri`）= slides（幻灯片 / 图集带视频流），每片一个 vid；纯图文 note 无 video 字段。
- **入口链**：`https://aweme.snssdk.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0`，备用主机 `www.douyin.com`、`api.amemv.com`。
- **v4.8 实测踩坑（2026-09-17）**：slides 详情响应中 `images[i].video.uri` **常为空**，vid 实际藏在 `images[i].video.play_addr.uri`（形如 `v0200fg10000dal8p1vog65thq9b1jo0`）；且 slides 可"图 + 视频"混合（实测 aweme_id `7686110919500390729` 共 5 片、仅第 1 片有视频流），**并非每片都入口链**。回退值须做纯 id 校验（不含 `http` / `/`），否则会把顶层 BGM mp3 URL 误当 vid 拼出废链。
- **实测**：免 Referer / 无签名，请求即 302 到新签名 douyinvod，返回 200 `video/mp4`；可嵌入 `<video>` 与 records 渲染，**无固定过期**（靠 video_id 换签名，与图片流的强制签名机制本质不同）。
- **CLI**：`--play-entry <vid>`；分享页解析已自动输出（SSR 与 detail API 两条通路均覆盖）。
- 注意：避免抽干式高频调用触发风控；BGM 仍走 douyinstatic 域（无防盗链）。

### 永久性结论（2026-09 实测，v4.5；**仅适用图片流**）
**抖音图片 CDN 强制签名，不存在可原样长期有效的直链**（视频流见上一节 v4.7 永久入口链）：
- `p*-sign.douyinpic.com` 的 `x-signature` 为 HMAC，签名参数缺失/篡改 → 400/403
- 换成无 sign 域名（`p3.douyinpic.com`）→ 403（私有桶拒绝匿名访问）
- 去模板 / 换模板 / 去 query → 403
- 签名有效期：`aweme_images` 图文 ≈ 30 天，`DOUYIN_REFLOW` 流式 ≈ 4 天（可从 `x-expires` 解析）

**唯一永久方案 = 下载转存**：
```bash
# 抖音等带签名媒体永久化落盘（v4.5）
python3 scripts/resolve_media_links.py --save /path/to/vault/attachments "https://v.douyin.com/xxxx"
# → 返回本地文件路径（永久），同时打印原始直链（时效）
```
- 首选：下载到 Obsidian vault 附件目录（本地文件 100% 永久、离线、无第三方依赖）
- 次选：转存自有图床/CDN
- 辅助：Obsidian 渲染时效直链时配合 `<img onerror>` 兜底 + 占位

### 视频渲染方案（2026-08 实测）
- **`douyinvod.com` 直链防盗链**：必须带 `Referer: https://www.douyin.com/`，否则 403；Obsidian 内嵌 `<video>` 不带 Referer 播不了。
- **`douyin.com/aweme/v1/play/?...` 官方中转**：302 自动带 douyin Referer 可播放（200 video/mp4），是 records 渲染的推荐链接；链接签名来自 SSR `aweme.detail.video`，每次请求都会 302 到新签名的 douyinvod URL，无固定过期（但抽干式调用会触发风控）。
- **v4.7 首选：`aweme.snssdk.com/aweme/v1/play/?video_id=<vid>&ratio=1080p&line=0` 永久转播入口链**——只需 `video_id`（取自 `video.uri` 或 slides 的 `images[i].video.uri`，**为空回退 `play_addr.uri`，v4.8**），免 Referer、无签名、无固定过期，slides 含视频流的片同样适用；无 Referer 的 `<video>` / `<audio>` 标签可直接播放。
- **BGM 提取**：SSR/分享页 JSON 中 `music.play_url`（域名 `lf*-music-east.douyinstatic.com/obj/ies-music-hj/*.mp3`）**无 Referer 限制**，可直接作为音频链接嵌入 `<audio>`；与视频同长的混音方案：`ffmpeg -i video.mp4 -i bgm.mp3 -t <视频时长> -c:v copy -c:a aac -shortest out.mp4`。

无永久直链方案 → 最佳实践：**`--save` 落盘本地 / 转存自有图床（永久）**，或保留时效直链并在 Obsidian 渲染时配合 `onerror` 兜底显示占位。
> **v4.7 更正**：该结论**仅对图片流成立**。视频流（含 slides 每片）改用 `video_id` 永久转播入口链，无需落盘即可长期引用。

---

## 6. TikTok（时效，同抖音）

- `*.tiktokcdn.com` 视频/图片链接带签名时效
- 页面链接需请求 `https://www.tiktok.com/@{user}/video/{id}` 提取直链
- 无永久方案 → 下载保存

---

## 7. Bilibili（永久嵌入方案）

```python
# 视频 → 官方播放器嵌入（永久）
r'bilibili\.com/video/(BV[\w]+)'  →  https://player.bilibili.com/player.html?bvid={bvid}&high_quality=1&danmaku=0
```

- 支持 `b23.tv` 短链（需先还原，或直接匹配 bvid 参数）
- 渲染引擎已内置 iframe 嵌入支持（16:9）

---

## 8. YouTube / Vimeo / Dailymotion（永久嵌入方案）

| 平台 | 匹配 | 嵌入链接 |
|------|------|---------|
| YouTube | `watch?v={11位ID}` / `youtu.be/{ID}` | `https://www.youtube.com/embed/{ID}` |
| Vimeo | `vimeo.com/{数字ID}` | `https://player.vimeo.com/video/{ID}` |
| Dailymotion | `dailymotion.com/video/{ID}` | `https://www.dailymotion.com/embed/video/{ID}` |

---

## 9. 爱奇艺 / 优酷 / 腾讯视频（无公开直链）

- 无稳定永久直链 API
- 渲染建议：保留原页面链接 + iframe 兜底（部分支持），或引导用户下载

---

## 10. 图床类平台汇总（永久方案简单）

| 平台 | 域名 | 永久方案 |
|------|------|---------|
| 搜狐 | `q*.itc.cn` / `p*.itc.cn` | 去掉 query 参数 |
| 腾讯 | `*.gtimg.com` | 原样保留 |
| 堆糖 | `c-ssl.duitang.com` | 去掉 query 参数 |
| 花瓣 | `gd-hbimg.huaban.com` | 原样保留 |
| Soogif | `img.soogif.com` | 原样保留 |
| OPPO | `imgfs.oppo.cn` | 原样保留 |
| 100VR | `file.100vr.com` | 原样保留 |
| 数英 | `file.digitaling.com` | 去掉 query 参数 |
| Doooor | `img.doooor.com` | 去掉 query 参数 |
| 简书 | `jianshu.io` | 原样保留 |
| CSDN | `csdnimg.cn` | 原样保留 |
| 掘金 | `p3-juejin.byteimg.com` | 原样保留 |
| 知乎 | `pic*.zhimg.com` | 原样保留 |
| 微信 | `mmbiz.qpic.cn` | 原样保留 |

---

## 11. 有时效图床

| 平台 | 域名 | 失效周期 | 策略 |
|------|------|---------|------|
| 爱给网 | `s1.aigei.com` | token 过期 | 去掉 query 试一次，仍失效需重新获取 |
| 摄图网 | `wimg.588ku.com` | 有时效 | 去掉 query 试一次 |
| 必应 | `ts*.tc.mm.bing.net` | 缓存时效 | **从 riu 参数还原原始来源 URL** |
| Google | `googleusercontent.com` | 可能过期 | 还原原始来源 |

### 11.1 必应特殊处理（还原原始来源）

必应图片缓存的 `riu` 参数嵌套了原始来源 URL：

```
https://ts1.tc.mm.bing.net/th/id/R-C.xxx?rik=...&riu=http%3a%2f%2fn.sinaimg.cn%2f...
                                     ↑ 这里解码后就是原始来源
```

```python
from urllib.parse import parse_qs, unquote

def extract_bing_original(url):
    qs = parse_qs(urlparse(url).query)
    if 'riu' in qs:
        return unquote(qs['riu'][0])   # 还原真实来源链接
```

---

## 12. X / Twitter

- `pbs.twimg.com` 图片：可长期使用，超大图替换后缀为 `:orig`
- 视频：需请求页面提取，无稳定直链

---

## 13. 通用降级策略

未匹配到已知平台时：

1. 尝试去掉 query 参数（保留 `scheme://netloc/path`）
2. 若 URL 有视频 MIME 特征（`mime_type=video`、`/video/tos/` 等）→ 标记为视频时效直链
3. 若 URL 有图片特征（`f=jpeg`、`!nd_dft_`、`imageMogr` 等）→ 标记为图片直链

---

## 14. 渲染集成建议（配合 Record_Manager）

1. **优先永久直链**：小红书/微博/百度/图床类直接用永久链接写入 records
2. **时效链接标记**：抖音/Instagram/TikTok/爱给等 → 卡片显示 ⚠️ 时效标记
3. **过期兜底**：`<img onerror>` 自动尝试 https 重试链 + 平台图标占位
4. **视频嵌入**：Bilibili/YouTube/Vimeo 等用官方 iframe 播放器永久嵌入
5. **下载兜底**：无永久方案的媒体建议立即下载到 vault 附件

---

## 15. 海外平台补充（v4.0 新增）

### 15.1 Pinterest（永久）

```
i.pinimg.com/{size}/{hash}.jpg   →  原样保留（永久）
pinimg.com 为官方 CDN，无签名，直接可用
```

### 15.2 Reddit（图床永久 / 视频时效）

| 域名 | 类型 | 永久性 |
|------|------|--------|
| `i.redd.it` | 图片/视频 | ✅ 图片永久，视频时效 |
| `preview.redd.it` | 缩略图 | ✅ 永久（可去掉 query 参数） |
| `v.redd.it` | 视频 | ❌ 时效 |
| `reddit.com` | 帖子页 | 🔍 需嗅探 |

### 15.3 Imgur（永久）

```
i.imgur.com/{hash}.jpg  →  原样保留（永久）
```

### 15.4 Facebook / fbcdn（时效）

`fbcdn.net` 媒体链接带签名，短时效。需从帖子页嗅探提取（--sniff），提取后立即下载。

### 15.5 SoundCloud（需嗅探）

音频页面，无公开永久直链。`--sniff` 后从内嵌 JSON（playback_secure、streamUrl）提取音频流地址。

### 15.6 VK / Niconico（需嗅探）

均需页面嗅探提取；VK 视频直链（vkvideo.ru CDN）时效短。

## 16. 猫抓式页面嗅探方法论（v4.0 核心新增）

参考 [CatCatch 猫抓](https://blog.csdn.net/gitblog_00290/article/details/159747143) 的资源嗅探引擎 + [DataTool](https://www.datatool.vip) 的平台提取思路，skill 内置 `--sniff` 模式：

### 16.1 嗅探流程

```
网页URL → fetch_page(模拟浏览器UA) → extract_media_from_html(HTML)
                                              │
              ┌───────────────────────────────┼────────────────────────────┐
              │                               │                            │
              ↓                               ↓                            ↓
        标签提取(mp4/mp3/...)         meta og:/twitter:            内嵌JSON提取
        <img>/<video>/<audio>        (video/image/audio)          (display_url/
        /<source src>                                            videoUrl/playAddr)
              │                               │                            │
              └───────────────┬───────────────┴────────────────────────────┘
                              ↓
                     detect_media_type(猫抓式)
                   扩展名 + CDN/MIME 特征识别
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
             普通媒体直链          流媒体(m3u8/mpd)
                                    → parse_m3u8 / parse_mpd
                                    → 提取分片/最高码率流
```

### 16.2 提取优先级

1. **内嵌 JSON**（DataTool 式）：`display_url`、`videoUrl`、`contentUrl`、`originVideoUrl`、`masterUrl`、`playAddr` 等字段
2. **meta 标签**：`og:video` / `og:image` / `og:audio` / `twitter:*`
3. **媒体标签**：`<img src>` / `<video src>` / `<audio src>` / `<source src>` / `<video poster>`
4. **脚本变量**：`window.__INITIAL_STATE__`、`__NEXT_DATA__` 中的媒体 URL

### 16.3 M3U8 流解析

```python
def parse_m3u8(content, base_url):
    streams, segments = [], []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            if line.startswith('#EXT-X-STREAM-INF'):
                streams.append(None)  # 下一行是多码率流地址
            continue
        url = line if line.startswith('http') else urljoin(base_url, line)
        if streams and streams[-1] is None:
            streams[-1] = url      # 多码率流（自适应）
        else:
            segments.append(url)   # 分片地址（TS）
    return streams, segments
```

优先返回 `streams`（多码率自适应流，播放器可用），`segments`（分片列表）供下载合并。

### 16.4 MPD (DASH) 解析

```python
def parse_mpd(content, base_url):
    urls = re.findall(r'<BaseURL>([^<]+)</BaseURL>', content)
    if urls:
        return [u if u.startswith('http') else urljoin(base_url, u) for u in urls]
    return re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m4s|webm)', content)
```

### 16.5 MIME 识别（猫抓式）

| 判定依据 | 媒体类型 |
|---------|---------|
| Content-Type: video/* 或 `mime_type=video` 参数 | video |
| Content-Type: audio/* 或 .mp3/.aac 等扩展名 | audio |
| .m3u8 / .mpd / DASH 特征 | stream |
| .gif / f=gif / soogif / 588ku/gif | gif |
| 图片扩展名或 CDN 特征（imageMogr/thumb/f=jpeg） | image |

### 16.6 防重复与过滤

- 提取结果自动 `dict.fromkeys` 去重，保持顺序
- 只保留 URL 中包含媒体特征的结果（非媒体链接自动丢弃）
- 流媒体二次请求解析，避免把播放列表页当直链

## 17. 媒体类型完整清单（猫抓式，配合 Record_Manager）

| 类型 | 扩展名 / 特征 |
|------|--------------|
| image | jpg jpeg png gif webp bmp svg avif heic jfif ico tiff |
| video | mp4 webm mov m4v mkv avi flv wmv 3gp |
| audio | mp3 wav ogg m4a aac flac wma opus |
| stream | m3u8 mpd |
| 视频CDN | mime_type=video / type=video / video/tos/ / douyinvod / tiktokcdn |
| 图片CDN | f=jpeg / !nd_dft_ / format=webp / imageMogr / thumb / xhscdn / spectrum / notes_pre_post / pbs.twimg / preview.redd.it |

## 18. 方法论版本

v4.0（2026-08-07）：在 v3.0 基础上新增海外平台（Pinterest/Reddit/Imgur/Facebook/SoundCloud/VK/Niconico，共 44 条规则）、猫抓式页面嗅探（--sniff 模式：HTML/内嵌JSON 提取 + M3U8/MPD 流解析 + MIME 识别）、媒体类型扩展（音频/流媒体/更多图片视频格式），国内国外全覆盖。

v4.8（2026-09-17）：修正抖音 vid 提取——`video.uri` 为空时回退 `play_addr.uri`（slides 实测普遍为空），新增 `_douyin_vid()` 并做纯 id 校验（排除 http / 带路径的 BGM mp3），slides 输出补充"作品共 N 片 / M 片带视频流"说明。
