# SSH Bridge Manager — Windows binaries (`x86_64`)

**Branch: `windows_x86_64`.** Binary downloads only. Source is private.

| Tool | Path |
|------|------|
| Manager + desktop shell | [`ssh_bridge_manager/`](./ssh_bridge_manager/) |
| LAN discovery WebView | [`windows_manager/`](./windows_manager/) |

## Get the binaries

### Option A — GitHub Releases (zip)

→ [Releases](https://github.com/EADK-SSH/ssh-bridge-releases/releases)

- `ssh_bridge_manager-windows-x86_64-<VERSION>.zip`（及无 arch 的兼容名）
- 本分支根目录 [`UPDATE.json`](./UPDATE.json) 供自升级读取

### Option B — git clone this branch

```bash
git clone -b windows_x86_64 https://github.com/EADK-SSH/ssh-bridge-releases.git
cd ssh-bridge-releases/ssh_bridge_manager
```

Run `run.bat` / `ssh_bridge_manager.exe`, or `../windows_manager/windows_manager.exe` for LAN discovery.

Latest build on this branch: **`20261111-050427`** (valid ~180 days from compile).

Contact: yanggan2015@foxmail.com
