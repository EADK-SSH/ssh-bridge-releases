# Skill: 板控 / 继电器 / 本机脚本

```bash
curl -s "http://HOST:18071/actions?board=BOARD"
curl -s -X POST -H 'Content-Type: application/json' -d '{"board":"BOARD","id":"reboot"}' http://HOST:18071/action
curl -s -X POST -H 'Content-Type: application/json' -d '{"board":"BOARD","id":"host_echo"}' http://HOST:18071/action
```
WebUI 点击会弹窗显示本机脚本输出，成功约 2.5s 自动关闭。
