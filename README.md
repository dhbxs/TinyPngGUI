# Tinify Compress

Windows 桌面客户端，基于 [Tinify / TinyPNG API](https://tinypng.com/developers/reference/python) 压缩图片。支持拖拽上传、批量处理、API Key 本地保存。

技术栈：Python 3.11+ · CustomTkinter · tkinterdnd2 · 官方 `tinify` SDK · [`uv`](https://docs.astral.sh/uv/) 管理环境

## 功能

- 填入并校验自己的 Tinify API Key
- 拖拽图片 / 文件夹，或按钮选择文件
- 批量压缩 PNG / JPEG / WebP / AVIF / JXL / HEIC
- 输出：同目录加后缀、覆盖原文件、指定文件夹
- 显示压缩前后体积与节省比例、本月压缩次数

## 环境要求

- Windows 10/11
- [uv](https://docs.astral.sh/uv/getting-started/installation/)（已安装即可）
- Python 由 uv 自动解析（`requires-python >= 3.11`）

## 快速开始

```bash
# 安装依赖并创建本地虚拟环境
uv sync

# 启动 GUI
uv run python main.py
```

也可以双击 `run.bat`。

## 打包成免安装 exe

```bash
# 或双击 build.bat
uv sync
uv run pyinstaller --noconfirm --clean TinifyCompress.spec
```

完成后得到：

`dist\TinifyCompress.exe`

双击即可运行，无需安装 Python。可单独拷贝该 exe 到其他 Windows 电脑使用。

首次使用：

1. 打开 [tinypng.com/developers](https://tinypng.com/developers) 申请免费 API Key  
2. 在应用顶部填入 Key →「校验」→「保存」  
3. 拖入图片 →「开始压缩」

API Key 保存在：

`%APPDATA%\TinifyCompress\config.json`

## 常用命令

```bash
uv sync                 # 安装 / 更新依赖
uv run python main.py   # 运行
uv add <package>        # 添加依赖
uv remove <package>     # 移除依赖
uv lock                 # 刷新锁文件
```

## 项目结构

```
Tinify-TUI/
├── main.py                 # 入口
├── run.bat                 # 开发时快捷启动
├── build.bat               # 打包 exe
├── TinifyCompress.spec     # PyInstaller 配置
├── pyproject.toml          # uv / 项目元数据
├── uv.lock                 # 锁定依赖版本
├── dist/TinifyCompress.exe # 打包产物（构建后生成）
└── tinify_app/
    ├── config.py           # 本地配置
    ├── compressor.py       # Tinify API 封装
    └── gui.py              # 界面与拖拽
```

## 说明

- 免费额度以 Tinify 账号为准（通常每月 500 次）
- 请勿把 API Key 提交到公开仓库
- 覆盖原文件前会二次确认
