# 简易视频播放器 🎬

一个基于 Python 和 PyQt5 构建的现代化、可扩展的视频播放器应用程序。

## ✨ 功能特性

- **多后端支持**：VLC、MPV、Qt 多媒体（自动选择）
- **清晰的架构**：模块化设计，关注点分离
- **高度可扩展**：轻松添加新功能和后端
- **跨平台支持**：适用于 Linux (Ubuntu 22.04+)、Windows、macOS
- **键盘快捷键**：完整的键盘控制支持
- **配置管理**：持久化设置和最近文件记录

## 📁 项目结构

```
vvv/
├── src/                      # 源代码目录
│   ├── __init__.py          # 包初始化文件
│   ├── main.py              # 应用程序入口
│   ├── core/                # 核心播放器后端
│   │   ├── __init__.py
│   │   ├── player_base.py   # 抽象基类定义
│   │   ├── vlc_player.py    # VLC 后端实现
│   │   ├── mpv_player.py    # MPV 后端实现
│   │   └── qt_player.py     # Qt 多媒体后端实现
│   ├── ui/                  # 用户界面组件
│   │   ├── __init__.py
│   │   ├── main_window.py   # 主应用窗口
│   │   ├── video_widget.py  # 视频显示组件
│   │   └── controls/
│   │       ├── __init__.py
│   │       └── control_bar.py  # 播放控制栏
│   ├── config/              # 配置管理
│   │   ├── __init__.py
│   │   └── settings.py      # 设置管理器
│   └── utils/               # 工具函数
│       ├── __init__.py
│       ├── time_utils.py    # 时间格式化工具
│       └── file_utils.py    # 文件操作工具
├── run.py                   # 启动脚本
├── setup.py                 # 安装脚本
├── requirements.txt         # Python 依赖列表
└── README.md               # 本文档
```

## 🚀 快速开始

### 前置要求

**Ubuntu 22.04 系统：**

```bash
# 方案1：安装 VLC（推荐 - 最稳定）
sudo apt update
sudo apt install python3-pyqt5 vlc python3-vlc

# 方案2：安装 MPV
sudo apt install python3-pyqt5 mpv

# 方案3：仅使用 Qt（可能存在兼容性问题）
sudo apt install python3-pyqt5 python3-pyqt5.qtmultimedia gstreamer1.0-plugins*
```

### 运行应用程序

```bash
cd ~/vvv

# 方法1：使用启动脚本（推荐）
python3 run.py

# 方法2：直接运行主程序
python3 src/main.py
```

## 🎮 使用说明

### 键盘快捷键

| 按键 | 功能 |
|------|------|
| `空格` | 播放/暂停 |
| `F` | 切换全屏模式 |
| `ESC` | 退出全屏 |
| `←` / `→` | 后退/前进 5 秒 |
| `↑` / `↓` | 音量增加/减少 10% |

### 主要功能

1. **打开视频**：点击"Open"按钮或使用文件对话框选择视频文件
2. **播放控制**：播放、暂停、停止按钮
3. **进度控制**：拖动进度条或使用方向键调整播放位置
4. **音量调节**：通过音量滑块或上下方向键调整音量
5. **全屏模式**：按 F 键或双击视频区域切换全屏

## 🔧 架构设计

### 设计模式

- **策略模式（Strategy Pattern）**：多个播放器后端（VLC/MPV/Qt）共享统一接口
- **观察者模式（Observer Pattern）**：信号槽机制实现 UI 更新通知
- **单例模式（Singleton Pattern）**：配置管理器提供全局设置访问
- **MVC 分离架构**：核心逻辑与 UI 层完全分离

### 核心组件

1. **PlayerBackend（抽象基类）**：定义所有媒体播放器的统一接口规范
2. **具体后端实现**：VLCPlayer、MPVPlayer、QtPlayer 的具体实现
3. **MainWindow**：应用主窗口和事件处理中心
4. **ControlBar**：播放控制和状态显示组件
5. **Config**：持久化配置管理系统

## 🔌 扩展播放器功能

### 添加新的播放后端

1. 在 `src/core/` 目录下创建新类，继承 `PlayerBackend`
2. 实现所有抽象方法
3. 在 `src/main.py` 的 `create_backend()` 函数中注册

示例代码：

```python
from src.core.player_base import PlayerBackend, PlayerState

class CustomPlayer(PlayerBackend):
    @staticmethod
    def is_available() -> bool:
        return True
    
    @staticmethod
    def get_backend_name() -> str:
        return "Custom"
    
    def load(self, file_path: str) -> bool:
        pass
    
    def play(self) -> None:
        pass
    
    # ... 实现其他抽象方法
```

### 添加新功能特性

模块化架构使添加新功能变得非常简单：
- 播放列表管理 (`src/ui/playlist.py`)
- 字幕支持 (`src/core/subtitles.py`)
- 音频均衡器 (`src/ui/equalizer.py`)
- 视频滤镜/特效 (`src/video/filters.py`)
- 网络流媒体支持 (`src/network/streaming.py`)

## ⚙️ 配置说明

配置文件存储在 `~/.config/simple-video-player/config.json`

默认配置项包括：
- 窗口大小和位置
- 默认音量级别
- 首选播放后端
- 最近打开的文件列表

## 🧪 测试

```bash
# 运行测试
pytest tests/

# 运行测试并生成覆盖率报告
pytest --cov=src tests/
```

## 📦 构建发布包

```bash
# 创建源码分发包
python3 setup.py sdist

# 创建 wheel 安装包
python3 setup.py bdist_wheel

# 以开发模式安装
pip install -e .
```

## 🛠️ 开发环境搭建

```bash
# 克隆代码仓库
git clone <仓库地址>
cd vvv

# 创建虚拟环境
python3 -m venv venv
source venv/bin/activate  # Windows 系统: venv\Scripts\activate

# 安装依赖包
pip install -r requirements.txt

# 启动应用
python3 run.py
```

## 📋 开发路线图

- [ ] 播放列表管理功能
- [ ] 字幕支持（.srt, .ass 格式）
- [ ] 音轨选择功能
- [ ] 视频播放速度控制
- [ ] 视频截图功能
- [ ] 网络流媒体支持（HTTP, RTSP）
- [ ] 视频录制功能
- [ ] 插件系统开发
- [ ] 深色/浅色主题切换
- [ ] 国际化多语言支持（i18n）

## 🤝 贡献指南

1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'Add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 提交 Pull Request

## 📄 许可证

本项目采用 MIT 许可证开源 - 详情请查看 LICENSE 文件。

## 🙏 致谢

- [PyQt5](https://www.riverbankcomputing.com/software/pyqt/) - GUI 框架
- [VLC](https://www.videolan.org/vlc/) - 多媒体框架
- [MPV](https://mpv.io/) - 媒体播放器
- [Python](https://www.python.org/) - 编程语言

---

**采用专业软件工程实践构建 ❤️**
