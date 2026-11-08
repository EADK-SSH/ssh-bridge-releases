# Skill: 继电器上下电 / 重启

```bash
curl -s "$BASE/actions?board=$BOARD"
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"board\":\"$BOARD\",\"id\":\"power_on\"}" $BASE/action
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"board\":\"$BOARD\",\"id\":\"power_off\"}" $BASE/action
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"board\":\"$BOARD\",\"id\":\"reboot\"}" $BASE/action
```
抢 U-Boot：reboot 后立刻 `send_keys` 空格 `duration≈8~10 interval=0.05`。
