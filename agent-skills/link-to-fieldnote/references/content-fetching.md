# 内容获取策略（Content Fetching）

> 本文件承载：证据优先级、视频/音频获取总则、工具缺失与反爬降级矩阵、各平台（B站/YouTube/抖音/小红书/播客）获取策略、通用 Fallback、平台处理要点汇总。获取到音频后是否转写、如何转写，见 [transcription.md](transcription.md)。

## 目录

- [证据优先级（Evidence Priority）](#证据优先级evidence-priority)
- [视频/音频获取策略（Content Fetching）](#视频音频获取策略content-fetching)
  - [总则](#总则)
  - [工具缺失与反爬降级矩阵](#工具缺失与反爬降级矩阵)
  - [B站（哔哩哔哩）](#b站哔哩哔哩)
  - [YouTube](#youtube)
  - [抖音](#抖音)
  - [小红书](#小红书)
  - [播客](#播客)
  - [通用 Fallback](#通用-fallback)
- [平台处理要点（Platform Summary）](#平台处理要点platform-summary)

---

## 证据优先级（Evidence Priority）

处理任何链接时，必须明确内容依据，**不要伪造**。

视频/音频内容优先级：

1. 平台公开字幕、自动字幕、章节文稿
2. 可下载或可访问音频的本地转写
3. 页面可读取的章节要点、简介、标题和评论区信息
4. 用户手动提供的正文、字幕或剪藏

网页文章优先级：

```
Defuddle（最佳） > Readability > 直接抓取（curl/fetch）
```

- 优先使用平台原生字幕（最准确、最快）
- 字幕缺失或不完整时，下载音频并用 Whisper 转写
- 网页文章优先用 Defuddle 清洗；Defuddle 失败时降级到 Readability，再降级到直接抓取

**重要**：如果只能拿到第 3 类页面信息，不能声称"基于完整音频内容"。应在文档中说明：本稿基于页面可读取的章节/简介整理，非音频转写。

如果用户要求完整视频内容，但无法获取字幕或音频，要明确告知限制，并请求用户上传视频/音频/字幕，或提供可访问链接。

---

## 视频/音频获取策略（Content Fetching）

### 总则

获取视频/音频是后续处理（字幕提取、音频转写）的前提。不同平台的获取难度差异很大，必须按平台使用正确的工具和优先级，避免无谓的试错浪费时间。

**核心原则：对于已知需要 cookies 或反爬严格的平台（抖音、小红书），直接使用浏览器自动化方案，不要先用 yt-dlp 试错。**

### 工具缺失与反爬降级矩阵

标准工具链（yt-dlp / 浏览器自动化 + browser_network_requests / Whisper 转写）并非每个环境都齐全，平台反爬也可能拦截其中任何一环。遇到障碍时**按层降级，禁止原地反复重试同一种方法**，也**禁止伪造内容**：

| 层级  | 障碍                                                                | 应对策略                                                                               | 文档标注要求       |
| --- | ----------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------ |
| L0  | 下载器被拦截（yt-dlp 403 / doubao 等第三方下载器报错）                             | 自行多试 几次不同技术方案，至少三次。还不行即切换浏览器自动化方案，不反复试错                                            | 无            |
| L1  | 浏览器弹出滑块/拼图验证                                                      | 最多试 2~3 次，仍不过就放弃浏览器渲染，改抓页面 HTML 内嵌 JSON 或搜索引擎缓存                                    | 标注"页面验证未通过"  |
| L2  | 无 browser_network_requests 类网络捕获工具 / Console 执行被阻止（allow pasting） | 用 curl/wget 带 Referer+UA 直接抓页面 HTML，正则提取 `window._ROUTER_DATA` 等内嵌 JSON；或改抓移动端/分享页 | 标注"未获取完整音视频" |
| L3  | 仅能拿到标题/简介/公开报道/字幕片段                                               | 用标题关键词检索公开报道、字幕片段、评论区要点交叉验证；按"降级整理模式"产出                                            | 显眼位置标注来源限制   |
| L4  | 全部失败                                                              | 请求用户上传视频/音频/字幕文件                                                                   | 明确告知限制       |

**降级整理模式（L3 及以下强制）**：
先中断当前任务，拉起询问用户是否需要用降级模式整理成对用内容，等待用户回复确认后，再继续后续操作。

- 文档必须在 `Abstract` 或开头用醒目提示说明内容依据（如"本稿基于页面简介 + 公开报道整理，非完整音频转写"），不得伪装成完整转写
- 知识笔记的信息密度、金句数量可相应下调，但**不得虚构**视频中未出现的数据、案例、观点和引用
- 所有关键引用必须标注出处（简介 / 公开报道 / 字幕片段 / 用户提供），区分"原视频内容"与"外部补充信息"

### B站（哔哩哔哩）

B站通常不需要登录即可获取视频/音频，工具链简单。

1. **首选 yt-dlp 直接下载**
   ```bash
   # 下载视频（包含音频）
   yt-dlp "https://www.bilibili.com/video/BVxxxxxxxxxx" -o "video.mp4"

   # 仅下载音频
   yt-dlp -x --audio-format mp3 "https://www.bilibili.com/video/BVxxxxxxxxxx" -o "audio.mp3"
   ```
   B站一般可直接下载，无需 cookies。

2. **如果 yt-dlp 失败**，用浏览器自动化打开页面，通过 `browser_network_requests` 捕获视频直链，再用 curl 下载。

3. **获取字幕优先**：yt-dlp 支持 B站字幕提取：
   ```bash
   yt-dlp --write-subs --sub-lang zh-CN --skip-download "https://www.bilibili.com/video/BVxxxxxxxxxx" -o "subtitle"
   ```
   有字幕时直接使用字幕，可跳过音频转写。

4. **从视频提取音频**：
   ```bash
   ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
   ```

### YouTube

YouTube 下载相对稳定，yt-dlp 是首选。

1. **首选 yt-dlp 直接下载**：
   ```bash
   # 下载最佳音频（推荐用于转写场景）
   yt-dlp --format bestaudio -x --audio-format wav "https://www.youtube.com/watch?v=VIDEO_ID" -o "audio.%(ext)s"

   # 下载视频
   yt-dlp "https://www.youtube.com/watch?v=VIDEO_ID" -o "video.mp4"
   ```

2. **获取字幕优先**：
   ```bash
   # 列出可用字幕
   yt-dlp --list-subs "https://www.youtube.com/watch?v=VIDEO_ID"

   # 下载手动字幕（如果有）
   yt-dlp --write-subs --sub-lang zh-Hans,zh,en --skip-download "https://www.youtube.com/watch?v=VIDEO_ID" -o "subtitle"

   # 下载自动字幕
   yt-dlp --write-auto-subs --sub-lang zh-Hans,zh,en --skip-download "https://www.youtube.com/watch?v=VIDEO_ID" -o "subtitle"
   ```
   有字幕时直接使用字幕，可跳过音频转写。

3. **如果 yt-dlp 失败**，用浏览器自动化打开页面，通过 `browser_network_requests` 捕获视频直链，再用 curl 下载。

4. **从视频提取音频**：
   ```bash
   ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
   ```

### 抖音

抖音反爬严格，yt-dlp 和 you-get 通常都会 403 失败（需登录/cookies），doubao-video-extract 等第三方下载器也可能报错（如 `Douyin router data does not contain videoInfoRes.item_list`）。**不要在这些下载器上反复试错**，直接进入浏览器自动化方案；但可先花一次调用快速确认下载器是否可用（部分视频/场景可能直接成功）。

1. **快速试一次下载器（可选，1 次即止）**：
   ```bash
   yt-dlp "https://v.douyin.com/xxxxx/" -o "video.%(ext)s"
   ```
   403 或报错立即放弃，切到方案 2。

2. **浏览器自动化方案（首选）**：
   - 导航到用户提供的分享短链（如 `https://v.douyin.com/xxxxx/`），等待跳转到视频详情页
   - 注意：抖音 SPA 页面加载后会自动跳转到推荐视频，**必须在页面加载后立即获取网络请求**，防止捕获到错误的视频地址
   - 通过 `browser_network_requests` 捕获 CDN 直链；CDN 域名通常为 `v11-weba.douyinvod.com` / `v26-web.douyinvod.com` 或类似
   - 过滤请求列表：找到 `.mp4` 结尾或 Content-Type 为 `video/mp4` 的请求（视频流），以及 `audio/mp4`、`.m4a` 的请求（音频流）

3. **视频流与音频流可能分离（重要，本次实战教训）**：抖音 CDN 常把视频流（`media-video-avc1`）和音频流（`media-audio-und-mp4a`）作为两个独立请求。下载后用 ffmpeg 探测：
   ```bash
   ffmpeg -i video.mp4 2>&1 | grep Stream
   ```
   若输出只有 `Video:` 没有 `Audio:` 流，**必须单独捕获音频流直链并下载**，否则转写无声音可用。音频流下载通常需要携带 `Referer: https://www.douyin.com/` 和浏览器 UA，否则 CDN 会 403。

4. **下载捕获到的直链（带 Referer + UA 更稳）**：
   ```bash
   curl -L -o video.mp4 -H "Referer: https://www.douyin.com/" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)" "捕获到的CDN直链"
   ```

5. **从视频/音频提取音频**：
   ```bash
   ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
   # 或对单独下载的音频流：ffmpeg -i audio.m4a -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
   ```

6. **滑块验证应对（不要死磕）**：抖音可能强制弹出滑块拼图验证，多次拖动易被轨迹检测识别为机器人。**单次尝试不超过 2~3 次**，仍失败即放弃浏览器渲染，改用降级路径：
   - 用 curl/wget 直接抓分享短链或视频详情页 HTML（带 UA），正则提取 `window._ROUTER_DATA` 等内嵌 JSON 中的标题、简介、视频 ID 等元数据
   - 或直接用视频标题关键词做搜索引擎检索，收集公开报道、字幕片段、评论区要点交叉验证内容
   - 按"工具缺失与反爬降级矩阵"标注来源限制后整理

7. **Console 执行被阻止（allow pasting）应对**：Chrome 开发者工具的"禁止粘贴代码"机制会拦截 JS 注入（type 输入会被识别为粘贴）。**不要依赖执行 JS 获取 `window._ROUTER_DATA`**；直接抓取页面 HTML 源码并从内嵌 JSON 中解析元数据即可，无需打开开发者工具。

**抖音 iframe 嵌入策略**：
- 抖音可能补支持稳定的 iframe 嵌入。尝试抖音的 iframe，验证是否可行，如 `<iframe src="https://www.douyin.com/video/VIDEO_ID">` ，可以尝试改变 iframe 的参数，模拟手机或平板，电脑灯不同设备播放比例，可能能够使播放可行，采用你已知的可行思路尝试一下即可。
- **当尝试失败后可以不用强求，保留链接即可，要在文档中放入抖音 iframe**，只保留安全链接：`> 📺 [抖音](原始链接)`

### 小红书

小红书反爬比较严格，与抖音类似，yt-dlp 通常失败，但是也要做尝试。

1. **yt-dlp 通常失败**，尝试两三次后失败，即可放弃尝试。

2. **直接使用浏览器自动化方案**：
   - 导航到用户提供的链接
   - 等待页面加载完成
   - 通过 `browser_network_requests` 捕获视频 CDN 直链
   - 用 curl 下载

3. **从视频提取音频**（同抖音）：
   ```bash
   ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
   ```

**小红书 iframe 嵌入策略**：
- 小红书可能不支持 iframe 嵌入。但还是要和抖音一样做尝试。
- **尝试后如果可行，则放入 iframe。不可行，则不用在文档中放入小红书 iframe**，只保留安全链接：`> 📺 [小红书](原始链接)`

### 播客

1. 优先读取节目页文稿或 RSS feed 中的正文。
2. 无文稿时，查找 RSS 中是否有音频直链（`.mp3` 或 `.m4a`），用 curl/wget 直接下载。
3. 如果 RSS 中没有直链，用浏览器自动化打开节目页面，通过 `browser_network_requests` 捕获音频地址。
4. 从音频文件提取 wav：同上 ffmpeg 命令。

### 通用 Fallback

如果以上所有工具和方法都失败：
- 明确告知用户平台限制（如"该平台需要登录才能获取视频/音频，当前环境无法完成"）
- 请求用户上传视频/音频文件，或提供字幕文件
- 不要伪造内容或跳过获取步骤不说明原因

---

## 平台处理要点（Platform Summary）

### 视频平台

| 平台          | 获取策略                                     | iframe 策略                  |
| ----------- | ---------------------------------------- | -------------------------- |
| **哔哩哔哩**    | yt-dlp 优先获取视频+字幕；失败时用浏览器自动化抓直链           | 标准 iframe，需带 `cid` 参数，关闭弹幕 |
| **YouTube** | yt-dlp 优先获取视频+字幕；失败时用浏览器自动化              | 标准 iframe，`autoplay=0`     |
| **抖音**      | **尝试先试 yt-dlp，一两次无果后**，直接用浏览器自动化抓 CDN 直链 | 若不支持稳定嵌入，只保留安全链接           |
| **小红书**     | **尝试先试 yt-dlp** 一两次无果后，直接用浏览器自动化抓 CDN 直链 | 若不支持 iframe，只保留安全链接        |
| **播客**      | 优先读取节目页文稿或 RSS 音频直链；无文稿时转写音频             | 通常无 iframe，保留链接            |

### 图文平台

- **微信公众号**：优先抓正文（Defuddle）；清理关注、二维码、广告、推荐阅读
- **普通网页/博客**：提取正文和元数据，清理导航、页脚、推荐卡片
- **新闻页**：保留标题、来源、发布时间和正文，删除相关新闻列表、广告和评论噪音
