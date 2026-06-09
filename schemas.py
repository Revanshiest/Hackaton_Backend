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
    score: int = Field(..., description="Индекс проблемности (5–100, чем выше — тем больше проблем)", example=87)
    main_problem: str = Field(..., description="Главная проблема", example="ЖКХ")
    analytical_summary: Optional[str] = Field(None, description="Аналитический вывод по МО")
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
    analytical_summary: Optional[str] = Field(None, description="Развёрнутый аналитический вывод по критическому МО")
    total_incidents: int = Field(..., description="Всего обращений по району", example=702)

class DashboardResponse(BaseModel):
    """Сводные данные для главной страницы (дашборда)"""
    map_data: List[DistrictShortInfo] = Field(..., description="Данные для карты")
    top_districts: List[DistrictShortInfo] = Field(..., description="Топ-10 районов по скору")
    critical_districts: List[CriticalDistrictCard] = Field(..., description="Карточки критических районов")
    start_date: Optional[datetime] = Field(None, description="Начало периода обращений в датасете")
    end_date: Optional[datetime] = Field(None, description="Конец периода обращений в датасете")
    total_incidents: Optional[int] = Field(None, description="Всего обращений в выборке", example=15000)
    problem_count: Optional[int] = Field(None, description="Проблемных обращений (severity > 0)", example=12000)


# --- 3. Отчёт по району (уже существующий/быстрый) ---

class ThematicGroupStat(BaseModel):
    """Статистика по конкретной тематической группе"""
    group_name: str = Field(..., description="Название тематической группы", example="Транспорт")
    count: int = Field(..., description="Количество обращений", example=345)
    percentage: float = Field(..., description="Процент от общего числа", example=39.0)


class SeverityStat(BaseModel):
    """Распределение обращений по классу тяжести (0–4)"""
    severity: int = Field(..., description="Класс тяжести", example=2)
    label: str = Field(..., description="Название класса", example="Средняя тяжесть")
    count: int = Field(..., description="Количество обращений", example=45)
    percentage: float = Field(..., description="Процент от общего числа", example=21.4)


class IncidentExample(BaseModel):
    """Пример обращения с классом тяжести"""
    text: str = Field(..., description="Текст обращения")
    severity: int = Field(..., description="Класс тяжести ONNX (1–4)", example=3)
    label: str = Field(..., description="Название класса", example="Высокая")


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
    severity_stat: List[SeverityStat] = Field(
        default_factory=list,
        description="Распределение обращений по классу тяжести ONNX (0–4)",
    )
    incident_examples: List[IncidentExample] = Field(
        default_factory=list,
        description="Примеры проблемных обращений (severity > 0)",
    )

class DistrictReportResponse(BaseModel):
    """Схема ответа при запросе отчёта по району"""
    data: DistrictReport


class RegionPdfRequest(BaseModel):
    """Сводный PDF по нескольким муниципалитетам (demo / кастомная выборка)"""
    districts: List[DistrictReport] = Field(..., description="Отчёты по МО")
    executive_summary: str = Field("", description="Общая справка по региону")


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
    progress: float | None = Field(None, description="Подпрогресс шага 0–100", example=42.0)
    duration_sec: float | None = Field(None, description="Длительность шага в секундах", example=12.4)
    started_at: str | None = Field(None, description="Время начала шага (ISO)")
    ended_at: str | None = Field(None, description="Время окончания шага (ISO)")


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
    progress: float | None = Field(None, description="Общий прогресс пайплайна 0–100", example=35.5)


class PipelineOptions(BaseModel):
    """Параметры запуска пайплайна"""
    skip_summary: bool = Field(False, description="Пропустить LLM-справки")
    batch_size: int = Field(16, description="Размер батча ONNX")
    nrows: int | None = Field(None, description="Ограничить число строк (для теста)")
    model: str | None = Field(None, description="Модель Ollama (по умолчанию gemma4:e2b)")
    llm_fast_mode: bool = Field(
        True,
        description="Короткие ИИ-сводки (параллельно по Top-10/Top-3) + итоговая справка; false — более развёрнутый текст",
    )


class AgencyPreviewItem(BaseModel):
    name: str
    total_count: int
    critical_count: int
    counts: dict[str, int]


class MunicipalityPreviewItem(BaseModel):
    name: str
    agencies: List[AgencyPreviewItem]


class DepartmentReportsPreview(BaseModel):
    municipalities_count: int
    agencies_count: int
    reports_count: int
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    municipalities: List[MunicipalityPreviewItem]


class DepartmentReportsStatus(BaseModel):
    task_id: str
    status: str
    message: str = ""
    progress: float = 0
    current: int = 0
    total: int = 0
    current_municipality: Optional[str] = None
    current_agency: Optional[str] = None
    phase: Optional[str] = None
    preview: Optional[DepartmentReportsPreview] = None
