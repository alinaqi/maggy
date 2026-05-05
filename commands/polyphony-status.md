# /polyphony-status — Show State

Display the current state of all Polyphony tasks and running containers.

---

## Steps

### 1. Show Task States

```bash
PYTHONPATH=scripts python3 -m polyphony status
```

### 2. Show Running Containers

```bash
docker ps --filter "name=polyphony-" --format "table {{.Names}}\t{{.Status}}\t{{.RunningFor}}"
```

### 3. Show Workspace Usage

```bash
du -sh ~/polyphony/workspaces/* 2>/dev/null || echo "No workspaces"
```
