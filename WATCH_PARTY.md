# 同步观影聊天室

## 安装

Ubuntu 系统依赖：

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip python3-cairo \
  python3-gi python3-gi-cairo gir1.2-gtk-3.0 mpv \
  mpv-common ffmpeg pkg-config build-essential
```

再安装当前 Ubuntu 版本提供的 libmpv 动态库：

```bash
if apt-cache show libmpv2 >/dev/null 2>&1; then
  sudo apt install -y libmpv2
else
  sudo apt install -y libmpv1
fi
sudo ldconfig
```

Ubuntu 20.04 等旧版本通常提供 `libmpv1`，较新版本通常提供 `libmpv2`。
可以用下面的命令确认 Python 能否找到动态库：

```bash
python3 -c "import ctypes.util; print(ctypes.util.find_library('mpv'))"
```

正常结果类似 `libmpv.so.1` 或 `libmpv.so.2`，不应为 `None`。

如果系统是 Python 3.8 且 libmpv API 为 `1.107`（mpv 0.32），需要使用
与该系统版本兼容的 `python-mpv 0.5.2`：

```bash
python3 -m pip uninstall -y python-mpv mpv
python3 -m pip install --no-cache-dir "python-mpv==0.5.2"
```

不要通过修改 `mpv.py` 跳过 API 版本检查；新版封装可能调用旧动态库没有的符号。
当前 `requirements.txt` 已按 Python 版本自动选择兼容版本。

播放器客户端依赖：

```bash
python3 -m venv --system-site-packages linuxplayer
source linuxplayer/bin/activate
pip install -r requirements.txt
```

只在运行房间服务的机器上安装：

```bash
pip install -r requirements-chat-server.txt
```

这里使用基础版 `uvicorn`，不安装 `uvicorn[standard]`。后者会额外引入
`uvloop`、`watchfiles` 等原生扩展；在旧版 Python 或部分 ARM Linux 环境中，
它们可能退回源码构建并尝试下载 Rust 构建后端 `puccinialin`。
WebSocket 支持通过独立的 `websockets` 包提供；Python 3.8 使用的最高兼容版本
为 `13.1`。

AI 字幕服务是可选功能，其依赖单独放在
`requirements-whisper-server.txt` 中。

### pip 代理连接失败

如果出现 `ProxyError: Cannot connect to proxy`，说明当前 shell 或 pip
配置了不可用的代理。先查看代理来源：

```bash
env | grep -i proxy
python3 -m pip config list -v
```

当前终端不需要代理时，可临时清除后安装：

```bash
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy
python3 -m pip install -r requirements.txt
```

如果代理写在 pip 配置中，可删除对应配置：

```bash
python3 -m pip config unset global.proxy
```

如果机器必须通过代理联网，需要将代理地址改为实际可访问的地址，而不是直接
清除。`No matching distribution found` 在这种情况下只是网络连接失败的后续提示，
并不代表 `python-mpv` 不存在。

## 启动

先在一台所有用户都能访问的电脑上启动房间服务：

```bash
python3 chat_server.py
```

默认监听 `0.0.0.0:8765`。公网部署时需要在防火墙放行该端口，建议通过
Nginx/Caddy 配置 TLS，并让客户端使用 `wss://` 地址。

然后启动播放器：

```bash
python3 linux_video_player.py
```

房主点击“影院房间”并创建房间，将 6 位邀请码发给其他用户。其他用户选择
“加入房间”，填写相同的服务器地址和邀请码。

房主打开视频后，播放器会在房主机器的 `8766` 端口启动视频流。房间成员会
自动加载该视频流，不需要持有或打开本地视频文件。虚拟机或防火墙环境需要同时
放行房间服务和视频流端口：

```bash
sudo ufw allow 8765/tcp
sudo ufw allow 8766/tcp
```

如房主有多个虚拟网卡，自动选择的流地址可能不是其他成员能访问的网卡地址。
此时在启动房主播放器前明确指定可访问的 IP：

```bash
export WATCH_PARTY_STREAM_HOST=192.168.1.100
python3 linux_video_player.py
```

流端口也可通过 `WATCH_PARTY_STREAM_PORT` 修改，但所有成员必须能访问该端口。

## 虚拟机网络

运行在不同虚拟机中的客户端不能使用 `ws://127.0.0.1:8765` 互相连接，
因为该地址始终指向当前虚拟机自身。

推荐将两台虚拟机的网卡都设置为“桥接网卡”，或者让它们都加入同一个
Host-only/Internal Network。两台虚拟机必须能通过各自的虚拟网卡 IP 互相访问。

在运行房间服务的虚拟机中查看 IP：

```bash
hostname -I
ss -lntp | grep 8765
```

在另一台虚拟机中测试服务，其中 `192.168.1.100` 替换为服务端虚拟机 IP：

```bash
ping -c 3 192.168.1.100
curl http://192.168.1.100:8765/health
nc -vz 192.168.1.100 8766
```

`curl` 正常时会返回包含 `"status":"ok"` 的 JSON。加入房间时填写：

```text
ws://192.168.1.100:8765
```

如果 ping 成功但 curl 失败，检查服务端防火墙：

```bash
sudo ufw allow 8765/tcp
sudo ufw status
```

## 使用限制

- 视频文件不会上传到聊天室服务器，而是由房主播放器通过 HTTP 直接流式发送
  给成员。房主上行带宽会随观看人数增加。
- 成员无需本地视频文件，但必须能通过网络访问房主的流地址和端口。
- 播放、暂停和进度由房主同步；音量、字幕、画面比例仍由每位用户独立控制。
- 聊天消息显示在右侧对话框；启用弹幕后也会通过 mpv OSD 显示在视频上。
