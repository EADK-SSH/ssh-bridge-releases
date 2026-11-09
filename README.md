# SSH Bridge Manager — Releases

**Binary downloads only.** Source is private.

Git trees are on **`{os}_{arch}`** branches (see private repo `DESIGN.md` §11.4):

| Branch | Contents |
|--------|----------|
| [`windows_x86_64`](https://github.com/EADK-SSH/ssh-bridge-releases/tree/windows_x86_64) | `ssh_bridge_manager/` + `windows_manager/` |
| [`linux_x86_64`](https://github.com/EADK-SSH/ssh-bridge-releases/tree/linux_x86_64) | `ssh_bridge_manager/` |
| [`linux_aarch64`](https://github.com/EADK-SSH/ssh-bridge-releases/tree/linux_aarch64) | `ssh_bridge_manager/` (when built) |

## Clone

```bash
git clone -b windows_x86_64 https://github.com/EADK-SSH/ssh-bridge-releases.git
# or: git clone -b linux_x86_64 https://github.com/EADK-SSH/ssh-bridge-releases.git
```

## Zip downloads

→ [Releases](https://github.com/EADK-SSH/ssh-bridge-releases/releases)

- `ssh_bridge_manager-windows-x86_64-<VERSION>.zip`
- `ssh_bridge_manager-linux-x86_64-<VERSION>.zip` / `...-linux-aarch64-...`
- 每平台分支根目录 `UPDATE.json`（自升级读取）

Contact: yanggan2015@foxmail.com
