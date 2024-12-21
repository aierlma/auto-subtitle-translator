# Auto Subtitle Translator

一个自动化的视频字幕翻译工具,集成了语音识别、字幕生成和翻译功能。仅限使用Sakura模型翻译，未考虑集成任何其他翻译模型，仅支持日语到简体中文。
对于gpt翻译需求，推荐使用[subtitle-translator-electron](https://github.com/gnehs/subtitle-translator-electron)

## 功能特点

- 自动语音识别(使用 faster-whisper+VAD)
- 字幕生成和格式转换
- 支持多语言翻译
- 支持批量处理
- 字幕去重优化


## 使用方法


```bash
python cli.py "path/to/your/video.mp4" [127.0.0.1:8080]
```
后面的[127.0.0.1:8080]是你的sakura api 地址，选择性填写。
若不填写，则需要在该项目的文件夹旁拥有Sakura_Launcher_GUI项目。并且使用main.py脚本启动sakura模型，或者可以自行修改cli.py中的start_sakura_service函数。

### 进阶用法
在已经开启Sakura服务器的情况下，可以使用monitor_videos.bat(限Windows)对指定文件夹里的所有mp4文件遍历并进行字幕生成。

### 配置说明

项目包含两个主要模块:

1. faster-whisper-webui: 语音识别和字幕生成模块
2. GalTransl: 翻译处理模块

详细配置请参考各模块的配置文件。

whisper转录模型会在一次使用时自动下载。
翻译模型使用的Sakura模型还请自行配置。推荐使用[Sakura_Launcher_GUI](https://github.com/PiDanShouRouZhouXD/Sakura_Launcher_GUI)
项目进行配置

## 项目结构

```
auto-subtitle-translator/
├── cli.py                 # 主命令行接口
├── delete_repeat.py       # 字幕去重工具
├── srt2prompt.py         # 字幕转换工具
├── faster-whisper-webui/ # 语音识别模块
└── GalTransl/            # 翻译处理模块
```

## 依赖说明

- Python 3.8+
- 其他依赖详见 第三方项目的requirments


## 许可证

本项目采用 GPL 许可证 - 详见 [LICENSE](LICENSE) 文件

### 第三方许可证

本项目使用了以下开源项目：

- [faster-whisper-webui](https://huggingface.co/spaces/aadnk/faster-whisper-webui) - Apache License 2.0
- [GalTransl](https://github.com/xd2333/GalTransl) - GNU General Public License
