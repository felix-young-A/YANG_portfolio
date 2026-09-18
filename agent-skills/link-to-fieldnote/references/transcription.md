# 音频转写：判定规则与 Whisper 技术规范

> 本文件承载：音频转写判定规则（何时强制/何时可跳过、速查表）与 Whisper 转写全流程技术规范（安装、模型选择、强制参数、预处理、耗时、纠错）。音频/视频的下载获取见 [content-fetching.md](content-fetching.md)。

## 目录

- [音频转写判定规则（Transcription Rules）](#音频转写判定规则transcription-rules)
  - [强制转写的场景](#强制转写的场景)
  - [可以跳过转写的场景](#可以跳过转写的场景)
  - [转写判定速查表](#转写判定速查表)
- [音频转写技术规范（Whisper Guide）](#音频转写技术规范whisper-guide)
  - [安装](#安装)
  - [模型选择](#模型选择)
  - [强制参数](#强制参数)
  - [音频预处理](#音频预处理)
  - [预期耗时](#预期耗时)
  - [转写后处理（纠错表）](#转写后处理纠错表)

---

## 音频转写判定规则（Transcription Rules）

### 强制转写的场景

以下场景中，音频转写是**必须执行的步骤**，不能跳过：

1. 用户要求"文稿""逐字稿""完整文稿""字幕排版""转写稿"
2. 用户说"提取完整文稿"
3. A 类任务（提炼知识）且需要提炼可复用知识（需要完整内容才能准确提炼，不能仅基于页面简介或片段信息）

### 可以跳过转写的场景

必须**同时满足以下所有条件**才可以跳过转写：

1. 平台有完整公开字幕，**且**已成功获取全部字幕内容
2. 或用户明确要求"只基于页面信息整理，不需要转写"

**注意**：B站部分视频只有自动字幕（可能不完整），这种情况不算"完整公开字幕"，仍需尝试音频转写。

**原则**：宁可多转写，不可遗漏。当不确定字幕是否完整时，执行音频转写。

### 转写判定速查表

| 用户要求 | 音频转写 | 说明 |
|---------|---------|------|
| "文稿 / 逐字稿 / 完整文稿" | **强制执行，不可跳过** | 这是 B 类任务的核心 |
| "总结 / 笔记 / 提炼要点" | 优先使用字幕；字幕不完整时执行音频转写 | A 类允许用字幕替代，但覆盖率不足时应补充 |
| "只基于页面信息整理" | **跳过音频转写** | 用户明确声明，尊重其选择 |

---

## 音频转写技术规范（Whisper Guide）

### 安装

**首选（openai-whisper）**：

```bash
pip install setuptools --break-system-packages   # 若环境缺 pkg_resources 必须先装，否则 openai-whisper 构建报错
pip install openai-whisper --break-system-packages
```

**备选（faster-whisper）**：openai-whisper 构建失败或 CPU 转写过慢时，改用 faster-whisper（CTranslate2 实现，CPU 下快 2~4 倍，中文准确率相当，本次实战已验证可用）：

```bash
pip install faster-whisper --break-system-packages
```

faster-whisper 使用示例（输出带时间戳的段落）：

```python
from faster_whisper import WhisperModel
model = WhisperModel("base", device="cpu", compute_type="int8")  # 也支持本地模型目录路径
segments, info = model.transcribe("audio.wav", language="zh", vad_filter=True)
for seg in segments:
    print(f"[{seg.start:.1f}-{seg.end:.1f}] {seg.text}")
```

**模型下载失败（HuggingFace 401 / 连接超时）**：openai-whisper 与 faster-whisper 首次使用都会从 HuggingFace 下载模型，国内环境常遇到 401（CAS 客户端报错）或连接失败。解决方案：设镜像手动下载到本地目录，再从本地路径加载，绕开联网：

```bash
export HF_ENDPOINT=https://hf-mirror.com
python3 -c "
from huggingface_hub import snapshot_download
snapshot_download('Systran/faster-whisper-base', local_dir='/path/to/whisper-models/faster-whisper-base')
"
```

```python
# 之后从本地目录加载，无需再联网
model = WhisperModel("/path/to/whisper-models/faster-whisper-base", device="cpu", compute_type="int8")
```

**ffmpeg 缺失（无 sudo 权限时）**：系统没有 ffmpeg 且无法 apt 安装时，用 pip 安装 imageio-ffmpeg 获取内置二进制（本次实战已验证）：

```python
import imageio_ffmpeg
ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()   # 返回 ffmpeg 可执行文件绝对路径
```

拿到路径后，把后续所有 `ffmpeg` / `ffprobe` 命令换成该绝对路径前缀即可（如 `"$FFMPEG" -i ...`）。

### 模型选择

| 模型 | 中文准确率 | CPU 耗时（21分钟音频） | 是否允许使用 |
|------|-----------|----------------------|-------------|
| `tiny` | 一般 | ~5~10 分钟 | 可以但不推荐 |
| `base` | 良好（中文准确率和速度的最佳平衡） | ~21~42 分钟（1~2 倍实时） | **默认使用** |
| `small` | 较好 | openai-whisper 极慢；faster-whisper(int8) 约 2~4 倍实时 | **faster-whisper 可用，openai-whisper 仅 GPU** |
| `medium` | 很好 | 极慢（CPU 下可能数小时） | **禁止使用** |
| `large` | 最好 | 极慢（CPU 下可能数小时） | **禁止使用** |

**规则**：
- 默认使用 `base` 模型。
- openai-whisper：`small` 仅在 GPU 可用时使用，CPU 下禁止使用。
- faster-whisper（int8 量化）：CPU 下 `small` 可用（约 2~4 倍实时，追求准确率时选用），`base` 仍是默认。
- `medium` / `large` 根据所在环境的参数配置来谨慎考量评判是否选择（CPU 下可能耗时数小时）。
- 当音频过长，结合环境配置参数、模型等综合考量，如果一次性转写消耗过大或者存在拖慢的可能时，可考虑音频分片转写。

### 强制参数

```bash
whisper audio.wav \
  --model base \
  --language Chinese \
  --output_format txt \
  --output_dir ./output/
```

- `--language Chinese`：**必须指定**。指定语言可大幅加速，避免自动语言检测的额外耗时。
- `--output_format txt`：输出纯文本格式，最简洁。
- `--output_dir`：指定输出目录，避免转写文件散落在工作目录。

### 音频预处理

必须先将视频/音频文件转换为 16kHz 单声道 WAV：

```bash
ffmpeg -i video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 audio.wav
```

参数说明：
- `-vn`：去除视频轨道
- `-acodec pcm_s16le`：16 位 PCM 编码（Whisper 要求）
- `-ar 16000`：16kHz 采样率（Whisper 要求）
- `-ac 1`：单声道

### 预期耗时

- `base` 模型在 CPU 上约 1~2 倍实时时长
- 例如：21 分钟音频，转写耗时约 21~42 分钟
- 在启动转写前，**告知用户预期等待时间**
- 每隔段时间必须检查进度，且告知用户当前任务进度状态，禁止闷头盲目等待，防止陷入循环与无用等待。可采用动态自制简易显示进度条监控进度，或者文字描述等方式进行展示告知。

### 转写后处理（纠错表）

Whisper 转写后**必须**进行同音字纠错。建立常见错误映射表，在整理文稿时批量替换。

**人名纠错**（高频出错）：
- 萨谬尔森 → 萨缪尔森
- 巴切里耶 → 巴契里耶
- 其他根据视频主题上下文判断

**金融术语纠错**（视频主题相关时）：
- B股、H股（常见被识别为"比股""aich"等）
- 羊群效应（常见被识别为"阳群效应"）
- 创业板（常见被识别为"创野板"）
- 中小板（常见被识别为"中小办"）
- 随机漫步（常见被识别为"随几慢不"）
- 其他金融专业术语根据上下文判断

**品牌名/机构名纠错**：
- 工商银行（常见被识别为"工业银行"）
- 建设银行（常见被识别为"建议银行"）
- 光大银行（常见被识别为"广大银行"）
- 其他品牌名根据上下文判断

**通用纠错原则**：
- 转写文本中出现不符合语义的词组时，根据上下文推断正确的词
- 人名、地名、专业术语是 Whisper 最容易出错的类别，需要重点检查
- 纠错时保持原意，不要过度修改说话人的表达习惯
- 从全文视角检查语句，尽量确保不出现低级词语文字错误。
