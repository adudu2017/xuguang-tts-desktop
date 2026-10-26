# 叙光 · Xuguang TTS Desktop

Windows 本地语音合成客户端，支持 Ming 0.5B 与 Qwen3-TTS、个人参考音色、中英文朗读以及带字幕的 MP4 导出。

![叙光](assets/themes/gold.png)

## 功能

- 中文 / 英文语音合成；Qwen 英文使用 English 参数。
- 录制、导入、试听、重命名及删除音色，录制时显示参考文案。
- 后台合成、分段进度、历史音频、播放拖动与分段文字高亮。
- WAV、TXT、SRT 和时间轴导出；英文字幕可离线翻译为中文。
- 1080p MP4：静态背景 + H.264/AAC + 画面内双语字幕，支持自定义图片、进度和取消。
- 四套独立切换的界面皮肤与背景：暖金书页、星海蓝、翡翠林语、暮紫花境。
- 日期与当日批次命名，配置在本地保存。
- Ming 常驻、参考音色缓存和 FlowGraph；Qwen 显式 KV 注意力优化、完整句子分段、异常长度保护和诊断日志。

## 源码运行

Windows、Python 3.12，模型推理推荐 NVIDIA CUDA 显卡。界面与两种模型运行环境分离。

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements-ui.txt
.venv/Scripts/python app.py
```

首次运行没有预设音色或模型路径。点击“设置”配置引擎，再通过“制作音色”录制或导入你有权使用的录音。源代码不包含私人音色、任务历史、模型权重、已生成音频或运行环境。

## 模型权重下载（中国大陆优先：ModelScope 魔搭）

模型权重不包含在 GitHub 仓库中。以下下载统一使用 **ModelScope 魔搭**，不需要从 Hugging Face 下载，也不会在失败时自动切换到 Hugging Face。

| 用途 | ModelScope 下载页面 | 本地保存目录 |
|---|---|---|
| Qwen 音色克隆 | [Qwen3-TTS-12Hz-0.6B-Base](https://modelscope.cn/models/Qwen/Qwen3-TTS-12Hz-0.6B-Base) | models/Qwen3-TTS-12Hz-0.6B-Base |
| Ming 语音合成 | [Ming-3.0-tts-0.5b](https://modelscope.cn/models/inclusionAI/Ming-3.0-tts-0.5b) | models/Ming-3.0-tts-0.5b |
| 英文字幕译中文 | [opus-mt-en-zh](https://modelscope.cn/models/Helsinki-NLP/opus-mt-en-zh) | models/opus-mt-en-zh |

先安装下载工具（可用清华 PyPI 镜像）：

```powershell
python -m pip install modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple
python download-models.py All --list
python download-models.py All
```

也可分别下载：

```powershell
python download-models.py Qwen
python download-models.py Ming
python download-models.py Translation
```

第二个位置参数可指定模型总目录，例如 `python download-models.py All D:/AI/models`；程序会在其中建立各模型子目录。若使用打包版，字幕翻译模型必须放到 EXE 同目录的 `models/opus-mt-en-zh`。TTS 模型路径可在设置中选择。

请下载完整仓库，不能只下载顶层权重：Qwen 需要 `speech_tokenizer/`，Ming 需要 `campplus.onnx` 和 tokenizer 文件，翻译需要 `source.spm`、`target.spm` 等文件。下载脚本会保留必要文件，仅跳过翻译模型不使用的 TensorFlow、Flax 和 Rust 权重。

2026-10-24 已验证上述 ModelScope 仓库文件列表及 config.json 可访问；实际速度取决于网络。本次没有重新下载数 GB 权重。下载完成后推理读取本地模型。安装 Python 依赖、PyTorch 和 Ming 源码仍分别涉及包源、PyTorch 官网及 GitHub，这与模型权重下载来源不同。

## 模型环境

```powershell
./setup-engines.ps1 -Engine Both -DownloadModels
```

安装脚本以 CUDA 12.4 / PyTorch 2.5.1 为基线；两个引擎必须使用独立环境。实际已测试包版本记录在 `qwen-tested-packages.txt` 和 `ming-tested-packages.txt`。第三方依赖与驱动可能需要针对电脑调整，本次仓库整理没有在全新电脑重做安装验证。

| 设置项 | 路径 |
|---|---|
| Qwen Python | runtime/qwen/Scripts/python.exe |
| Qwen 模型 | models/Qwen3-TTS-12Hz-0.6B-Base |
| Ming Python | runtime/ming/Scripts/python.exe |
| Ming 模型 | models/Ming-3.0-tts-0.5b |
| Ming 源码 | runtime/Ming-3.0-tts |

Ming 固定源码版本 `028c1eace193e7acdb256453da89b6e9207e052b`。Ming 的本客户端推理路径需要 CUDA。Qwen 优化可能改变采样结果，不能视为逐样本等价；任务会固定注意力设置避免恢复时混用。生成长度保护不等于语义漏读检测，输出仍需试听。

## 字幕翻译和视频

中文翻译使用本地 Marian `opus-mt-en-zh` 模型，从上表的 ModelScope 仓库下载，放到 `models/opus-mt-en-zh`。在 Ming 环境安装所需依赖并下载：

```powershell
runtime/ming/Scripts/python -m pip install sentencepiece sacremoses modelscope -i https://pypi.tuna.tsinghua.edu.cn/simple
runtime/ming/Scripts/python download-models.py Translation
```

MP4 导出需要带 libass、libx264 的 FFmpeg，放到 `tools/ffmpeg.exe` 或配置在 PATH。中文使用 Windows 微软雅黑字体。字幕时间轴按合成分段，不是逐词对齐。若未安装翻译模型，音频保留，系统提示中文字幕失败。

## 构建和验证

```powershell
python -m unittest discover -s . -p 'test_*.py'
./build.ps1
```

构建产物为 `dist/VoiceDesk/VoiceDesk.exe`，须连同 `_internal`、外部 worker 源文件、assets 一起使用。模型和独立 Python 环境另行配置，FFmpeg 另行安装。这不是包含所有模型的一体化安装包。

## 数据与主题

配置、批次号和任务在 `data/`，音色在 `voices/`，均默认不进入 Git。诊断包含阶段耗时、步数、心跳与超时调用栈。四主题说明及图像生成提示词见 `assets/themes/主题说明.md`。品牌图由 AI 生成，应用图标由本项目绘制。

## 来源

交互目标参考 [qwen3-tts-android-zh](https://github.com/adudu2017/qwen3-tts-android-zh)，客户端使用 Python/Tkinter 独立实现。

- [Qwen3-TTS](https://github.com/QwenLM/Qwen3-TTS)
- [Ming-3.0-tts](https://github.com/inclusionAI/Ming-3.0-tts)
- [FFmpeg](https://ffmpeg.org/)

第三方模型、运行库和工具遵循各自许可，未在此仓库分发其模型或二进制文件。本仓库尚未指定开源许可证。

### 中文字幕选项

输出语言选择中文时，可选择「仅中文字幕」（默认）、「中英双语字幕」或「不生成字幕」。英文输出仍自动生成英中双语字幕。选择不生成字幕时，保存音频及原文 TXT，不生成 SRT/时间轴字幕，也不提供字幕视频导出。历史任务保留各自的字幕设置。

中译英使用独立的本地模型 [Helsinki-NLP/opus-mt-zh-en](https://modelscope.cn/models/Helsinki-NLP/opus-mt-zh-en)，通过 ModelScope 下载：

```powershell
python download-models.py TranslationZH
```

模型保存到 `models/opus-mt-zh-en`，安装后翻译可离线运行。`All` 同时包含两个方向的翻译模型。缺少模型或翻译失败时保留音频及原文字幕，并显示提示。

### 字幕质量保护

生成前检查稿件主要语言与输出语言是否匹配；输出语言不会自动翻译朗读稿件。字幕翻译根据每段原文判断中英方向，语言不明确时才使用任务语言。仅标点、异常连续重复、错误目标语言或达到长度上限的译文会触发一次短分段重试，失败后保留原文并记录 `complete.translation-report.json`。音频保存和 MP4 导出也会拦截明显异常的历史译文。这些规则只检查明显异常，不代表译文语义已经人工校对。

### 视频背景音乐（音源待安装）

MP4 导出窗口提供关闭背景音乐与两个固定曲目槽位，默认关闭。音乐不足视频长度时循环，开头结尾淡入淡出；混音将人声标准化为 -18 LUFS、音乐为 -30 LUFS，再在人声出现时压低音乐，并限制混合峰值。关闭音乐时保持原有导出处理。原始 TTS 音频及主界面试听仍为纯人声。

指定音源：网易云歌曲 `1989154383`、`2150746620`。2026-10-26 测试公开音源链接均返回 404 页面，尚未取得歌曲文件；仓库与客户端目前不含这两首音乐。取得可用文件后分别放到 `assets/music/1989154383.mp3`、`assets/music/2150746620.mp3`。缺少文件时明确提示，不会静默导出无配乐视频。混音流程已使用临时测试音频验证，实际曲目的听感平衡待取得文件后验证。
