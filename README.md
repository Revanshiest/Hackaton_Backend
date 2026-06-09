# ZeroProblems (Hackaton_Backend)

Бэкенд + фронтенд для анализа обращений граждан.

## Docker (единый стек)

Требуется **NVIDIA GPU** (протестировано на RTX 3060): драйвер, [Docker Desktop GPU support](https://docs.docker.com/desktop/features/gpu/) (WSL2).

```bash
docker compose up --build
```

ONNX и Ollama используют GPU. Проверка после старта:

```bash
docker logs zeroproblems-api 2>&1 | findstr ONNX
docker logs zeroproblems-ollama 2>&1 | findstr inference
```

В логах API должно быть `CUDAExecutionProvider`, у Ollama — `total_vram` > 0.

| Сервис   | URL                    |
|----------|------------------------|
| Frontend | http://localhost:8080  |
| API      | http://localhost:8000  |
| Swagger  | http://localhost:8000/docs |
| Ollama   | http://localhost:11434 |

## Локальная разработка

**API:**
```bash
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Фронт: http://localhost:5173 — прокси `/api` → `:8000`.

## API

Префикс: `/api/v1` — загрузка Excel, статус задачи, дашборд, отчёты по районам.
