from contextlib import asynccontextmanager
from pathlib import Path
import sys

from fastapi import FastAPI, APIRouter
from fastapi.middleware.cors import CORSMiddleware

# Настраиваем пути, чтобы можно было импортировать модули из корня
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipeline.inference import run_inference
# Здесь мы в будущем импортируем схемы из schemas.py
# from schemas import ... 

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Здесь можно сделать "прогрев" модели при старте
    print("Бэкенд запущен, ONNX модель готова.")
    yield
    print("Выключение бэкенда...")

app = FastAPI(
    title="Омск Пульс - ML API",
    description="Бэкенд для классификации инцидентов на базе ONNX Runtime",
    version="1.0.0",
    lifespan=lifespan,
)

# Настройка CORS для работы с фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # На проде нужно будет ограничить
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")

@api_router.get("/health", summary="Проверка состояния API")
async def health_check():
    """Возвращает статус сервера."""
    return {"status": "ok", "backend": "onnx", "message": "ML API is running"}

# TODO: Добавить эндпоинты для предсказаний
# @api_router.post("/predict")
# async def predict(...): ...

app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
