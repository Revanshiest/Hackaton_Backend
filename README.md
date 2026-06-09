# ZeroProblems

Excel → ONNX-классификация → дашборд и карта по муниципалитетам Омской области.

**Полная документация:** [README.full.md](README.full.md)

---

## Быстрый старт (Docker)

### 1. Модель

Скачайте файлы с [Google Drive](https://drive.google.com/drive/folders/1rVa7C1k0yA0EOSnfxa1wUmeHsW6RXuMC) → положите в `fast_rubert/` (нужен минимум `model.onnx`).

### 2. Конфиг

```bash
cp .env.example .env
```

### 3. Запуск

```bash
docker compose up -d --build
```

Открыть: **http://localhost** · Swagger: **http://localhost/docs**

Первый старт ~10–30 мин (сборка + `ollama pull`).

### 4. HTTPS (опционально)

В `.env`: `DOMAIN` и `EMAIL`. DNS → IP сервера, порты 80/443 открыты.

```bash
docker compose --profile init-cert run --rm certbot-issue
docker compose restart nginx
```

---

## Без GPU

```bash
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
```

В `.env`: `ONNX_DEVICE=cpu`, `ONNX_VARIANT=cpu`.

---

## Полезные команды

```bash
docker compose ps
docker compose logs -f api
docker compose restart api          # после смены модели в fast_rubert/
docker compose build frontend && docker compose up -d frontend nginx
docker compose down
```

---

## Требования

- Docker 24+
- NVIDIA GPU + [Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (или CPU-режим выше)
- Windows: Docker Desktop с GPU
