# Skill: ok3562 进 U-Boot + TFTP 内核/ramdisk

1. `reboot` action + 空格抢 U-Boot（见串口 skill）
2. 配网并 `ping 192.168.137.1`
3. U-Boot 几乎只认文件名 `Image`：主机依次把文件覆盖为 `share/Image` 再 tftp

```
tftp 0x20000000 Image          # imgpart00 = 16777216
tftp 0x21000000 Image          # imgpart01
tftp 0x0a200000 Image          # rootfs.cpio.gz，记录 Bytes
tftp 0x1f000000 Image          # noesis-rk3562-v8.dtb
# 要交互 shell（推荐烧写）：
setenv bootargs console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000 rdinit=/bin/sh
# 或完整 init（getty 可能在错误 tty）：
# setenv bootargs console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000 root=/dev/ram0 rw init=/sbin/init
booti 0x20000000 0x0a200000:SIZE 0x1f000000
```

SIZE 用 TFTP 打印的 hex（例 `12e235a`）。见 `ok3562-ramdisk-shell.md`。
