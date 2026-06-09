# ZeroProblems — полная документация

> Быстрый старт: [README.md](README.md)

Веб-платформа для анализа обращений граждан: загрузка Excel → ONNX-классификация тяжести (0–4) → Health Score по муниципалитетам → LLM-справки (Ollama) → карта, дашборд и drilldown по районам.

**Стек:** FastAPI · React (Vite) · ONNX Runtime · Ollama

---

## Содержание

- [Требования](#требования)
- [Подготовка модели](#подготовка-модели)
- [Развёртывание в Docker](#развёртывание-в-docker)
- [Развёртывание без Docker](#развёртывание-без-docker)
- [Переменные окружения](#переменные-окружения)
- [Формат входного Excel](#формат-входного-excel)
- [Демо-режим](#демо-режим)
- [API](#api)
- [Устранение неполадок](#устранение-неполадок)

---

## Требования

| Компонент   | Минимум                   | Рекомендуется                          |
| ----------- | ------------------------- | -------------------------------------- |
| **GPU**     | — (CPU-режим медленный)   | NVIDIA с 8+ ГБ VRAM                    |
| **Python**  | 3.11                      | 3.11                                   |
| **Node.js** | 18+                       | 20+                                    |
| **Ollama**  | для LLM-справок           | `gemma4:e2b`                           |
| **Docker**  | 24+ (для Docker-варианта) | Docker Desktop + GPU (WSL2 на Windows) |

Папки, создаваемые при работе:

```
Hackaton_Backend/
├── fast_rubert/    # ONNX-модель и токенизатор (скачивается отдельно, в git не входит)
├── data/           # загруженные файлы
├── cache/jobs/     # результаты пайплайна
├── dataset/        # тестовые Excel (опционально)
└── frontend/       # React-приложение
```

---

## Подготовка модели

Каталог `fast_rubert/` **не хранится в git** (см. `.gitignore`). Перед первым запуском скачайте файлы модели и положите их в `Hackaton_Backend/fast_rubert/`.

**Ссылка на файлы модели:**  
https://drive.google.com/drive/folders/1rVa7C1k0yA0EOSnfxa1wUmeHsW6RXuMC

(та же ссылка указана в `fast_rubert/put_model_here.txt`)

Ожидаемое содержимое каталога:

```
fast_rubert/
├── model.onnx              # обязательно
├── config.json
├── tokenizer.json
├── tokenizer_config.json
├── special_tokens_map.json
└── label_map.json
```

Без `model.onnx` пайплайн завершится с ошибкой. После скачивания модели **пересобирать Docker-образ API не нужно** — каталог примонтирован как volume (см. ниже), достаточно положить файлы на хост и перезапустить API.

Проверка:

```bash
ls fast_rubert/model.onnx   # файл должен существовать
```

---

## Развёртывание в Docker

Пошаговая инструкция для production-развёртывания на сервере или локально.

### Что поднимается

| Контейнер                  | Назначение                                          |
| -------------------------- | --------------------------------------------------- |
| `zeroproblems-nginx`       | Reverse proxy: `/` → frontend, `/api/` → API, HTTPS |
| `zeroproblems-frontend`    | Собранный React (nginx внутри)                      |
| `zeroproblems-api`         | FastAPI + ONNX-классификация                        |
| `zeroproblems-ollama`      | LLM для справок                                     |
| `zeroproblems-ollama-pull` | Одноразовая загрузка модели Ollama                  |
| `zeroproblems-certbot`     | Автопродление Let's Encrypt                         |

Схема трафика:

```
Браузер → nginx:80/443 → frontend (статика)
                       → api:8000 (/api/, /docs)
API → ollama:11434 (LLM-справки)
```

### Шаг 1. Клонировать репозиторий

```bash
git clone <url-репозитория> Hackaton_Backend
cd Hackaton_Backend
```

### Шаг 2. Скачать ONNX-модель

1. Откройте папку на Google Drive:  
   https://drive.google.com/drive/folders/1rVa7C1k0yA0EOSnfxa1wUmeHsW6RXuMC
2. Скачайте все файлы модели.
3. Положите их в `fast_rubert/` (создайте каталог, если его нет).
4. Убедитесь, что есть `fast_rubert/model.onnx`.

### Шаг 3. Настроить `.env`

```bash
cp .env.example .env
```

Минимум для локального запуска:

```env
OLLAMA_MODEL=gemma4:e2b
ONNX_DEVICE=cuda
ONNX_VARIANT=gpu
```

Для HTTPS на боевом домене дополнительно:

```env
DOMAIN=your.domain.ru
EMAIL=admin@your.domain.ru
CERTBOT_STAGING=0
HTTP_PORT=80
HTTPS_PORT=443
```

Полный список переменных — в [Переменные окружения](#переменные-окружения) и `.env.example`.

### Шаг 4. GPU (рекомендуется)

**Linux / WSL2:**

- [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- Проверка:  
  `docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi`

**Windows:**

- Docker Desktop + [GPU support](https://docs.docker.com/desktop/features/gpu/)
- Актуальный драйвер NVIDIA

**Без GPU** — см. [CPU-режим](#cpu-режим-docker) ниже.

### Шаг 5. Запуск

Из корня `Hackaton_Backend`:

```bash
docker compose up -d --build
```

Первый запуск занимает **10–30 минут**: сборка образов API/frontend, `pip install`, `ollama pull gemma4:e2b`.

Следить за прогрессом:

```bash
docker compose ps
docker compose logs -f api
docker compose logs -f ollama-pull
```

Дождитесь, пока `zeroproblems-api` станет **healthy**.

### Шаг 6. Проверка

| Что         | Команда / URL                                                              |
| ----------- | -------------------------------------------------------------------------- |
| UI          | http://localhost                                                           |
| Swagger     | http://localhost/docs                                                      |
| Health API  | `curl http://localhost/api/v1/health`                                      |
| ONNX на GPU | `docker logs zeroproblems-api 2>&1 \| grep ONNX` → `CUDAExecutionProvider` |
| Ollama      | http://localhost:11434                                                     |

Загрузите `.xlsx` через UI и дождитесь завершения пайплайна.

### HTTPS (Let's Encrypt)

Сертификат выпускает **certbot**, не nginx. Nginx только отдаёт ACME-challenge и после появления сертификата включает SSL.

**Предусловия:**

- A-запись `DOMAIN` → IP сервера
- Порты **80** и **443** открыты снаружи
- В `.env` заданы `DOMAIN` и `EMAIL`

```bash
# стек уже должен быть запущен
docker compose up -d --build

# первый выпуск сертификата
docker compose --profile init-cert run --rm certbot-issue

# nginx подхватит сертификат и включит HTTPS
docker compose restart nginx
```

Проверка: `curl -I https://your.domain.ru`

**Тест без лимитов Let's Encrypt:** `CERTBOT_STAGING=1` в `.env`, те же команды, затем `CERTBOT_STAGING=0` и повторный `certbot-issue` для боевого сертификата.

**Продление:** контейнер `certbot` обновляет сертификат в фоне. После renew при необходимости:

```bash
docker compose exec nginx nginx -s reload
```

### Тома и данные на хосте

| Хост                        | Контейнер          | Назначение                                  |
| --------------------------- | ------------------ | ------------------------------------------- |
| `./fast_rubert`             | `/app/fast_rubert` | ONNX-модель (можно обновить без пересборки) |
| `./data`                    | `/app/data`        | входные файлы                               |
| `./cache`                   | `/app/cache`       | jobs, parquet, отчёты                       |
| `./dataset`                 | `/app/dataset`     | тестовые датасеты                           |
| `zeroproblems-certbot-conf` | `/etc/letsencrypt` | SSL-сертификаты                             |
| `ollama_data`               | `/root/.ollama`    | веса LLM                                    |

### CPU-режим (Docker)

Если GPU нет или не нужен:

```bash
docker compose -f docker-compose.yml -f docker-compose.cpu.yml up -d --build
```

В `.env`: `ONNX_DEVICE=cpu`, `ONNX_VARIANT=cpu`. Классификация будет заметно медленнее на больших файлах.

### Режим разработки API

Правки Python без пересборки образа (bind-mount + `--reload`):

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d ollama ollama-pull api
```

Фронтенд и nginx в этом режиме не поднимаются — UI через `npm run dev` в `frontend/` или полный стек отдельно.

Пересборка образа API нужна только при изменении `Dockerfile` или `requirements-*.txt`.

### Обновление только фронтенда

После правок в `frontend/`:

```bash
docker compose build frontend
docker compose up -d frontend nginx
```

### Полезные команды

```bash
docker compose down              # остановить всё
docker compose up -d --build     # фоновый перезапуск со сборкой
docker compose logs -f api       # логи API
docker compose restart api       # перезапуск API (после смены модели в fast_rubert/)
docker compose ps                # статус контейнеров
```

### Чеклист перед демо / продакшеном

- [ ] `fast_rubert/model.onnx` на месте
- [ ] `docker compose ps` — api **healthy**, nginx **Up**
- [ ] В логах API есть `CUDAExecutionProvider` (или осознанно CPU)
- [ ] Ollama скачала модель (`ollama-pull` завершился)
- [ ] Тестовый `.xlsx` обрабатывается до `completed`
- [ ] (опционально) HTTPS работает на `DOMAIN`

---

## Развёртывание без Docker

### 1. Ollama (LLM-справки)

```bash
# Установка: https://ollama.com
ollama pull gemma4:e2b
ollama serve   # по умолчанию http://localhost:11434
```

Без Ollama пайплайн отработает, но справки будут из шаблонов (`skip_summary=true` отключает LLM полностью).

### 2. Backend (API)

**Windows (PowerShell) с GPU:**

```powershell
cd Hackaton_Backend
python -m venv env
.\env\Scripts\Activate.ps1

pip install -r requirements.txt
# При проблемах с CUDA на Windows:
pip install -r requirements-windows-gpu.txt

$env:PYTHONPATH = "."
$env:OLLAMA_HOST = "http://localhost:11434"
$env:OLLAMA_MODEL = "gemma4:e2b"
# $env:ONNX_DEVICE = "cpu"   # раскомментировать для CPU

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Linux / macOS:**

```bash
cd Hackaton_Backend
python3.11 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
export PYTHONPATH=.
export OLLAMA_HOST=http://localhost:11434
export OLLAMA_MODEL=gemma4:e2b

uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**CPU-only:** установите `onnxruntime` вместо `onnxruntime-gpu`, задайте `ONNX_DEVICE=cpu`. Пакеты `nvidia-*` не нужны.

Проверка:

```bash
curl http://localhost:8000/api/v1/health
```

В логах при первой классификации должно появиться:

```
ONNX inference: requested=[...] active=['CUDAExecutionProvider', ...]
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

| Режим               | URL                       | API                                                                     |
| ------------------- | ------------------------- | ----------------------------------------------------------------------- |
| Dev (`npm run dev`) | http://localhost:5173     | прокси `/api` → `:8000` (см. `vite.config.js`)                          |
| Production build    | `npm run build` → `dist/` | задайте `VITE_API_URL=http://localhost:8000` или раздавайте через nginx |

Preview production-сборки:

```bash
npm run build
npm run preview   # http://localhost:4173
```

### 4. Полный локальный цикл

1. Запустить Ollama (`ollama serve`)
2. Запустить API (`uvicorn …`)
3. Запустить фронт (`npm run dev`)
4. Открыть http://localhost:5173
5. Загрузить `.xlsx` через UI или:

```bash
curl -X POST "http://localhost:8000/api/v1/dataset/upload" \
  -F "file=@dataset/test_300.xlsx"
```

6. Следить за статусом: `GET /api/v1/jobs/{task_id}`
7. После `completed`: дашборд `GET /api/v1/dashboard?task_id=…`

---

## Переменные окружения

Файл `.env` в корне проекта читается `docker compose` автоматически.

| Переменная                 | По умолчанию                   | Описание                                      |
| -------------------------- | ------------------------------ | --------------------------------------------- |
| `DOMAIN`                   | —                              | Домен для HTTPS (Let's Encrypt)               |
| `EMAIL`                    | —                              | Email для Let's Encrypt                       |
| `CERTBOT_STAGING`          | `0`                            | `1` — тестовый сертификат LE                  |
| `HTTP_PORT` / `HTTPS_PORT` | `80` / `443`                   | Порты nginx на хосте                          |
| `OLLAMA_PORT`              | `11434`                        | Порт Ollama на хосте                          |
| `PYTHONPATH`               | `/app` в Docker                | Корень проекта для импортов                   |
| `OLLAMA_HOST`              | `http://ollama:11434` в Docker | URL Ollama                                    |
| `OLLAMA_MODEL`             | `gemma4:e2b`                   | Модель для справок                            |
| `ONNX_DEVICE`              | `cuda`                         | `cpu` — принудительно CPU                     |
| `ONNX_VARIANT`             | `gpu`                          | `cpu` — сборка образа API без GPU wheels      |
| `NVIDIA_VISIBLE_DEVICES`   | `all`                          | Какие GPU видит контейнер                     |
| `EXCEL_ENGINE`             | `auto`                         | `calamine` / `openpyxl` — движок чтения Excel |

Параметры загрузки (query API `/dataset/upload`):

| Параметр        | По умолчанию      | Описание                         |
| --------------- | ----------------- | -------------------------------- |
| `skip_summary`  | `false`           | Пропустить LLM-справки           |
| `batch_size`    | `16`              | Размер батча ONNX                |
| `nrows`         | все строки        | Ограничить число строк (отладка) |
| `model`         | из `OLLAMA_MODEL` | Переопределить модель Ollama     |
| `llm_fast_mode` | `true`            | Укороченные промпты              |

---

## Формат входного Excel

Поддерживаются три раскладки колонок (автоопределение):

1. **Хакатон / train.xlsx** — T=группа, U=тема, V=регион, W=муниципалитет, AI=текст
2. **Выгрузка мониторинга** — даты в T,U; W=МО; AC=тема; AI=текст
3. **Legacy** — T,U даты; V группа; W тема; Y МО; AI текст

Также принимаются файлы с именованными колонками (`Группа тем`, `Тема`, `Текст инцидента`, `Дата создания`, `муниципалитет`).

Муниципалитет обязателен для расчёта Health Score и отображения на карте.

---

## Демо-режим

Фронтенд может работать без живого API, используя снимок `frontend/src/data/demoSnapshot.json`.

Собрать снимок из последнего завершённого job:

```powershell
$env:PYTHONPATH = "."
.\env\Scripts\python.exe scripts/build_demo_snapshot.py --latest
```

Другие варианты:

```bash
python scripts/build_demo_snapshot.py                    # самый полный report (max МО)
python scripts/build_demo_snapshot.py --job a1b2c3d4     # конкретный job
python scripts/build_demo_snapshot.py --report cache/jobs/.../output/report.json
```

После пайплайна снимок обновляется автоматически, если `update_demo_snapshot=True` в настройках (по умолчанию включено).

---

## API

Префикс: `/api/v1`

| Метод  | Путь                         | Описание                         |
| ------ | ---------------------------- | -------------------------------- |
| `GET`  | `/health`                    | Проверка API                     |
| `POST` | `/dataset/upload`            | Загрузка Excel, запуск пайплайна |
| `GET`  | `/jobs`                      | Список задач                     |
| `GET`  | `/jobs/{id}`                 | Статус и шаги пайплайна          |
| `GET`  | `/dashboard`                 | Данные для главной страницы      |
| `GET`  | `/districts/{id}/report`     | Drilldown по муниципалитету      |
| `GET`  | `/districts/{id}/report.pdf` | PDF-отчёт по муниципалитету      |
| `POST` | `/reports/district/pdf`      | PDF по JSON (demo-режим)         |
| `POST` | `/reports/generate`          | LLM-отчёт по району              |
| `GET`  | `/jobs/{id}/summary/briefs`  | Markdown-справки Top-3/Top-10    |

Полная схема: http://localhost:8000/docs

### Health Score (скор на карте)

Для каждого МО:

1. Классы ONNX 0–4 получают веса: `0→0, 1→1, 2→5, 3→20, 4→100`
2. `rating_score = Σвесов / ln(1 + N)` — нормировка на объём обращений
3. `score = 5 + 95 × ln(1 + rating) / ln(1 + max_rating)`, в диапазоне **5–100**

**Чем выше скор — тем больше проблем.** 5 — минимум, 100 — худший МО в выборке.

---

## Устранение неполадок

### ONNX: `CUDAExecutionProvider` не активен

- Проверьте драйвер NVIDIA и `nvidia-smi`
- Windows: `pip install -r requirements-windows-gpu.txt`
- Временно: `$env:ONNX_DEVICE = "cpu"`

### Ollama 404 / пустые справки

- Убедитесь, что Ollama запущен: `curl http://localhost:11434/api/tags`
- Модель скачана: `ollama pull gemma4:e2b`
- `OLLAMA_HOST` указывает на правильный хост (в Docker: `http://ollama:11434`)

### Карта: «нет данных» для района

- В Excel нет обращений с этим муниципалитетом
- Название МО не совпадает с GeoJSON (нормализация имён в `frontend/src/utils/matchDistrict.js`)

### `model.onnx` не найден

Скачайте файлы с Google Drive и положите в `fast_rubert/` (см. [Подготовка модели](#подготовка-модели)):

https://drive.google.com/drive/folders/1rVa7C1k0yA0EOSnfxa1wUmeHsW6RXuMC

Затем `docker compose restart api`.

### Docker: долгая первая сборка

Нормально из-за `pip install` тяжёлых ML-зависимостей и `ollama pull`. Повторные запуски быстрее.

### Порт занят

Измените маппинг в `docker-compose.yml` (`8080:80`, `8000:8000`) или порты uvicorn/vite.

---

## Структура проекта

```
app/           # пайплайн, агрегация, отчёты, LLM
pipeline/      # ONNX-инференс
src/           # FastAPI (main.py, jobs.py)
schemas.py     # Pydantic-модели API
frontend/      # React + Vite + Leaflet
scripts/       # build_demo_snapshot.py и утилиты
```

---

## Лицензия

Проект хакатона. Уточните лицензию у команды перед публичным распространением.
