#!/usr/bin/env python3
"""
Media Link Resolver v4.10 - 社媒平台媒体直链解析与嗅探器
=========================================================
将各大平台（国内 20+ / 海外 15+）的 CDN 链接、签名链接、短链、网页链接
转换为【永久直链】或【最优直链】。

核心思路（融合三大实现）：
  1. 平台规则表（参考 Record_Manager PLATFORM_RULES，38 项 + 扩展）
  2. 猫抓式资源嗅探：页面请求 → HTML/内嵌JSON 提取 → M3U8/MPD 流解析 → MIME 识别
  3. DataTool 式海外平台覆盖：Twitter/X、TikTok、Instagram、Facebook、Pinterest、
     Reddit、Vimeo、YouTube、Bilibili 等，无水印优先、多清晰度

用法:
  python3 resolve_media_links.py <url>                 # 单条解析
  python3 resolve_media_links.py --batch urls.txt      # 文件批量
  echo "<url>" | python3 resolve_media_links.py --stdin
  python3 resolve_media_links.py --sniff <网页url>      # 猫抓式页面嗅探
  python3 resolve_media_links.py --platforms            # 列出平台
"""

import re
import sys
import json
import argparse
from urllib.parse import urlparse, unquote, parse_qs, urljoin

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False


# ════════════════════════════════════════════════════════════
# 0. 媒体类型检测（猫抓式：扩展名 + MIME/CDN 特征 双重识别）
# ════════════════════════════════════════════════════════════

IMAGE_EXTS = r'\.(jpg|jpeg|png|gif|webp|bmp|svg|avif|heic|jfif|ico|tiff)(\?.*)?$'
VIDEO_EXTS = r'\.(mp4|webm|mov|m4v|mkv|avi|flv|wmv|3gp)(\?.*)?$'
AUDIO_EXTS = r'\.(mp3|wav|ogg|m4a|aac|flac|wma|opus)(\?.*)?$'
STREAM_EXTS = r'\.(m3u8|mpd)(\?.*)?$'

VIDEO_CDN_PATTERNS = [
    r'[?&]mime_type=video[_/](mp4|webm|flv|m4v)',
    r'[?&]type=video',
    r'/video/tos/',          # 抖音/TikTok CDN
    r'\.douyinvod\.com',
    r'\.tiktokcdn\.com',
    r'/video/.*\.mp4',
]
IMAGE_CDN_PATTERNS = [
    r'(\?|&)f=(jpeg|gif|png|bmp|webp|jpg)(&|$)',
    r'!nd_dft_[\w-]+_(webp|jpg|jpeg|png|gif)_\d+',
    r'/(format|fmt)=(webp|jpg|jpeg|png|gif)',
    r'imageMogr',
    r'/thumb/',
    r'\.xhscdn\.com.*\!',
    r'ci\.xiaohongshu\.com/(spectrum|notes_pre_post)/',
    r'sns-webpic.*\.xhscdn\.com.*notes_pre_post',
    r'/spectrum/[\w]+$',
    r'/notes_pre_post/[\w]+$',
    r'pbs\.twimg\.com/media',   # Twitter 图片 CDN
    r'preview\.redd\.it',       # Reddit 预览图
]
GIF_INDICATORS = [
    r'\.gif(\?.*)?$',
    r'(\?|&)f=gif',
    r'!nd_dft_[\w-]+_gif_\d+',
    r'soogif\.com',
    r'588ku\.com/gif',
]
ANIMATED_INDICATORS = [
    # 动图/动态图 URL 特征（animated webp / apng / 动图平台）
    r'\.webp\?.*&?f=webp',      # 部分 CDN 动图 webp
    r'\.png\?.*&?f=png',
    r'\.gifv',                  # imgur gifv
    r'\.webm(\?.*)?$',          # 动图常以 webm 编码
    r'animated',
    r'livephoto',
    r'live_photo',
    r'/dynamic/',
    r'wbp\d',                   # 动图平台特征
]


def probe_media_type(url, timeout=6):
    """HTTP 探测真实媒体类型（魔数/Content-Type）：识别 GIF / 动图 WebP / APNG / 视频等"""
    if not HAS_REQUESTS or not url.startswith('http'):
        return None
    try:
        headers = {'User-Agent': BROWSER_UA, 'Range': 'bytes=0-127'}
        resp = requests.get(url, headers=headers, timeout=timeout, stream=True)
        if resp.status_code not in (200, 206):
            return None
        chunk = b''
        for c in resp.iter_content(128):
            chunk += c
            if len(chunk) >= 160:
                break
        resp.close()
        if not chunk:
            return None
        # 魔数判断
        if chunk[:6] in (b'GIF87a', b'GIF89a'):
            return 'gif'
        if chunk[:4] == b'RIFF' and chunk[8:12] == b'WEBP':
            # 真正动图 webp 必须含 ANIM + ANMF 帧；仅有 VP8X 扩展头（含 ICCP/ALPH）是静态图
            if b'ANIM' in chunk and b'ANMF' in chunk:
                return 'animated'
            return 'image'
        if chunk[:8] == b'\x89PNG\r\n\x1a\n':
            # APNG: 文件头之后出现 acTL chunk
            if b'acTL' in chunk:
                return 'animated'
            return 'image'
        if chunk[:3] == b'\xff\xd8\xff':
            return 'image'
        if b'ftyp' in chunk[:16]:
            return 'video'
        if chunk[:4] == b'\x1a\x45\xdf\xa3':
            return 'video'   # webm/mkv
        if chunk[:3] == b'ID3' or chunk[:2] in (b'\xff\xfb', b'\xff\xf3'):
            return 'audio'
        if b'#EXTM3U' in chunk or b'#EXT-X' in chunk:
            return 'stream'
        # Content-Type 兜底
        ct = resp.headers.get('Content-Type', '')
        if 'image/gif' in ct:
            return 'gif'
        if 'image/webp' in ct:
            return 'animated'
        if 'image/png' in ct:
            return 'animated' if b'acTL' in chunk else 'image'
        if ct.startswith('video/'):
            return 'video'
        if ct.startswith('audio/'):
            return 'audio'
        return None
    except Exception:
        return None


def detect_media_type(url):
    """猫抓式媒体类型识别：扩展名 + CDN/MIME 特征"""
    if not url:
        return 'file'
    lower = url.lower()
    if re.search(STREAM_EXTS, lower, re.I):
        return 'stream'
    if re.search(VIDEO_EXTS, lower, re.I):
        return 'video'
    for p in VIDEO_CDN_PATTERNS:
        if re.search(p, url, re.I):
            return 'video'
    if re.search(AUDIO_EXTS, lower, re.I):
        return 'audio'
    for p in GIF_INDICATORS:
        if re.search(p, url, re.I):
            return 'gif'
    for p in ANIMATED_INDICATORS:
        if re.search(p, url, re.I):
            return 'animated'
    if re.search(IMAGE_EXTS, lower, re.I):
        return 'image'
    for p in IMAGE_CDN_PATTERNS:
        if re.search(p, url, re.I):
            return 'image'
    if re.search(r'\.md(\?.*)?$', lower, re.I) or '[[' in url:
        return 'note'
    if re.search(r'^https?://', lower):
        return 'web'
    return 'file'


def media_type_label(url):
    m = detect_media_type(url)
    return {'gif': 'GIF', 'animated': '动图', 'image': 'Image', 'video': 'Video', 'audio': 'Audio',
            'stream': 'Stream', 'note': 'Note', 'web': 'Web', 'file': 'File'}.get(m, m)


# ════════════════════════════════════════════════════════════
# 1. 通用工具
# ════════════════════════════════════════════════════════════

def strip_query(url):
    try:
        p = urlparse(url)
        return f"{p.scheme}://{p.netloc}{p.path}"
    except Exception:
        return url.split('?')[0]


def notes(items):
    return [i for i in items if i.startswith('[')]


def urls_only(items):
    return [i for i in items if not i.startswith('[')]


def clean_escaped(s):
    return s.replace('\\u002F', '/').replace('\\/', '/')


# ════════════════════════════════════════════════════════════
# 2. 页面嗅探（猫抓式核心思路）
# ════════════════════════════════════════════════════════════

BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")


def fetch_page(url, mobile=False):
    """请求页面，返回 (html, final_url)"""
    if not HAS_REQUESTS:
        return None, None
    try:
        headers = {'User-Agent': MOBILE_UA if mobile else BROWSER_UA,
                   'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'}
        resp = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
        resp.encoding = resp.apparent_encoding or 'utf-8'
        return resp.text, resp.url
    except Exception:
        return None, None


def extract_media_from_html(html, base_url):
    """从 HTML 提取媒体直链（猫抓式：标签 + meta + 内嵌 JSON）"""
    found = []
    # <img src> / <video src> / <audio src> / <source src>
    for tag, attr in [('img', 'src'), ('video', 'src'), ('audio', 'src'),
                      ('source', 'src'), ('video', 'poster')]:
        for m in re.finditer(rf'<{tag}[^>]*{attr}\s*=\s*["\']([^"\']+)["\']', html, re.I):
            u = clean_escaped(m.group(1))
            if u.startswith('http'):
                found.append(u)
            elif u.startswith('//'):
                found.append('https:' + u)
            elif u.startswith('/'):
                found.append(urljoin(base_url, u))
    # meta og:video / og:image / og:audio
    for m in re.finditer(r'<meta[^>]+property=["\'](?:og|twitter):(video|image|audio)["\'][^>]+content=["\']([^"\']+)["\']', html, re.I):
        found.append(m.group(2))
    for m in re.finditer(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\'](?:og|twitter):(video|image|audio)["\']', html, re.I):
        found.append(m.group(1))
    # 内嵌 JSON 中的媒体字段（DataTool 式）
    for key in ['display_url', 'displayUrl', 'video_url', 'videoUrl', 'contentUrl',
                'originalUrl', 'originVideoUrl', 'masterUrl', 'downloadUrl',
                'mediaUrl', 'mainVideoUrl', 'playAddr', 'play_addr']:
        for m in re.finditer(rf'"{key}"\s*:\s*"([^"]+)"', html):
            u = clean_escaped(m.group(1))
            if u.startswith('http') or u.startswith('//'):
                found.append('https:' + u if u.startswith('//') else u)
    # 脚本变量中的 URL（window.__INITIAL_STATE__ 等，宽松匹配）
    for m in re.finditer(r'https?:\\?/\\?/[^"\'\\\s]+\.(?:mp4|m3u8|mpd|jpg|jpeg|png|gif|webp)(?:\\?/[^"\'\\\s]*)?', html):
        found.append(clean_escaped(m.group(0)))
    return list(dict.fromkeys(found))


def parse_m3u8(content, base_url):
    """解析 m3u8 播放列表：返回 (streams, segments)。
    v4.6: master 列表按 #EXT-X-STREAM-INF 的 BANDWIDTH 从高到低排序（最高清档在前），
    并记录 RESOLUTION（猫抓 m3u8.js 用 hls.js 按带宽选最高档的思路）。"""
    streams, segments = [], []
    cur = None
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith('#'):
            if line.startswith('#EXT-X-STREAM-INF'):
                attrs = {}
                for k, v in re.findall(r'([A-Z0-9-]+)=([^,]+)', line):
                    attrs[k] = v.strip('"')
                try:
                    bw = int(attrs.get('BANDWIDTH', 0) or 0)
                except Exception:
                    bw = 0
                cur = {'url': None, 'bandwidth': bw, 'resolution': attrs.get('RESOLUTION', '')}
                streams.append(cur)
            continue
        url = line if line.startswith('http') else urljoin(base_url, line)
        if streams and streams[-1].get('url') is None and cur is not None:
            streams[-1]['url'] = url
            cur = None
        else:
            segments.append(url)
    # master: 过滤无 url 的残留标记，按带宽降序（最高清在前）
    streams = [s for s in streams if s.get('url')]
    streams.sort(key=lambda s: s.get('bandwidth', 0), reverse=True)
    return [s['url'] for s in streams], segments


def parse_mpd(content, base_url):
    """解析 MPD 清单：提取各 Representation 的 BaseURL"""
    urls = re.findall(r'<BaseURL>([^<]+)</BaseURL>', content)
    if urls:
        return [u if u.startswith('http') else urljoin(base_url, u) for u in urls]
    # 兜底:匹配完整媒体 URL
    return re.findall(r'https?://[^\s"\'<>]+\.(?:mp4|m4s|webm)', content)


def sniff_page(url):
    """猫抓式完整嗅探：请求页面 → 平台解析器优先 → HTML 提取 → 动图/视频探测"""
    results = {'page': url, 'platform': '未知', 'media': [], 'streams': [], 'error': None}
    html, final_url = fetch_page(url)
    if not html:
        results['error'] = '页面请求失败（网络不可达或超时）'
        return results

    # 平台识别
    from urllib.parse import urlparse as _up
    host = _up(url).hostname or ''
    results['final_url'] = final_url
    for pattern, name in PLATFORM_META:
        if re.search(pattern, url, re.I):
            results['platform'] = name
            break

    def add_media(u):
        """单条媒体入库（v4.6: 扩展名 + HTTP 魔数 + 响应头三重识别，附 CDN 平台标签）"""
        mt = detect_media_type(u)
        if mt in ('image', 'web') and re.search(r'\.(webp|png|jpe?g|gif)(\?.*)?$|douyinpic|tiktokcdn', u, re.I):
            probed = probe_media_type(u)
            if probed and probed in ('gif', 'animated', 'video', 'audio', 'stream', 'image'):
                mt = probed
        # v4.6: 扩展名/魔数仍无法判定的 URL，用响应头嗅探（猫抓 findMedia 思路）
        entry_size = None
        if mt in ('web', 'file'):
            hdr = sniff_media_headers(u)
            if hdr and hdr.get('type'):
                mt = hdr['type']
                entry_size = hdr.get('size')
        if mt not in ('image', 'gif', 'animated', 'video', 'audio', 'stream'):
            return
        type_map = {'image': 'Image', 'gif': 'GIF', 'animated': '动图', 'video': 'Video',
                    'audio': 'Audio', 'stream': 'Stream'}
        entry = {'type': type_map.get(mt, mt), 'url': u}
        if mt == 'stream' and 'm3u8' in u.lower():
            c, _ = fetch_page(u)
            if c:
                s, segs = parse_m3u8(c, u)
                entry['streams'] = s if s else segs[:3]
                entry['segment_count'] = len(segs)
        elif mt == 'stream' and ('.mpd' in u.lower() or 'mpd' in u.lower()):
            c, _ = fetch_page(u)
            if c:
                entry['streams'] = parse_mpd(c, u)
        # v4.6: CDN 域名识别平台（智Tool manifest 域名清单）
        plat = identify_platform_cdn(u)
        if plat:
            entry['platform'] = plat
        if entry_size:
            entry['size'] = entry_size
        results['media'].append(entry)

    # 优先平台解析器（短链重定向/分享页内嵌 JSON 等 HTML 标签抓不到的场景）
    for pattern, resolver, name, _perm in PLATFORM_RULES:
        if re.search(pattern, url, re.I):
            try:
                resolved = resolver(url)
            except Exception:
                resolved = None
            if resolved:
                for u in urls_only(resolved):
                    add_media(u)
            break

    # HTML 标签 / 内嵌 JSON 兜底
    raw = extract_media_from_html(html, url)
    seen = {m['url'] for m in results['media']}
    for u in raw:
        if u in seen:
            continue
        add_media(u)
        seen.add(u)
    return results


# ════════════════════════════════════════════════════════════
# 3. 各平台解析器（国内 + 海外）
# ════════════════════════════════════════════════════════════

def _find_chromium():
    """v4.10 新增：自动探测可用 Chromium/Chrome 可执行文件。
    优先级：环境变量 DOUYIN_CHROME > ~/.cache/ms-playwright/chromium-*/ > 系统 chromium/chrome。
    （v4.9 及以前硬编码 /usr/local/bin/chromium，该路径在本机不存在 → 浏览器兜底直接失败。）"""
    import os, glob
    env = os.environ.get('DOUYIN_CHROME')
    if env:
        return env
    pats = [
        '~/.cache/ms-playwright/chromium-*/chrome-linux*/chrome',
        '~/.cache/ms-playwright/chromium_headless_shell-*/chrome-linux*/headless_shell',
        '/usr/local/bin/chromium', '/usr/bin/chromium', '/usr/bin/chromium-browser',
        '/snap/bin/chromium', '/usr/bin/google-chrome', '/usr/bin/google-chrome-stable',
    ]
    for pat in pats:
        for h in sorted(glob.glob(os.path.expanduser(pat)), reverse=True):
            if os.path.exists(h):
                return h
    return '/usr/local/bin/chromium'


# v4.10 新增：小红书视频免签名镜像域（实测：/stream/ 同路径去掉 sign 参数后换域即 206/200 video/mp4）
XHS_VIDEO_MIRROR_HOSTS = ['sns-video-bd.xhscdn.com', 'sns-video-hw.xhscdn.com',
                          'sns-video-al.xhscdn.com', 'sns-bak-v1.xhscdn.com']


def xhs_video_permanent(url):
    """小红书签名视频链 → 免签名长期可引用直链列表（去 x-signature 等参数 + 换镜像域）。
    仅处理 /stream/ 视频路径；ci.xiaohongshu.com 只服务图片，不适用。"""
    if not url or '/stream/' not in url:
        return []
    m = re.match(r'^https?://[^/]+(/stream/[^?]+)', url)
    if not m:
        return []
    path = m.group(1)
    return [f'https://{h}{path}' for h in XHS_VIDEO_MIRROR_HOSTS]


def resolve_xiaohongshu(url):
    """小红书: sns-webpic 签名 → ci.xiaohongshu.com 永久直链；笔记页/短链 → 浏览器拦截 /api/sns/web/v1/feed 提取视频与图片"""
    m = re.search(r'xhscdn\.com/[^/]+/[^/]+/((?:notes_pre_post|spectrum)/[a-z0-9]+)', url)
    if m:
        return [f"http://ci.xiaohongshu.com/{m.group(1)}"]
    m = re.search(r'ci\.xiaohongshu\.com/((?:notes_pre_post|spectrum)/[a-z0-9]+)', url)
    if m:
        return [f"http://ci.xiaohongshu.com/{m.group(1)}"]
    m = re.search(r'ci\.xiaohongshu\.com/([a-z0-9]+(?:\.[a-z0-9_]+)?(?:\![^\s"\'?]+)?)', url)
    if m:
        return [f"http://ci.xiaohongshu.com/{m.group(1)}"]
    # ── v4.6: 笔记页 / 短链 → 浏览器拦截 feed API（智Tool API map: /api/sns/web/v1/feed）──
    # v4.10: 短链域名扩展 xhslink.cn / .net / rednote.com（手机端分享用 .cn，此前只认 .com → 未匹配平台规则）
    if re.search(r'xhslink\.(?:com|cn|net)|rednote\.com', url):
        # 短链先还原
        try:
            r = requests.head(url, headers={'User-Agent': BROWSER_UA}, allow_redirects=True, timeout=10)
            url = r.url
        except Exception:
            pass
    if 'xiaohongshu.com' in url and ('explore' in url or 'discovery' in url or 'item' in url):
        # 拦截详情接口：h5 note_info（旧）/ web v1 feed（新，智Tool API map）
        caps = _browser_intercept_api(url, ['/api/sns/h5/v1/note_info', '/api/sns/web/v1/feed', '/api/sns/web/v2/note_info'])
        for cap in reversed(caps):
            try:
                data = json.loads(cap['body'])
                note = ((data.get('data') or {}).get('note') or {}) or ((data.get('data') or {}).get('items') or [{}])[0].get('note_card') or {}
                if not note:
                    continue
                out = []
                # 视频: video.media.stream.h264[].master_url / consumer.origin_video_key
                vd = note.get('video') or {}
                stream = (vd.get('media') or {}).get('stream') or {}
                h264 = stream.get('h264') or []
                for s in h264:
                    for k in ('master_url', 'backup_urls'):
                        us = s.get(k) or []
                        if isinstance(us, str):
                            us = [us]
                        for u in us:
                            if u.startswith('http'):
                                out.append(u)
                for su in (vd.get('consumer') or {}).get('origin_video_key') or []:
                    if isinstance(su, str) and su.startswith('http'):
                        out.append(su)
                # 图片: image_list[].url_default / url_pre / url_720w / url_1080p
                imgs = note.get('image_list') or []
                for im in imgs:
                    for k in ('url_default', 'url_pre', 'url_720w', 'url_1080p'):
                        u = im.get(k)
                        if u and u.startswith('http'):
                            out.append(u)
                            break
                if out:
                    out = list(dict.fromkeys(out))
                    # v4.10: 视频 master_url 为时效签名链 → 换免签名镜像域，永久链置顶
                    perm = []
                    for u in out:
                        perm.extend(xhs_video_permanent(u))
                    if perm:
                        perm = list(dict.fromkeys(perm))
                        out = perm + [u for u in out if u not in perm]
                        out.append('[永久] 小红书 /stream/ 视频免签名镜像域直链（sns-video-bd/hw/al/bak-v1.xhscdn.com，'
                                   '去掉 sign 类参数，免 Referer 免 UA，实测 200/206 video/mp4），可长期引用')
                    out.append('[可渲染] 小红书笔记直链（图片需 Referer: xiaohongshu.com）')
                    out.append(f'[笔记] {_note_desc(note.get("title") or note.get("desc"))}')
                    return out
            except Exception:
                continue
        # 判断是否登录墙
        try:
            page_html, _ = fetch_page(url)
            login_wall = page_html and ('请先登录' in page_html or '验证码' in page_html or '登录后' in page_html)
        except Exception:
            login_wall = False
        if login_wall:
            return [f"[登录墙] 小红书需登录后才能读取笔记详情，请在已登录的浏览器会话中解析，或手动复制图片/视频链接 {url}"]
        return [f"[需要登录态或页面未返回数据，浏览器拦截未命中详情 API] {url}"]
    if re.search(r'xhslink\.(?:com|cn|net)', url):
        return [f"[短链，需请求还原后再提取 fileId] {url}"]
    return None


def resolve_weibo(url):
    """微博: sinaimg.cn 永久直链 + oslarge 无水印原图；详情页 → 浏览器拦截 /ajax/statuses/show 提取视频"""
    m = re.search(r'(wx\d+|ww\d+|n)\.sinaimg\.cn/(\w+)/(.+\.\w+)', url)
    if m:
        sub, size, filename = m.group(1), m.group(2), m.group(3)
        base = f"https://{sub}.sinaimg.cn"
        return [f"{base}/oslarge/{filename}", f"{base}/large/{filename}", f"{base}/{size}/{filename}"]
    # ── v4.6: 微博详情页 → 浏览器拦截 /ajax/statuses/show + /tv/api/component（智Tool API map）──
    if 'weibo.com' in url and re.search(r'weibo\.com/\d+/[A-Za-z0-9]+', url):
        caps = _browser_intercept_api(url, ['/ajax/statuses/show', '/tv/api/component'])
        for cap in reversed(caps):
            try:
                data = json.loads(cap['body'])
                st = data.get('data') or data
                out = []
                # 图片
                pics = st.get('pic_ids') or []
                mid = st.get('mid') or st.get('idstr') or ''
                for pid in pics:
                    out.append(f"https://wx2.sinaimg.cn/oslarge/{pid}.jpg")
                # 视频（新版微博 detail 结构）
                vd = st.get('page_info', {}).get('media_info') or {}
                for k in ('mp4_720p_mp4', 'mp4_hd_url', 'mp4_sd_url', 'stream_url_hd', 'stream_url'):
                    v = vd.get(k)
                    if v and v.startswith('http'):
                        out.append(v)
                # 旧版 /tv/api/component
                if not out:
                    txt = cap['body']
                    for m2 in re.finditer(r'"(stream_url_hd|mp4_hd_url|mp4_720p_mp4|mp4_sd_url|page_url)":"([^"]+)"', txt):
                        u = clean_escaped(m2.group(2))
                        if u.startswith('http'):
                            out.append(u)
                if out:
                    out = list(dict.fromkeys(out))
                    out.append('[可渲染] 微博直链（图片 oslarge 无水印永久；视频带签名需 Referer: weibo.com）')
                    if mid:
                        out.append(f'[微博ID] {mid}')
                    return out
            except Exception:
                continue
        return [f"[需要登录态或页面未返回数据，浏览器拦截未命中] {url}"]
    if 'weibo.com' in url or 'weibo.cn' in url:
        return [f"[需要请求页面嗅探提取媒体] {url}"]
    return None


def resolve_baidu(url):
    if 'pic.rmb.bdstatic.com' in url:
        return [strip_query(url)]
    if 'hiphotos.baidu.com' in url or 'img2.baidu.com' in url or 'img.baidu.com' in url:
        return [url]
    return None


def _extract_json_array(html, field):
    """括号配对提取 JSON 数组字段（处理嵌套 url_list）"""
    idx = html.find(f'"{field}"')
    if idx == -1:
        return None
    start = html.find('[', idx)
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(html)):
        ch = html[i]
        if in_str:
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(html[start:i + 1].replace('\\u002F', '/'))
                    except Exception:
                        return None
    return None


def _extract_router_data(html):
    """解析抖音分享页 SSR _ROUTER_DATA JSON（比正则抠 url_list 更完整）"""
    try:
        idx = html.find('_ROUTER_DATA')
        if idx == -1:
            return None
        eq = html.find('=', idx)
        start = html.find('{', eq)
        return json.JSONDecoder().raw_decode(html[start:])[0]
    except Exception:
        return None


def _douyin_page_item(html):
    """从分享页 SSR 提取 item_list[0]（含 img_bitrate / images / video 全量字段）"""
    data = _extract_router_data(html)
    if not data:
        return None
    try:
        ld = data.get('loaderData') or {}
        page = ld.get('note_(id)/page') or {}
        vr = page.get('videoInfoRes') or {}
        il = vr.get('item_list') or []
        return il[0] if il else None
    except Exception:
        return None


def _probe_douyin_quality(u, timeout=8):
    """高清/永久化探测：尝试去模板、q100、无签名访问，确认是否还有更高清档或永久直链。
    返回探测结论字符串（或 None 表示保持原链接即可）。"""
    try:
        from urllib.parse import urlsplit, parse_qs, urlencode, urlunsplit
        sp = urlsplit(u)
        q = dict(parse_qs(sp.query))
        path = sp.path
        # 变体1: ~q80 → 去模板后缀（原图直出候选）
        variants = {}
        if '~q80.' in path:
            variants['原图直出(去模板)'] = re.sub(r'~q80\.[a-z]+$', '', path)
        # 变体2: ~q80 → q100
        if '~q80.' in path:
            variants['q100(最高质量)'] = path.replace('~q80.', '~q100.')
        # 变体3: 无签名访问
        variants['无签名访问'] = None  # 表示直接去掉 x-signature
        hh = {'User-Agent': MOBILE_UA, 'Referer': 'https://www.douyin.com/'}
        ok = False
        for name, new_path in variants.items():
            try:
                if new_path is None:
                    qq = {k: v for k, v in q.items() if k not in ('x-signature',)}
                    uu = urlunsplit((sp.scheme, sp.netloc, sp.path,
                                     urlencode(qq, doseq=True), ''))
                else:
                    uu = urlunsplit((sp.scheme, sp.netloc, new_path,
                                     urlencode(q, doseq=True), ''))
                rr = requests.get(uu, headers=hh, timeout=timeout)
                if rr.status_code == 200 and len(rr.content) > 5000:
                    ok = True
            except Exception:
                continue
        if ok:
            return '探测到更高清/免签名变体可用（见上方直链）'
        return '已探测 去模板/q100/无签名 均不可用，无更高清档与永久 API'
    except Exception:
        return None


def resolve_douyin_page(url):
    """抖音分享页实时解析：短链重定向 → SSR(_ROUTER_DATA) → img_bitrate 高清档 / 视频地址 / 兜底直链。
    优先取 img_bitrate 的 ~q80 无尺寸模板（原图直出最高清），jpeg 副档，排除 water 水印版。"""
    try:
        if not HAS_REQUESTS:
            return None
        headers = {'User-Agent': MOBILE_UA, 'Accept-Language': 'zh-CN,zh;q=0.9'}
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None
        html = resp.text
        item = _douyin_page_item(html)

        # ── v4.7：slides 幻灯片作品优先（images[i].video.uri → 永久入口链）──
        if item:
            slides = _douyin_slides_entries(item)
            if slides:
                out = [s['entry'] for s in slides]
                out.append(_douyin_slides_note(
                    slides, 'SSR', total=len(item.get('images') or [])))
                durls, _dm = _douyin_images_from_detail(item)
                if durls:
                    out.extend(durls)
                    out.append('[时效] 抖音图片直链带签名（签名参数必带；Referer 可省略），'
                               '约30天过期，长期保存请 --save 落盘')
                out.extend(_douyin_music_entries(item))  # v4.9: BGM 音频
                return out

        # ── 纯图文作品: img_bitrate 高清档（~q80 无尺寸模板 = 原图直出）──
        if item:
            brs = item.get('img_bitrate') or []
            imgs = item.get('images') or []
            if brs or imgs:
                seen = set()
                out = []
                if brs:
                    for br in brs:  # gear_960p → gear_480p，顺序即码率档
                        for im in (br.get('images') or []):
                            for u in (im.get('url_list') or []):
                                u = clean_escaped(u)
                                if not u.startswith('http') or 'water' in u:
                                    continue
                                # 只取 ~q80 无尺寸模板（原图直出）；排除 shrink/lqen-new 降采样模板
                                if '~q80.' in u and 'shrink' not in u and 'lqen' not in u:
                                    k = u.split('?')[0]
                                    if k not in seen:
                                        seen.add(k)
                                        out.append(u)
                if not out:
                    # 回退: images 数组 url_list 全档（优先 lqen-new 原尺寸模板）
                    for im in imgs:
                        for u in (im.get('url_list') or []):
                            u = clean_escaped(u)
                            if not u.startswith('http') or 'water' in u:
                                continue
                            k = u.split('?')[0]
                            if k not in seen:
                                seen.add(k)
                                out.append(u)
                if out:
                    probe = _probe_douyin_quality(out[0])
                    note = ('[时效] 抖音图片直链带签名（约30天过期，签名参数必带、Referer 可省略）。'
                            + (probe or '无更高清档/无永久 API，建议立即下载保存'))
                    out.append(note)
                    return out

        # ── 视频作品: 优先 video.uri → 永久入口链；回退 play_addr（排除 BGM mp3）──
        if item:
            video = item.get('video') or {}
            if video.get('uri'):
                out = [douyin_play_entry(video['uri']),
                        '[永久] 抖音视频作品：video.uri → video_id 永久转播入口链'
                        '（免 Referer / 无签名，302 到 douyinvod，200 video/mp4），可长期引用']
                out.extend(_douyin_music_entries(item))  # v4.9: BGM 音频
                return out
            for key in ('play_addr', 'download_addr'):
                vv = video.get(key) or {}
                for u in (vv.get('url_list') or []):
                    u = clean_escaped(u)
                    if not u.startswith('http'):
                        continue
                    if 'ies-music' in u or '.mp3' in u or 'music' in u:
                        continue  # BGM 音频，跳过（已由 _douyin_music_entries 单独提取）
                    return [u, '[可渲染] 抖音官方 play 中转链接（无固定过期，302 滚动签名）'] + _douyin_music_entries(item)
            for key in ['playAddr', 'play_addr', 'videoUrl', 'video_url',
                        'originVideoUrl', 'downloadAddr']:
                m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', html)
                if m:
                    u = clean_escaped(m.group(1))
                    if u.startswith('http') and '.mp3' not in u and 'music' not in u:
                        return [u, '[时效] 抖音视频直链有时效，建议立即下载保存']

        # ── 旧逻辑兜底: images 数组 → url_list[0] ──
        imgs = _extract_json_array(html, 'images')
        if imgs and isinstance(imgs, list):
            out = []
            for img in imgs:
                ul = img.get('url_list') or []
                if ul:
                    out.append(clean_escaped(ul[0]))
            if out:
                out.append('[时效] 抖音图片直链带签名，建议立即下载保存')
                return out
        # 视频作品: playAddr / videoUrl 等（SSR 不可用时）
        for key in ['playAddr', 'play_addr', 'videoUrl', 'video_url',
                    'originVideoUrl', 'downloadAddr']:
            m = re.search(rf'"{key}"\s*:\s*"([^"]+)"', html)
            if m:
                u = clean_escaped(m.group(1))
                if u.startswith('http'):
                    return [u, '[时效] 抖音视频直链有时效，建议立即下载保存']
        # 兜底: 提取分享页全部 douyinpic 直链（去头像/去重）
        urls = [clean_escaped(u) for u in
                re.findall(r'"(https?:\\?/\\?/[^"]*?douyinpic[^"]*?)"', html)]
        seen, out = set(), []
        for u in urls:
            if 'avatar' in u:
                continue
            k = u.split('?')[0]
            if k not in seen:
                seen.add(k)
                out.append(u)
        if out:
            exp = _parse_expiry(out[0])
            out.append(f'[时效] 抖音图片直链带签名（{exp or "约30天"}过期；签名参数必带、Referer 可省略），建议立即下载保存或 --save 落盘')
            return out
        # ── v4.5 兜底: 新版【客户端渲染】分享页 SSR 无图 → detail API + 无头浏览器 ──
        # 注意: 短链 302 后要取 resp.url（重定向后的 /note/<id> 地址）提取 aweme_id
        aid = _extract_aweme_id(resp.url) or _extract_aweme_id(url)
        if aid:
            detail = _douyin_detail_via_browser(aid)
            if detail:
                # ── v4.7：slides 优先（detail.images[i].video.uri → 永久入口链）──
                slides = _douyin_slides_entries(detail)
                if slides:
                    out = [s['entry'] for s in slides]
                    out.append(_douyin_slides_note(
                        slides, 'detail API', total=len(detail.get('images') or [])))
                    durls, _dm = _douyin_images_from_detail(detail)
                    if durls:
                        out.extend(durls)
                        out.append('[时效] 抖音图片直链带签名（签名参数必带；Referer 可省略），'
                                   '约30天过期，长期保存请 --save 落盘')
                    out.extend(_douyin_music_entries(detail))  # v4.9: BGM 音频
                    return out
                durls, dmeta = _douyin_images_from_detail(detail)
                if durls:
                    exp = _parse_expiry(durls[0])
                    out = list(durls)
                    out.append(f'[时效] 抖音图片直链带签名（{exp or "约30天"}过期；签名参数必带、Referer 可省略），建议立即下载保存或 --save 落盘')
                    if dmeta:
                        dims = ' / '.join(f"{m['width']}x{m['height']}" for m in dmeta)
                        out.append(f'[尺寸] 各图 {dims}')
                    out.extend(_douyin_music_entries(detail))  # v4.9: BGM 音频
                    return out
                vu = _douyin_video_from_detail(detail)
                if vu:
                    return [vu, '[可渲染] 抖音官方 play 中转链接（无固定过期，302 滚动签名）'] + _douyin_music_entries(detail)
    except Exception:
        pass
    return None


# ════════════════════════════════════════════════════════════
# v4.5 新增：签名过期解析 / aweme_id 提取 / detail API+浏览器兜底 / 永久化落盘
# ════════════════════════════════════════════════════════════
def _parse_expiry(url):
    """从带签名 URL 提取 x-expires 过期时间（人类可读）。返回 'YYYY-MM-DD HH:MM:SS' 或 None。"""
    import datetime
    m = re.search(r'[?&]x-expires=(\d+)', url)
    if m:
        ts = int(m.group(1))
        try:
            return datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        except Exception:
            return str(ts)
    return None

# ════════════════════════════════════════════════════════════
# v4.7 新增：抖音【永久转播入口链】（slides / 视频作品通用）
# ════════════════════════════════════════════════════════════
# 永久入口链主机（按优先级）：aweme.snssdk.com 实测免 Referer、免签名
DOUYIN_PLAY_HOSTS = ('aweme.snssdk.com', 'www.douyin.com', 'api.amemv.com')


def douyin_play_entry(vid, ratio='1080p', line=0, host=DOUYIN_PLAY_HOSTS[0]):
    """video_id → 抖音永久转播入口链。
    vid 来源：aweme_detail.video.uri（视频作品）或 images[i].video.uri（slides 每片）。
    无签名参数、免 Referer，每次请求 302 到新签名的 douyinvod 地址（实测 200 video/mp4）。"""
    return f"https://{host}/aweme/v1/play/?video_id={vid}&ratio={ratio}&line={line}"


def douyin_play_entry_alts(vid, ratio='1080p'):
    """同一条 vid 的全部备用入口主机（主入口失效时依次回退）。"""
    return [douyin_play_entry(vid, ratio, 0, h) for h in DOUYIN_PLAY_HOSTS]


def _douyin_vid(video):
    """从 video 对象提取 vid：uri → play_addr.uri → play_addr_h264/lowbr → bit_rate[].play_addr.uri。
    （实测部分 detail 响应 video.uri 缺失，但 play_addr.uri 即 video_id，拼出的入口链可用。
    仅接受纯 id 形态——抖音 vid 形如 v0200fg10000xxxx，排除 http URL / 带路径的 BGM mp3 等异常值）"""
    v = video or {}
    cands = [v.get('uri')]
    for k in ('play_addr', 'play_addr_h264', 'play_addr_lowbr', 'download_addr'):
        pa = v.get(k) or {}
        if isinstance(pa, dict):
            cands.append(pa.get('uri'))
    for br in (v.get('bit_rate') or []):
        pa = br.get('play_addr') or {}
        if isinstance(pa, dict):
            cands.append(pa.get('uri'))
    for c in cands:
        if c and 'http' not in c and '/' not in c:
            return c
    return ''


def _douyin_slides_entries(item):
    """从作品 item（SSR item_list[0] 或 aweme_detail）提取 slides 每片的永久转播入口链。
    判据：images[i] 能解析出 vid（video.uri，回退 video.play_addr.uri）→ 该片含视频流。
    返回 [{index, vid, uri, width, height, duration, entry, alts}]；无任何视频片返回 []。"""
    out = []
    for i, im in enumerate(item.get('images') or [], 1):
        v = im.get('video') or {}
        vid = _douyin_vid(v)
        if not vid:
            continue
        out.append({
            'index': i, 'vid': vid, 'uri': im.get('uri'),
            'width': im.get('width'), 'height': im.get('height'),
            'duration': v.get('duration'),
            'entry': douyin_play_entry(vid),
            'alts': douyin_play_entry_alts(vid),
        })
    return out


def _douyin_has_video(item):
    """作品是否含视频流（判据：顶层 video 或 images[].video 能解析出 vid）。
    纯图文 note 无 video 字段 → False（无 play 入口链，只能走图片直链）。"""
    if _douyin_vid((item or {}).get('video')):
        return True
    return any(_douyin_vid(im.get('video')) for im in (item.get('images') or []))


def _douyin_slides_note(slides, source='', total=None):
    """生成 slides 入口链说明文案（永久性结论 + 使用提示 + 视频片/纯图片片分布）。"""
    tag = f'{source} ' if source else ''
    extra = ''
    if total and total > len(slides):
        extra = (f'（作品共 {total} 片，其中 {len(slides)} 片带视频流已给入口链，'
                 f'其余 {total - len(slides)} 片为纯图片，仅图片直链）')
    return (f'[永久] {tag}抖音 slides 幻灯片作品：'
            '带视频流的片 images[i].video.uri（回退 play_addr.uri）→ video_id 永久转播入口链，'
            '免 Referer / 无签名，302 到 douyinvod（200 video/mp4），可长期引用'
            + extra)


def _extract_aweme_id(url):
    """从抖音 URL 提取 aweme_id（v.douyin.com 短链需先 302 还原后才有 /note|video/<id>）。"""
    m = re.search(r'(?:note|video|share/(?:note|video))/(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'aweme_id=(\d+)', url)
    if m:
        return m.group(1)
    return None

def _douyin_detail_via_browser(aweme_id, timeout=45, retries=3):
    """通过无头浏览器获取抖音作品 detail JSON（应对新版【客户端渲染】分享页 SSR 无图 + 反爬签名）。
    流程：访问 douyin.com + 分享页拿 cookie/msToken → APIRequestContext 调 detail 接口 → 解析 aweme_detail。
    依赖 playwright + chromium（可用环境变量 DOUYIN_CHROME 指定浏览器路径）。
    v4.9：浏览器偶发被风控/拿不到 detail（实测约 1/3 概率空返回），自动重试 retries 次。
    返回 aweme_detail dict 或 None。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None
    import os, time
    exe = _find_chromium()  # v4.10: DOUYIN_CHROME 优先，其次自动探测 ms-playwright/系统 chromium
    for attempt in range(max(1, retries)):
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, executable_path=exe,
                                            args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
                ctx = browser.new_context(user_agent=BROWSER_UA, locale='zh-CN',
                                          viewport={"width": 1280, "height": 900})
                page = ctx.new_page()
                try:
                    page.goto('https://www.douyin.com/', timeout=20000, wait_until='domcontentloaded')
                except Exception:
                    pass
                time.sleep(2)
                try:
                    page.goto(f'https://www.iesdouyin.com/share/note/{aweme_id}/', timeout=25000,
                              wait_until='domcontentloaded')
                except Exception:
                    pass
                time.sleep(2)
                # 用 APIRequestContext（复用会话 cookie/msToken）调 detail 接口
                r = ctx.request.get(
                    f'https://www.douyin.com/aweme/v1/web/aweme/detail/?aweme_id={aweme_id}'
                    f'&device_platform=webapp&aid=6383&channel=channel_pc_web',
                    headers={'Referer': 'https://www.douyin.com/', 'Accept': 'application/json'})
                body = r.text() if r.status == 200 else ''
                browser.close()
                if body:
                    data = json.loads(body)
                    detail = data.get('aweme_detail') or None
                    if detail:
                        return detail
        except Exception:
            pass
        time.sleep(2 + attempt * 2)  # 退避后重试
    return None

def _douyin_images_from_detail(detail):
    """从 aweme_detail 提取图文 images 直链（url_list 无水印首选 + 尺寸 + 对象 uri）。
    返回 (urls, meta)，urls 为去重后的直链列表，meta 为 {uri,width,height} 列表。"""
    imgs = detail.get('images') or []
    urls, meta = [], []
    for im in imgs:
        ul = im.get('url_list') or []
        best = None
        for u in ul:
            u = clean_escaped(u)
            if not u.startswith('http'):
                continue
            if 'water' in u or 'tplv-dy-water' in u:
                continue  # 排除水印版
            if best is None:
                best = u
            elif '~tplv-dy-aweme-images:q75.webp' in u and 'jpeg' not in u:
                best = u  # webp 分享档优先于 jpeg 副档
        if not best and ul:
            best = clean_escaped(ul[0])
        if best:
            k = best.split('?')[0]
            if k not in urls:
                urls.append(best)
                meta.append({'uri': im.get('uri'), 'width': im.get('width'),
                             'height': im.get('height')})
    return urls, meta

def _douyin_video_from_detail(detail):
    """从 aweme_detail 提取视频播放入口。
    v4.7：优先 video.uri → 永久转播入口链（免 Referer / 无签名，可长期引用）；
    回退 play_addr / download_addr CDN 直链（带 x-expires 时效）。返回直链或 None。"""
    vid = detail.get('video') or {}
    uri = _douyin_vid(vid)
    if uri:
        return douyin_play_entry(uri)
    for key in ('play_addr', 'download_addr'):
        vv = vid.get(key) or {}
        for u in (vv.get('url_list') or []):
            u = clean_escaped(u)
            if u.startswith('http') and 'music' not in u and '.mp3' not in u and 'ies-music' not in u:
                return u
    return None

def _douyin_music_entries(detail):
    """v4.9 新增：从 aweme_detail 提取 BGM 音频直链。
    此前脚本在取视频时主动跳过 BGM（'BGM 可另提取'），未给自动化方法；现内置：
    读 detail.music.play_url.url_list（douyinstatic music 域，无防盗链），
    并兜底在整个 detail JSON 里正则找 ies-music/*.mp3。返回 [url..., note]，无 BGM 返回 []。"""
    out, seen = [], set()
    def _push(u):
        u = clean_escaped(u)
        if u.startswith('http') and u not in seen:
            seen.add(u)
            out.append(u)
    music = (detail or {}).get('music') or {}
    for u in ((music.get('play_url') or {}).get('url_list') or []):
        _push(u)
    # 兜底：整个 detail 里正则找 ies-music / douyinstatic music mp3
    if not out:
        try:
            raw = json.dumps(detail, ensure_ascii=False)
            for u in set(re.findall(r'https?:[^"\\ ]*?(?:ies-music|douyinstatic[^"\\ ]*?music)[^"\\ ]*?\.mp3[^"\\ ]*', raw)):
                _push(u)
        except Exception:
            pass
    if out:
        title = music.get('title') or ''
        extra = f"（{title}）" if title else ''
        out.append(f"[音频] 抖音 BGM 音频直链{extra}，douyinstatic music 域无防盗链，可嵌入 <audio> 播放")
    return out

def _douyin_entries_from_detail(detail):
    """v4.10 新增：把 aweme_detail 直接组装为最终交付条目（视频永久入口链 / 图文 + BGM + 说明）。"""
    base = 'https://www.douyin.com/video/'
    aid = detail.get('aweme_id') or ''
    out = []
    vid = _douyin_vid(detail.get('video') or {})
    if vid:
        out.extend(douyin_play_entry_alts(vid))
        out.append('[永久] 抖音 video_id 永久转播入口链（免 Referer / 无签名，302 到 douyinvod，实测 200 video/mp4），可长期引用')
    imgs, _meta = _douyin_images_from_detail(detail)
    if imgs:
        out.extend(imgs)
        out.append(f'[图文] 共 {len(imgs)} 张；douyinpic CDN 带 x-signature（约 30 天过期），需长期引用请 --save 落盘或转存自有图床')
    if not out and aid:
        out.append(f'{base}{aid}')
    if detail.get('desc'):
        out.append(f'[作品] {_note_desc(detail.get("desc"))}')
    if aid:
        out.append(f'[来源] {base}{aid}')
    out.extend(_douyin_music_entries(detail))
    return out


def verify_url(url):
    """v4.9 新增：HEAD 验证直链可用性。返回 (status:int|None, content_type:str, note:str)。
    视频入口链预期 302→video/*；音频预期 200 audio/*；图片直链预期 200 image/*。"""
    if not HAS_REQUESTS:
        return None, '', 'requests 不可用'
    try:
        r = requests.head(url, headers={'User-Agent': MOBILE_UA}, timeout=10, allow_redirects=True)
        return r.status_code, r.headers.get('Content-Type', ''), ''
    except Exception as e:
        return None, '', str(e)[:120]

def download_to_dir(url, out_dir, referer='https://www.douyin.com/'):
    """永久化落盘：把（带签名的）媒体下载到本地目录，返回本地绝对路径（永久保存）或 None。
    这是对"平台侧无永久直链"媒体（抖音图片/视频等）的真正永久方案。"""
    import os, hashlib
    if not HAS_REQUESTS:
        return None
    try:
        os.makedirs(out_dir, exist_ok=True)
        p = urlparse(url)
        ext = ''
        hh = {'User-Agent': MOBILE_UA, 'Referer': referer}
        try:
            rr = requests.head(url, headers=hh, timeout=10)
            ct = rr.headers.get('Content-Type', '')
            ext = {'image/webp': '.webp', 'image/jpeg': '.jpg', 'image/png': '.png',
                   'image/gif': '.gif', 'video/mp4': '.mp4', 'audio/mpeg': '.mp3'}.get(ct, '')
        except Exception:
            pass
        if not ext:
            m = re.search(r'\.(webp|jpe?g|png|gif|mp4|mp3|m4a|webm)(?:\?|$)', p.path)
            ext = '.' + m.group(1) if m else '.bin'
        fn = f"dy_{hashlib.md5(url.encode()).hexdigest()[:12]}{ext}"
        fp = os.path.join(out_dir, fn)
        if os.path.exists(fp) and os.path.getsize(fp) > 0:
            return fp
        rr = requests.get(url, headers=hh, timeout=40, stream=True)
        if rr.status_code != 200:
            return None
        with open(fp, 'wb') as f:
            for chunk in rr.iter_content(65536):
                f.write(chunk)
        return fp if os.path.getsize(fp) > 0 else None
    except Exception:
        return None

def resolve_douyin(url):
    if 'douyinpic.com' in url:
        exp = _parse_expiry(url)
        return [url, f"[时效] 抖音图片 CDN 有签名（{exp or '短期'}过期；签名参数必带、Referer 可省略），无免签名永久路径，请 --save 落盘永久化"]
    if 'douyinvod.com' in url:
        return [url, "[时效] 视频链接带 x-expires（约14天），到期需重新提取；可用 video.uri 生成永久入口链替代"]
    if 'aweme/v1/play' in url or 'aweme.snssdk.com' in url or 'api.amemv.com' in url:
        return [url, "[永久] 抖音 video_id 永久转播入口链（免 Referer / 无签名，302 到 douyinvod，实测 200 video/mp4），可长期引用；BGM 需单独提取"]
    if 'douyinstatic.com' in url and ('music' in url or url.endswith('.mp3')):
        return [url, "[音频] 抖音 BGM 音频直链，无 Referer 限制，可嵌入 <audio> 播放"]
    if 'v.douyin.com' in url or 'iesdouyin.com' in url:
        # ── v4.10: 短链先 302 还原拿 aweme_id → detail API（视频永久入口链 + 图文 + BGM），失败回退 SSR 嗅探 ──
        aid = _extract_aweme_id(url)
        if not aid and 'v.douyin.com' in url:
            for _ua in (MOBILE_UA, BROWSER_UA):
                try:
                    rr = requests.head(url, headers={'User-Agent': _ua}, allow_redirects=True, timeout=12)
                    aid = _extract_aweme_id(rr.url)
                except Exception:
                    aid = None
                if aid:
                    break
        if aid:
            _detail = _douyin_detail_via_browser(aid)
            if _detail:
                _out = _douyin_entries_from_detail(_detail)
                if _out:
                    return _out
        r = resolve_douyin_page(url)
        if r:
            # 探测媒体真实类型（动图 webp 等），标注在 notes
            for u in urls_only(r):
                p = probe_media_type(u)
                if p in ('gif', 'animated', 'video', 'audio'):
                    label = {'gif': 'GIF', 'animated': '动图', 'video': '视频', 'audio': '音频'}.get(p, p)
                    r = [x for x in r if not x.startswith('[媒体类型')]
                    r.append(f'[媒体类型: {label}]')
                    break
            return r
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


# ════════════════════════════════════════════════════════════
# v4.6 新增（逆向 CatCatch 猫抓 v2.7.2 + DataTool 智Tool v3.0.0 浏览器扩展）
#   A. 完整媒体扩展名 + MIME 类型表（猫抓 init.js Ext/Type 表）
#   B. 响应头嗅探（猫抓 background.js findMedia 三重判断：扩展名/Content-Type/资源类型）
#   C. 平台 CDN 域名清单（智Tool manifest host_permissions，嗅探识别平台媒体）
#   D. M3U8 master 按 BANDWIDTH 选最高清档（猫抓 m3u8.js hls.js 选档思路）
#   E. 小红书/微博 浏览器拦截页面自身 API 响应（智Tool inject.js API map 思路）
# ════════════════════════════════════════════════════════════
# A. 完整媒体扩展名（猫抓 init.js Ext 表）
CATCATCH_EXTENSIONS = {
    'video': ['flv', 'hlv', 'f4v', 'mp4', 'webm', 'ogv', 'mov', 'mkv', 'm4s', 'mpeg',
              'avi', 'wmv', 'asf', 'movie', 'divx', 'mpeg4', 'vid', 'ts', '3gp', 'm4v'],
    'audio': ['mp3', 'wma', 'wav', 'm4a', 'aac', 'ogg', 'acc', 'weba', 'opus', 'flac', 'mid', 'midi'],
    'stream': ['m3u8', 'm3u', 'mpd'],
    'image': ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'avif', 'heic', 'jfif', 'ico', 'tiff'],
}
# 完整 MIME 类型（猫抓 init.js Type 表）
CATCATCH_MIME = [
    'audio/', 'video/', 'application/ogg', 'application/vnd.apple.mpegurl',
    'application/x-mpegurl', 'application/mpegurl', 'application/octet-stream-m3u8',
    'application/dash+xml', 'application/m4s', 'application/x-mpegURL',
]

# C. 平台 CDN 域名清单（智Tool manifest host_permissions，用于嗅探识别平台媒体）
PLATFORM_CDN_DOMAINS = {
    '抖音/TikTok': ['.douyinvod.com', '.douyinpic.com', '.byteimg.com', '.ibyteimg.com',
                   '.tiktokcdn.com', '.tiktokcdn-us.com', '.tiktokv.com', '.muscdn.com'],
    '小红书': ['.xhscdn.com', '.xhslink.com', '.xhslink.cn', '.rednote.com', '.xiaohongshu.com'],
    '微博': ['.sinaimg.cn', '.weibocdn.com', '.weibo.com', '.wbimg.cn'],
    '头条': ['.toutiaoimg.com', '.toutiaovod.com', '.toutiaostatic.com', 'vod.bytedanceapi.com'],
    'B站': ['.bilibili.com', '.biliapi.net', '.hdslb.com', '.bilivideo.com', '.bilivideo.cn'],
    '快手': ['.kwai.com', '.kuaishou.com', '.yximgs.com', '.kwimgs.com'],
    '淘宝/天猫': ['.alicdn.com', '.aliyuncs.com'],
    '腾讯/微信': ['.qpic.cn', '.gtimg.cn', '.qq.com'],
    '新片场': ['mod-api.xinpianchang.com', '.xinpianchang.com'],
}
def identify_platform_cdn(url):
    """按 CDN 域名识别媒体所属平台（智Tool manifest 域名清单）"""
    for plat, domains in PLATFORM_CDN_DOMAINS.items():
        for d in domains:
            if d in url:
                return plat
    return None

# B. 响应头嗅探（猫抓 findMedia 思路）
def sniff_media_headers(url, timeout=8):
    """请求媒体 URL 读响应头判定：Content-Type / Content-Length / Content-Range / Content-Disposition。
    返回 {content_type, size, type} 或 None。用于嗅探中扩展名不明的 URL 判定。"""
    if not HAS_REQUESTS or not url.startswith('http'):
        return None
    try:
        h = {'User-Agent': BROWSER_UA, 'Range': 'bytes=0-1', 'Referer': 'https://www.douyin.com/'}
        r = requests.get(url, headers=h, timeout=timeout, stream=True, allow_redirects=True)
        if r.status_code not in (200, 206):
            return None
        ct = r.headers.get('Content-Type', '').split(';')[0].lower()
        cl = r.headers.get('Content-Length', '') or ''
        cr = r.headers.get('Content-Range', '')
        if cr and '/' in cr and cr.split('/')[1] != '*':
            cl = cr.split('/')[1]
        disp = r.headers.get('Content-Disposition', '').lower()
        size = int(cl) if cl.isdigit() else None
        r.close()
        mtype = None
        if ct.startswith('video/'):
            mtype = 'video'
        elif ct.startswith('audio/'):
            mtype = 'audio'
        elif ct.startswith('image/'):
            mtype = 'image'
        elif any(m in ct for m in ('mpegurl', 'dash+xml', 'm3u8', 'mpd', 'm4s')):
            mtype = 'stream'
        if not mtype and 'attachment' in disp:
            fn = re.search(r'filename="?([^"]+)"?', disp)
            if fn:
                mtype = detect_media_type(fn.group(1))
        return {'content_type': ct, 'size': size, 'type': mtype}
    except Exception:
        return None

def _browser_intercept_api(start_url, api_fragments, timeout=45):
    """【智Tool 思路】用无头浏览器打开页面，拦截页面自身请求的 JSON API 响应（页面已自带签名/登录态）。
    参数: start_url 要打开的页面; api_fragments 要拦截的 URL 片段列表（如 ['/api/sns/web/v1/feed']）。
    返回: [{url, body}]（匹配的响应列表）或 []。依赖 playwright + chromium（DOUYIN_CHROME 可指定路径）。"""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    import os, time
    exe = _find_chromium()  # v4.10: DOUYIN_CHROME 优先，其次自动探测 ms-playwright/系统 chromium
    captured = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path=exe,
                                        args=['--no-sandbox', '--disable-blink-features=AutomationControlled'])
            ctx = browser.new_context(user_agent=BROWSER_UA, locale='zh-CN',
                                      viewport={"width": 1280, "height": 900})
            page = ctx.new_page()

            def on_resp(resp):
                try:
                    u = resp.url
                    if any(f in u for f in api_fragments):
                        ct = resp.headers.get('content-type', '')
                        if 'json' in ct or 'text' in ct:
                            captured.append({'url': u, 'body': resp.text()})
                except Exception:
                    pass
            page.on('response', on_resp)
            try:
                page.goto(start_url, timeout=25000, wait_until='domcontentloaded')
                page.wait_for_timeout(7000)
            except Exception:
                pass
            browser.close()
    except Exception:
        pass
    return captured

def _note_desc(text, limit=60):
    """安全截断笔记描述"""
    if not text:
        return ''
    return text[:limit].replace('\n', ' ')

def resolve_tiktok(url):
    if 'tiktokcdn.com' in url:
        return [url, "[时效] TikTok CDN 链接有时效，建议立即下载"]
    if 'tiktok.com' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_kuaishou(url):
    if 'kuaishou.com' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_instagram(url):
    if 'cdninstagram.com' in url:
        return [url, "[时效] Instagram CDN 链接会过期，需从帖子页重新提取"]
    m = re.search(r'/(p|reel|tv|stories)/([A-Za-z0-9_-]+)', url)
    if m:
        return [f"https://www.instagram.com/{m.group(1)}/{m.group(2)}/", "[需要请求帖子页嗅探提取]"]
    return None


def resolve_bilibili(url):
    m = re.search(r'bilibili\.com/video/(BV[\w]+)', url)
    if m:
        return [f"https://player.bilibili.com/player.html?bvid={m.group(1)}&high_quality=1&danmaku=0"]
    m = re.search(r'bvid=(BV[\w]+)', url)
    if m:
        return [f"https://player.bilibili.com/player.html?bvid={m.group(1)}&high_quality=1&danmaku=0"]
    m = re.search(r'b23\.tv/([\w]+)', url)
    if m:
        return [f"[短链 {m.group(0)}，需先还原再提取 bvid] {url}"]
    return None


def resolve_youtube(url):
    m = re.search(r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/|youtube\.com/shorts/)([A-Za-z0-9_-]{11})', url)
    if m:
        return [f"https://www.youtube.com/embed/{m.group(1)}"]
    return None


def resolve_vimeo(url):
    m = re.search(r'vimeo\.com/(\d+)', url)
    if m:
        return [f"https://player.vimeo.com/video/{m.group(1)}"]
    return None


def resolve_dailymotion(url):
    m = re.search(r'dailymotion\.com/video/([A-Za-z0-9]+)', url)
    if m:
        return [f"https://www.dailymotion.com/embed/video/{m.group(1)}"]
    return None


def resolve_facebook(url):
    """Facebook/Instagram 系: fbcdn 媒体链接（时效）"""
    if 'fbcdn.net' in url:
        return [url, "[时效] fbcdn 媒体链接会过期，建议立即下载"]
    if 'facebook.com' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_pinterest(url):
    """Pinterest: pinimg.com 永久图床"""
    if 'pinimg.com' in url:
        return [url]
    if 'pinterest.com' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_reddit(url):
    """Reddit: redd.it / preview.redd.it 永久图床; v.redd.it 视频时效"""
    if 'preview.redd.it' in url or 'i.redd.it' in url or 'redd.it' in url:
        return [url]
    if 'v.redd.it' in url:
        return [url, "[时效] Reddit 视频链接需尽快下载"]
    if 'reddit.com' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_soundcloud(url):
    """SoundCloud: 音频页面，需嗅探提取流地址"""
    if 'soundcloud.com' in url:
        return [f"[需要请求页面嗅探提取音频流] {url}"]
    return None


def resolve_twitter(url):
    if 'pbs.twimg.com' in url:
        base = url.split('?')[0]
        return [base, base + ':orig', "[提示] 替换 :orig 可获取原图"]
    if 'twitter.com' in url or 'x.com' in url:
        return [f"[需要请求页面嗅探提取媒体] {url}"]
    return None


def resolve_zhihu(url):
    m = re.search(r'(pic\d?\.zhimg\.com/[^\s"\'?]+)', url)
    if m:
        return [m.group(1)]
    if 'zhihu.com' in url or 'zhimg.com' in url:
        return [url]
    return None


def resolve_wechat(url):
    if 'mmbiz.qpic.cn' in url:
        return [url]
    return None


def resolve_iqiyi(url):
    return [url, "[提示] 爱奇艺无公开永久直链，需页面观看或下载"] if 'iqiyi.com' in url else None


def resolve_youku(url):
    return [url, "[提示] 优酷无公开永久直链，需页面观看或下载"] if 'youku.com' in url else None


def resolve_qqvideo(url):
    return [url, "[提示] 腾讯视频无公开永久直链，需页面观看或下载"] if 'v.qq.com' in url else None


def resolve_twitch(url):
    m = re.search(r'twitch\.tv/(\w+)', url)
    if m:
        return [f"https://player.twitch.tv/?channel={m.group(1)}&parent=localhost"]
    return None


def resolve_douyu(url):
    m = re.search(r'douyu\.com/(\w+)', url)
    if m:
        return [f"https://www.douyu.com/{m.group(1)}", "[提示] 斗鱼无稳定永久直链"]
    return None


def resolve_huya(url):
    m = re.search(r'huya\.com/(\w+)', url)
    if m:
        return [f"https://www.huya.com/{m.group(1)}", "[提示] 虎牙无稳定永久直链"]
    return None


def resolve_vk(url):
    if 'vk.com' in url or 'vkvideo.ru' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_niconico(url):
    if 'nicovideo.jp' in url:
        return [f"[需要请求页面嗅探提取] {url}"]
    return None


def resolve_imgur(url):
    """Imgur: i.imgur.com 永久图床"""
    if 'imgur.com' in url or 'i.imgur.com' in url:
        return [url]
    return None


def resolve_tencent_img(url):
    if 'gtimg.com' in url:
        return [url]
    return None


def resolve_jianshu(url):
    if 'jianshu.io' in url or 'jianshu.com' in url:
        return [url]
    return None


def resolve_csdn(url):
    if 'csdnimg.cn' in url or 'csdn.net' in url:
        return [url]
    return None


def resolve_juejin(url):
    if 'byteimg.com' in url or 'juejin.cn' in url:
        return [url]
    return None


def resolve_sohu(url):
    if 'itc.cn' in url:
        return [strip_query(url)]
    return None


def resolve_duitang(url):
    if 'duitang.com' in url:
        return [strip_query(url)]
    return None


def resolve_huaban(url):
    if 'huaban.com' in url:
        return [url]
    return None


def resolve_aigei(url):
    if 'aigei.com' in url:
        return [strip_query(url), "[时效] token 参数过期后需重新获取"]
    return None


def resolve_588ku(url):
    if '588ku.com' in url:
        return [strip_query(url)]
    return None


def resolve_soogif(url):
    if 'soogif.com' in url:
        return [url]
    return None


def resolve_oppo(url):
    if 'oppo.cn' in url:
        return [url]
    return None


def resolve_100vr(url):
    if '100vr.com' in url:
        return [url]
    return None


def resolve_digitaling(url):
    if 'digitaling.com' in url:
        return [strip_query(url)]
    return None


def resolve_dooloor(url):
    if 'dooloor.com' in url or 'doooor.com' in url:
        return [strip_query(url)]
    return None


def resolve_bing(url):
    qs = parse_qs(urlparse(url).query)
    if 'riu' in qs:
        return [unquote(qs['riu'][0]), "[提示] 已从 bing 缓存还原原始来源 URL"]
    return [url, "[注意] bing 图片 CDN 有时效，建议还原原始来源"]


def resolve_google(url):
    if 'googleusercontent.com' in url:
        return [url, "[注意] googleusercontent 图片链接可能过期"]
    return [url]


def resolve_generic(url):
    parsed = urlparse(url)
    if parsed.query:
        return [f"{parsed.scheme}://{parsed.netloc}{parsed.path}", url]
    return [url]


# ════════════════════════════════════════════════════════════
# 4. 平台匹配规则（参考 Record_Manager + DataTool 扩展）
#    (pattern, resolver, name, permanent)
#    permanent: True=永久 / False=时效 / None=需嗅探
# ════════════════════════════════════════════════════════════

PLATFORM_RULES = [
    # ── 国内图床/CDN（永久优先）──
    (r'xiaohongshu\.com|xhscdn\.com|xhslink\.(?:com|cn|net)|rednote\.com|ci\.xiaohongshu\.com', resolve_xiaohongshu, '小红书', True),
    (r'sinaimg\.cn|weibo\.com|weibo\.cn', resolve_weibo, '微博', True),
    (r'bdstatic\.com|baidu\.com|hiphotos\.baidu', resolve_baidu, '百度', True),
    (r'itc\.cn', resolve_sohu, '搜狐', True),
    (r'gtimg\.com', resolve_tencent_img, '腾讯', True),
    (r'duitang\.com', resolve_duitang, '堆糖', True),
    (r'huaban\.com', resolve_huaban, '花瓣', True),
    (r'soogif\.com', resolve_soogif, 'Soogif', True),
    (r'oppo\.cn', resolve_oppo, 'OPPO', True),
    (r'100vr\.com', resolve_100vr, '100VR', True),
    (r'digitaling\.com', resolve_digitaling, '数英', True),
    (r'dooloor\.com|doooor\.com', resolve_dooloor, 'Doooor', True),
    (r'588ku\.com', resolve_588ku, '摄图网', False),
    (r'aigei\.com', resolve_aigei, '爱给网', False),
    (r'bing\.net|bing\.com', resolve_bing, '必应', False),
    (r'google\.com|googleusercontent\.com', resolve_google, 'Google', False),
    # ── 海外图床/CDN ──
    (r'pinimg\.com|pinterest\.com', resolve_pinterest, 'Pinterest', True),
    (r'preview\.redd\.it|i\.redd\.it|v\.redd\.it|redd\.it|reddit\.com', resolve_reddit, 'Reddit', True),
    (r'imgur\.com', resolve_imgur, 'Imgur', True),
    (r'fbcdn\.net|facebook\.com', resolve_facebook, 'Facebook', False),
    # ── 视频平台（可嵌入，永久性较好）──
    (r'bilibili\.com|b23\.tv', resolve_bilibili, 'Bilibili', True),
    (r'youtube\.com|youtu\.be', resolve_youtube, 'YouTube', True),
    (r'vimeo\.com', resolve_vimeo, 'Vimeo', True),
    (r'dailymotion\.com', resolve_dailymotion, 'Dailymotion', True),
    (r'twitch\.tv', resolve_twitch, 'Twitch', False),
    (r'douyu\.com', resolve_douyu, '斗鱼', False),
    (r'huya\.com', resolve_huya, '虎牙', False),
    # ── 社交/内容平台 ──
    (r'douyin\.com|douyinpic\.com|douyinvod\.com|douyinstatic\.com|iesdouyin\.com|aweme\.snssdk\.com|api\.amemv\.com', resolve_douyin, '抖音', False),
    (r'tiktok\.com|tiktokcdn\.com', resolve_tiktok, 'TikTok', False),
    (r'kuaishou\.com', resolve_kuaishou, '快手', False),
    (r'instagram\.com|cdninstagram\.com', resolve_instagram, 'Instagram', False),
    (r'twitter\.com|x\.com|pbs\.twimg\.com', resolve_twitter, 'X (Twitter)', False),
    (r'zhihu\.com|zhimg\.com', resolve_zhihu, '知乎', True),
    (r'weixin\.qq\.com|mp\.weixin|mmbiz\.qpic\.cn', resolve_wechat, '微信公众号', True),
    (r'jianshu\.com|jianshu\.io', resolve_jianshu, '简书', True),
    (r'csdn\.net|csdnimg\.cn', resolve_csdn, 'CSDN', True),
    (r'juejin\.cn|byteimg\.com', resolve_juejin, '掘金', True),
    (r'notion\.so', resolve_generic, 'Notion', None),
    # ── 海外音频/视频平台 ──
    (r'soundcloud\.com', resolve_soundcloud, 'SoundCloud', None),
    (r'vk\.com|vkvideo\.ru', resolve_vk, 'VK', None),
    (r'nicovideo\.jp', resolve_niconico, 'Niconico', None),
    # ── 国内视频（无公开直链）──
    (r'iqiyi\.com', resolve_iqiyi, '爱奇艺', False),
    (r'youku\.com', resolve_youku, '优酷', False),
    (r'v\.qq\.com', resolve_qqvideo, '腾讯视频', False),
]

# 用于页面嗅探的平台元信息（名称映射）
PLATFORM_META = [(p, n) for p, _, n, _ in PLATFORM_RULES]


def resolve_url(url, with_type=True):
    """解析 URL，返回 {platform, permanent, original, type, urls, notes, expiry}"""
    for pattern, resolver, name, permanent in PLATFORM_RULES:
        if re.search(pattern, url, re.I):
            results = resolver(url)
            if results:
                ul = urls_only(results)
                exp = None
                for u in ul:
                    exp = _parse_expiry(u)
                    if exp:
                        break
                out = {
                    'platform': name,
                    'permanent': permanent,
                    'original': url,
                    'type': media_type_label(url),
                    'urls': ul,
                    'notes': notes(results),
                    'expiry': exp,
                }
                # v4.7: 结果全为抖音 video_id 永久转播入口链时，修正 permanent=True
                if name == '抖音' and ul and all(
                        ('aweme.snssdk.com' in u or 'api.amemv.com' in u
                         or ('douyin.com' in u and 'aweme/v1/play' in u))
                        for u in ul):
                    out['permanent'] = True
                return out
    out = {
        'platform': '未知',
        'permanent': None,
        'original': url,
        'type': media_type_label(url),
        'urls': [url],
        'notes': ['未匹配到已知平台规则'],
        'expiry': _parse_expiry(url),
    }
    return out


# ════════════════════════════════════════════════════════════
# 5. CLI
# ════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description='社媒平台媒体直链解析器 v4.9 (国内+海外, 优先永久直链; 抖音支持 --save 永久化落盘 + --play-entry 永久转播入口链 + 内置 BGM 音频提取 + --verify 验活)')
    parser.add_argument('urls', nargs='*', help='要解析的 URL')
    parser.add_argument('--stdin', action='store_true', help='从 stdin 读取 URL（每行一个）')
    parser.add_argument('--batch', type=str, help='从文件读取 URL（每行一个）')
    parser.add_argument('--sniff', type=str, help='猫抓式页面嗅探: 请求网页并提取所有媒体直链')
    parser.add_argument('--save', type=str, metavar='DIR', help='永久化落盘: 把带签名的时效媒体下载到本地目录（永久保存），同时打印原始直链')
    parser.add_argument('--play-entry', nargs='+', metavar='VID', help='抖音 video_id（video.uri）→ 永久转播入口链，可传多个或用逗号分隔（v4.7）')
    parser.add_argument('--verify', action='store_true', help='v4.9: 对输出的每条直链做 HEAD 验活，报告 HTTP 状态码与 Content-Type（视频入口链预期 302→video/*，音频预期 200 audio/*）')
    parser.add_argument('--json', action='store_true', help='JSON 格式输出')
    parser.add_argument('--platforms', action='store_true', help='列出所有支持平台')
    args = parser.parse_args()

    # v4.7: video_id → 永久转播入口链（slides 每片 / 视频作品通用）
    if args.play_entry:
        vids = [v.strip() for item in args.play_entry for v in item.split(',') if v.strip()]
        if args.json:
            print(json.dumps([{'vid': v, 'entry': douyin_play_entry(v),
                               'alts': douyin_play_entry_alts(v)} for v in vids],
                             ensure_ascii=False, indent=2))
        else:
            for v in vids:
                print(douyin_play_entry(v))
                for alt in douyin_play_entry_alts(v)[1:]:
                    print(f"  (备用入口) {alt}")
        return

    if args.platforms:
        print(f"支持平台 ({len(PLATFORM_RULES)} 条规则):")
        seen = set()
        for _, _, name, perm in PLATFORM_RULES:
            if name not in seen:
                seen.add(name)
                tag = '永久' if perm else ('时效' if perm is False else '嗅探')
                if name == '抖音':
                    tag += '（图片流时效 / 视频流有永久入口链）'
                print(f"  {name} [{tag}]")
        return

    if args.sniff:
        result = sniff_page(args.sniff)
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"平台: {result['platform']} | 页面: {result['page']}")
            if result.get('error'):
                print(f"⚠ {result['error']}")
            print(f"发现媒体 {len(result['media'])} 个:")
            for i, m in enumerate(result['media'], 1):
                print(f"  [{i}] {m['type']}: {m['url'][:120]}")
                if m.get('streams'):
                    for s in m['streams'][:5]:
                        print(f"      流: {s[:120]}")
                if m.get('segment_count'):
                    print(f"      分片数: {m['segment_count']}")
        return

    urls = list(args.urls)
    if args.stdin:
        urls.extend(line.strip() for line in sys.stdin if line.strip())
    if args.batch:
        with open(args.batch, 'r') as f:
            urls.extend(line.strip() for line in f if line.strip())

    if not urls:
        parser.print_help()
        sys.exit(1)

    results = [resolve_url(u) for u in urls]

    # --save 永久化落盘：把带签名的时效媒体下载到本地（平台侧无永久直链时的真正永久方案）
    if args.save:
        for r in results:
            if r['permanent'] is False and r['urls']:
                saved = []
                for u in r['urls']:
                    fp = download_to_dir(u, args.save)
                    if fp:
                        saved.append(fp)
                if saved:
                    r['saved'] = saved
                    r['notes'].append(f"[永久化] 已下载到本地 {len(saved)} 个文件，永久保存不随签名过期")

    # v4.9: --verify 对每条直链 HEAD 验活
    if args.verify:
        for r in results:
            r['checks'] = []
            for u in r['urls']:
                st, ct, err = verify_url(u)
                r['checks'].append({'url': u, 'status': st, 'content_type': ct, 'error': err})

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for r in results:
            perm = '✅ 永久' if r['permanent'] else ('⚠️ 时效' if r['permanent'] is False else '🔍 需嗅探')
            print(f"\n{'='*60}")
            print(f"平台: {r['platform']} | {perm} | 类型: {r['type']}")
            print(f"原始: {r['original']}")
            if r.get('expiry'):
                print(f"过期: {r['expiry']}")
            print(f"直链:")
            for u in r['urls']:
                print(f"  → {u}")
            for chk in r.get('checks', []):
                st = chk['status']
                tag = f"{st} {chk['content_type']}".strip() if st else f"❌ {chk['error']}"
                print(f"     [验活] {tag}")
            for n in r['notes']:
                print(f"  ⚠ {n}")
            for s in r.get('saved', []):
                print(f"  💾 已永久保存: {s}")


if __name__ == '__main__':
    main()
