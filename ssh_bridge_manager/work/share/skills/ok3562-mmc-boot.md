# Skill: ok3562 eMMC 正常启动参数

根分区 `/dev/mmcblk0p8`，PARTUUID=`614e0000-0000`。

U-Boot：
```
setenv bootargs console=ttyFIQ0 earlycon=uart8250,mmio32,0xff210000 root=PARTUUID=614e0000-0000 rw rootwait storagemedia=emmc
setenv bootcmd 'ext4load mmc 0:8 0x20000000 /boot/Image; ext4load mmc 0:8 0x1f000000 /boot/noesis-rk3562-v8.dtb; booti 0x20000000 - 0x1f000000'
saveenv
boot
```
登录：`root` / `Ncti2023`。成功见 `noesis3562 login:`。

烧写后务必确认 `/boot/Image` 与 dtb 存在，否则会出现 `Bad Linux ARM64 Image magic!`。  
若 `saveenv` 报 `Saving Environment to nowhere...`，env 不落盘，仅本次生效。
