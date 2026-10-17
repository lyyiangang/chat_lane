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

需要 Python 3.10 或更高版本。

```bash
cd /home/lyy/code/chat_lan
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

服务默认监听所有网卡的 `8000` 端口。也可以使用环境变量修改地址和端口：

```bash
HOST=0.0.0.0 PORT=8080 python app.py
```

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
source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

健康检查：

```bash
curl http://127.0.0.1:8000/healthz
```

## 使用范围与安全说明

本项目面向受信任的局域网，没有账号、权限和消息加密。不要在不可信网络中运行，也不要通过此页面发送密码、Token 等敏感信息。

不同网络下的设备不能仅靠本服务直接互访。需要额外配置 VPN、组网工具或安全的公网入口。
