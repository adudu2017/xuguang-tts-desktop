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

中文翻译使用本地 `Helsinki-NLP/opus-mt-en-zh` 模型，放到 `models/opus-mt-en-zh`，在 Ming 环境安装 sentencepiece、sacremoses 和 huggingface_hub 后下载：

```powershell
runtime/ming/Scripts/python -m pip install sentencepiece sacremoses huggingface_hub
runtime/ming/Scripts/python -c "from huggingface_hub import snapshot_download; snapshot_download('Helsinki-NLP/opus-mt-en-zh', local_dir='models/opus-mt-en-zh')"
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
