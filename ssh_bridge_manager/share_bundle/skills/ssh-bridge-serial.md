# Skill: 串口板卡控制

BASE=`http://HOST:18071`，board=板名。

```bash
curl -s "$BASE/status?board=$BOARD"
curl -s -X POST -H 'Content-Type: application/json' -d "{\"board\":\"$BOARD\"}" $BASE/log/clear
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"board\":\"$BOARD\",\"command\":\"uname -a\",\"timeout\":5}" $BASE/command_block
curl -s "$BASE/log?board=$BOARD&lines=100"
curl -s -X POST -H 'Content-Type: application/json' -d "{\"board\":\"$BOARD\",\"id\":\"reboot\"}" $BASE/action
curl -s -X POST -H 'Content-Type: application/json' \
  -d "{\"board\":\"$BOARD\",\"char\":\" \",\"duration\":8,\"interval\":0.05}" $BASE/send_keys
```
