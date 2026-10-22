# 局域网聊天室

在同一 Wi-Fi / 局域网下，Ubuntu 电脑启动服务后，电脑和手机直接打开网址即可互相发送消息。不需要安装 App，也不需要账号。

## 功能

- 浏览器之间通过 WebSocket 实时收发文字消息
- 显示发送者、发送时间，并支持一键复制消息
- 手机和电脑响应式界面
- 断线自动重连
- 内存中保留最近 100 条消息，刷新页面后可恢复
- 无数据库，服务重启后聊天记录会清空

## 启动

需要 Python 3.10 或更高版本。项目使用 [uv](https://docs.astral.sh/uv/) 管理环境和依赖：`uv sync` 会根据 `pyproject.toml` 和 `uv.lock` 创建 `.venv` 并安装依赖，缺少合适的 Python 版本时会自动下载。

```bash
cd /path/to/chat_lane
uv sync
uv run python app.py
```

如果还没有安装 uv：

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

服务默认监听所有网卡的 `8000` 端口；如果该端口已被占用，会自动顺延到下一个可用端口，并打印实际使用的端口。也可以用环境变量修改地址和起始端口：

```bash
HOST=0.0.0.0 PORT=8080 uv run python app.py
```

启动时会打印实际使用的访问地址，例如 `访问地址: http://192.168.1.100:8000`，手机直接打开该地址即可。

## 手机访问

先查看 Ubuntu 电脑的局域网 IP：

```bash
hostname -I
```

假设输出中 Wi-Fi 地址是 `192.168.1.100`，手机浏览器打开：

```text
http://192.168.1.100:8000
```

电脑也打开相同地址，双方就可以聊天。手机和电脑必须连接同一个局域网。

如果 Ubuntu 开启了 UFW 防火墙，需要放行端口：

```bash
sudo ufw allow 8000/tcp
```

## Ubuntu 后台运行

服务直接使用项目内的 `.venv/bin/uvicorn`，所以安装服务前先在项目目录执行一次 `uv sync`。

复制 `deploy/chat-lan.service.example`，将其中两处路径和 `YOUR_USER` 改成实际值：

```bash
sudo cp deploy/chat-lan.service.example /etc/systemd/system/chat-lan.service
sudo nano /etc/systemd/system/chat-lan.service
sudo systemctl daemon-reload
sudo systemctl enable --now chat-lan
```

查看状态和日志：

```bash
sudo systemctl status chat-lan
sudo journalctl -u chat-lan -f
```

修改代码后重启服务：

```bash
sudo systemctl restart chat-lan
```

如果不需要系统级服务，也可以把项目自带的用户级服务安装到当前用户：

```bash
install -Dm644 deploy/chat-lan-user.service ~/.config/systemd/user/chat-lan.service
systemctl --user daemon-reload
systemctl --user enable --now chat-lan
```

用户级服务的常用命令：

```bash
systemctl --user status chat-lan
journalctl --user -u chat-lan -f
systemctl --user restart chat-lan
```

如果希望计算机重启后、用户未登录桌面时也自动启动，需要由管理员为当前用户开启 lingering：

```bash
sudo loginctl enable-linger "$USER"
```

## 开发与测试

```bash
uv sync
uv run pytest
```

添加依赖时使用 uv 更新 `pyproject.toml` 和 `uv.lock`：

```bash
uv add 包名
uv add --dev 包名
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## 使用范围与安全说明

本项目面向受信任的局域网，没有账号、权限和消息加密。不要在不可信网络中运行，也不要通过此页面发送密码、Token 等敏感信息。

不同网络下的设备不能仅靠本服务直接互访。需要额外配置 VPN、组网工具或安全的公网入口。
