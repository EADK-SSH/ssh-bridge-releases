# Skill: Agent 锁

```bash
curl -s -X POST -H 'Content-Type: application/json' -H 'X-Agent-Session: SID' \
  -d '{"board":"BOARD","ttl_ms":3600000}' http://HOST:18071/lock
curl -s -X POST -H 'Content-Type: application/json' -H 'X-Agent-Session: SID' \
  -d '{"board":"BOARD"}' http://HOST:18071/unlock
```
