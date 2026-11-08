# EADK SSH Bridge（便携包）

本目录为**二进制发行包**（不含源码）。

详细说明：[使用说明.md](使用说明.md)（与 [USAGE.zh-CN.md](USAGE.zh-CN.md) 相同）

## 快速开始

1. 保持本目录完整（两个 exe + 全部 DLL；`WebView2Loader.dll` 仅 `windows_manager` 需要时可忽略）。
2. 仅后端：`run.bat` 或 `ssh_bridge_manager.exe`（控制台，无托盘）
3. 托盘入口：双击 `ssh_bridge_desktop.exe`（拉起无窗口 manager，浏览器打开 WebUI）

## 配置

未传 `-c` 时：

1. 本目录 `ssh_bridge_config.json`
2. `%USERPROFILE%\.ssh-bridge\ssh_bridge_config.json`
3. 本目录遗留 `config.json`

都没有则在用户目录创建空配置。包内仅有 `*.example`。

## Web

默认端口以配置 `http_port` 为准（示例 18081）：

- `http://127.0.0.1:<port>/`
- `http://127.0.0.1:<port>/help`

## 许可

自编译起约 180 天 API 可用。见 `VERSION.txt`。  
https://github.com/EADK-SSH/ssh-bridge-releases/releases  
yanggan2015@foxmail.com
