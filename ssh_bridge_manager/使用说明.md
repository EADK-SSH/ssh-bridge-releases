# EADK SSH Bridge（EADK SSH 桥）使用说明

Windows 便携版。本包不含源码。

- 下载：https://github.com/EADK-SSH/ssh-bridge-releases/releases
- 联系：yanggan2015@foxmail.com

---

## 1. 程序做什么

| 类型 | 配置段 | 作用 |
|------|--------|------|
| 串口桥 | `boards` | 本机串口 ↔ 入站 SSH（约 2200–2299）↔ Web/HTTP |
| SSH Link | `ssh` | 连远端 SSH ↔ 本机入站 SSH（约 2300–2399）↔ Web/HTTP |

---

## 2. 目录与入口

| 文件 | 说明 |
|------|------|
| `ssh_bridge_desktop.exe` | **推荐入口**：系统托盘 + 默认浏览器打开 WebUI；自动拉起无窗口后端 |
| `ssh_bridge_manager.exe` | 无 UI 后端（由桌面壳或脚本启动；`CREATE_NO_WINDOW`） |
| `run.bat` | 启动 `ssh_bridge_manager.exe` |
| `*.dll` | manager 运行时依赖 |
| `WebView2Loader.dll` | 仅 `windows_manager`（局域网发现 GUI）需要 |
| `README.md` / `使用说明.md` | 说明文档 |

---

## 3. 快速开始

1. 解压 zip。  
2. 仅后端：`run.bat` / `ssh_bridge_manager.exe`。  
3. 托盘入口：`ssh_bridge_desktop.exe`；启动后打开浏览器，托盘可开网页/开机自启/退出。

```bat
run.bat
ssh_bridge_manager.exe -c %USERPROFILE%\.ssh-bridge\ssh_bridge_config.json
```

桌面壳参数：

```bat
ssh_bridge_desktop.exe
ssh_bridge_desktop.exe --ui-only --http-port 18081
ssh_bridge_desktop.exe --no-tray
ssh_bridge_desktop.exe --smoke-test
```

---

## 4. 配置查找

1. 当前目录 `ssh_bridge_config.json`  
2. `%USERPROFILE%\.ssh-bridge\ssh_bridge_config.json`  
3. 遗留 `config.json`  

`ssh_bridge_manager.exe which-config` 可查看实际路径。

增删板卡为手术式热更新（HTTP 不断）；详见运行中 `/help`。

---

## 5. 托盘（desktop）

| 菜单 | 行为 |
|------|------|
| 打开网页 / 主界面 / 管理器 / Agent 接口 | 打开对应入口 |
| 反馈 Issues / 邮件联系作者 | 提建议或联系（Issues 需登录 GitHub） |
| 开机自启 | `HKCU\...\Run`，值名 `EADK SSH Bridge` |
| 退出 | 结束 desktop 与其拉起的 manager |

---

## 6. HTTP 速查

```bat
curl http://127.0.0.1:18081/status
curl -H "Content-Type: application/json" -d "{\"board\":\"my-board\",\"timestamp\":true,\"persist\":true}" http://127.0.0.1:18081/channel/configure
```

完整 curl 以 `/help` 为准。

---

## 7. 常见问题

**端口占用**：结束多余 `ssh_bridge_manager` / `ssh_bridge_desktop`。  
**无窗口**：看托盘是否已隐藏。  
**串口失败**：COM 号、占用、波特率。  
**发同事**：发整个目录，不要带含密码的真实配置。
