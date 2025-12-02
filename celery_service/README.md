Got it — here is a clean **README section** you can copy-paste into your README.md for **starting & stopping Celery with Docker** ✅

---

## 🐳 Docker – Start / Stop Celery

Run all commands from:

```
backend/celery_service/
```

### ▶️ Start Celery + Redis

```sh
docker compose up
```

### ▶️ Start in background (detached mode)

```sh
docker compose up -d
```

### 🔁 Rebuild and start (use when code changes)

```sh
docker compose up --build
```

### ⛔ Stop Celery + Redis

```sh
docker compose down
```

### 🔄 Restart Celery

```sh
docker compose down
docker compose up --build
```

---
### 🔄 Stop container and  remove all images

```sh
docker compose down --remove-orphans
```

---

## 📌 Useful Docker Commands

| Action                             | Command                                                              |
| ---------------------------------- | -------------------------------------------------------------------- |
| View container logs                | `docker compose logs -f celery`                                      |
| Open shell inside Celery container | `docker exec -it celery_service_celery_1 bash`                       |
| Check if DB file is mounted        | `docker exec -it celery_service_celery_1 ls -l /app/conversation_db` |
| Remove unused docker cache         | `docker system prune -af`                                            |

---

# Redis
---
### 🔄 Start Redis Cli

```sh
docker exec -it celery_service_redis_1 redis-cli
```

