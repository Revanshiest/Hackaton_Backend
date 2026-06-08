from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

# --- 1. Загрузка датасета ---

class DatasetUploadResponse(BaseModel):
    """Схема ответа при успешной загрузке датасета"""
    task_id: str = Field(..., description="ID фоновой задачи обработки", example="a1b2c3d4")
    filename: str = Field(..., description="Имя загруженного файла", example="dataset_2023.xlsx")
    message: str = Field(..., description="Статус обработки", example="Датасет успешно загружен и обработан")
    rows_processed: int = Field(..., description="Количество обработанных строк", example=15000)


# --- 2. Дашборд (Главная страница) ---

class DistrictShortInfo(BaseModel):
    """Краткая информация по району (для карты и топа)"""
    district_id: int = Field(..., description="Уникальный идентификатор района", example=1)
    district_name: str = Field(..., description="Название района", example="Центральный АО")
    score: int = Field(..., description="Скор района (от 0 до 100, чем выше, тем лучше)", example=87)
    main_problem: str = Field(..., description="Главная проблема", example="ЖКХ")
    center_coordinates: Optional[List[float]] = Field(None, description="Координаты центра района [широта, долгота]", example=[54.989347, 73.368221])

class ThemeCount(BaseModel):
    """Счетчик инцидентов по теме"""
    theme: str = Field(..., description="Название темы", example="Дороги")
    count: int = Field(..., description="Количество", example=287)

class CriticalDistrictCard(BaseModel):
    """Карточка критического района"""
    district_id: int = Field(..., description="ID района", example=5)
    district_name: str = Field(..., description="Название района", example="Калачинский район")
    criticality_status: str = Field(..., description="Статус критичности (КРИТИЧНЫЙ, ОЧЕНЬ ВЫСОКИЙ и т.д.)", example="КРИТИЧНЫЙ")
    score: int = Field(..., description="Скор района", example=22)
    top_themes: List[ThemeCount] = Field(..., description="Топ проблем с количеством обращений")
    sample_incident_text: str = Field(..., description="Цитата/пример обращения", example="Мост в аварийном состоянии, проезд опасен")
    total_incidents: int = Field(..., description="Всего обращений по району", example=702)

class DashboardResponse(BaseModel):
    """Сводные данные для главной страницы (дашборда)"""
    map_data: List[DistrictShortInfo] = Field(..., description="Данные для карты")
    top_districts: List[DistrictShortInfo] = Field(..., description="Топ-10 районов по скору")
    critical_districts: List[CriticalDistrictCard] = Field(..., description="Карточки критических районов")


# --- 3. Отчёт по району (уже существующий/быстрый) ---

class ThematicGroupStat(BaseModel):
    """Статистика по конкретной тематической группе"""
    group_name: str = Field(..., description="Название тематической группы", example="Транспорт")
    count: int = Field(..., description="Количество обращений", example=345)
    percentage: float = Field(..., description="Процент от общего числа", example=39.0)

class DistrictReport(BaseModel):
    """Подробный отчёт по району"""
    district_id: int = Field(..., description="ID района", example=1)
    district_name: str = Field(..., description="Название района", example="Большеуковский район")
    score: int = Field(..., description="Скор/Индекс района", example=25)
    analytical_summary: str = Field(..., description="Аналитическая сводка (текст)", example="Критически низкий уровень транспортной доступности.")
    total_incidents: int = Field(..., description="Всего инцидентов за период", example=879)
    top_category: str = Field(..., description="Топ-категория (больше всего жалоб)", example="Транспорт")
    categories_count: int = Field(..., description="Количество типов проблем", example=4)
    start_date: Optional[datetime] = Field(None, description="Начало периода")
    end_date: Optional[datetime] = Field(None, description="Конец периода")
    themes_stat: List[ThematicGroupStat] = Field(..., description="Статистика по категориям (для графиков)")
    incident_examples: List[str] = Field(..., description="Примеры обращений", example=["В паводок район полностью отрезан от области.", "Школьники живут в интернате из-за отсутствия транспорта."])

class DistrictReportResponse(BaseModel):
    """Схема ответа при запросе отчёта по району"""
    data: DistrictReport


# --- 4. Создание подробного отчёта по запросу ---

class GenerateReportRequest(BaseModel):
    """Схема запроса на генерацию нового подробного отчёта"""
    district_id: int = Field(..., description="ID района для отчёта", example=1)
    start_date: Optional[datetime] = Field(None, description="Начало периода (опционально)")
    end_date: Optional[datetime] = Field(None, description="Конец периода (опционально)")
    include_raw_data: bool = Field(False, description="Включать ли примеры исходных данных")

class GenerateReportResponse(BaseModel):
    """
    Схема ответа на запрос генерации.
    Так как ML-задачи и генерация отчётов могут быть долгими,
    лучше возвращать ID задачи (Background Task), статус которой фронтенд сможет проверять.
    """
    task_id: str = Field(..., description="ID фоновой задачи генерации отчёта", example="task-12345-abcde")
    status: str = Field(..., description="Текущий статус", example="processing")
    message: str = Field(..., description="Сообщение для пользователя", example="Отчёт генерируется, пожалуйста, подождите.")


# --- 5. Фоновые задачи (пайплайн) ---

class PipelineStep(BaseModel):
    """Шаг обработки датасета"""
    id: str = Field(..., description="Идентификатор шага", example="classify")
    label: str = Field(..., description="Название шага", example="Классификация ONNX")
    status: str = Field(..., description="Статус: pending, running, done, error", example="running")
    detail: str = Field("", description="Детали выполнения")


class JobStatus(BaseModel):
    """Статус фоновой задачи обработки датасета"""
    task_id: str = Field(..., description="ID задачи", example="a1b2c3d4")
    status: str = Field(..., description="queued, running, completed, failed", example="running")
    message: str | None = Field(None, description="Текущее сообщение")
    created_at: str | None = Field(None, description="Время создания (ISO)")
    filename: str | None = Field(None, description="Имя загруженного файла")
    rows_processed: int | None = Field(None, description="Обработано строк")
    stats: dict | None = Field(None, description="Статистика после завершения")
    steps: list[PipelineStep] | None = Field(None, description="Шаги пайплайна")


class PipelineOptions(BaseModel):
    """Параметры запуска пайплайна"""
    skip_summary: bool = Field(False, description="Пропустить LLM-справки")
    batch_size: int = Field(16, description="Размер батча ONNX")
    nrows: int | None = Field(None, description="Ограничить число строк (для теста)")
    model: str | None = Field(None, description="Модель Ollama (по умолчанию gemma4:e2b)")
