from contextlib import asynccontextmanager
from pathlib import Path
import sys
import uuid

from fastapi import APIRouter, BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, Response

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config.paths import DATA_DIR, JOBS_DIR
from app.pdf_report import (  # noqa: I001
    build_district_pdf,
    build_region_pdf,
    content_disposition_header,
    content_disposition_region_header,
)
from app.report import build_dashboard, build_district_report, build_top10_excel_from_report, enrich_report_period
from schemas import (
    DashboardResponse,
    DatasetUploadResponse,
    DistrictReport,
    DistrictReportResponse,
    GenerateReportRequest,
    GenerateReportResponse,
    JobStatus,
    PipelineOptions,
    PipelineStep,
    RegionPdfRequest,
)
from src import jobs

_district_tasks: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    jobs.load_jobs_from_disk()
    try:
        import onnxruntime as ort

        print(f"ZeroProblems: ONNX providers = {ort.get_available_providers()}", flush=True)
    except Exception as exc:
        print(f"ZeroProblems: ONNX check failed: {exc}", flush=True)
    print("ZeroProblems: бэкенд запущен, ONNX + пайплайн готовы.", flush=True)
    yield
    print("Выключение бэкенда...")


app = FastAPI(
    title="ZeroProblems - ML API",
    description="ZeroProblems: анализ обращений граждан — ONNX-классификация, Top-10/Top-3, LLM-справки",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api_router = APIRouter(prefix="/api/v1")


def _job_status(task_id: str) -> JobStatus:
    job = jobs.get_job(task_id)
    if job is None:
        raise HTTPException(404, "Задача не найдена")
    return JobStatus(
        task_id=job["task_id"],
        status=job["status"],
        message=job.get("message"),
        created_at=job.get("created_at"),
        filename=job.get("filename"),
        rows_processed=job.get("rows_processed"),
        stats=job.get("stats"),
        steps=[PipelineStep(**s) for s in (job.get("steps") or [])],
        progress=job.get("progress"),
    )


def _require_completed(task_id: str) -> Path:
    try:
        return jobs.require_completed(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Статус: {exc.status}") from exc


@api_router.get("/health", summary="Проверка состояния API")
async def health_check():
    return {"status": "ok", "backend": "onnx", "service": "ZeroProblems", "message": "ML API is running"}


@api_router.post(
    "/dataset/upload",
    response_model=DatasetUploadResponse,
    summary="Загрузка Excel и запуск обработки",
)
async def upload_dataset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    skip_summary: bool = False,
    batch_size: int = 16,
    nrows: int | None = None,
    model: str | None = None,
    llm_fast_mode: bool = True,
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(400, "Нужен файл .xlsx или .xls")

    task_id = str(uuid.uuid4())[:8]
    job_dir = jobs.job_path(task_id)
    job_dir.mkdir(parents=True, exist_ok=True)
    dest = job_dir / f"input{Path(file.filename).suffix}"
    content = await file.read()
    dest.write_bytes(content)

    options = PipelineOptions(
        skip_summary=skip_summary,
        batch_size=batch_size,
        nrows=nrows,
        model=model,
        llm_fast_mode=llm_fast_mode,
    )
    jobs.create_job(task_id, file.filename)
    background_tasks.add_task(jobs.run_job, task_id, dest, options)

    return DatasetUploadResponse(
        task_id=task_id,
        filename=file.filename,
        message=f"Датасет принят, задача {task_id} в обработке",
        rows_processed=0,
    )


@api_router.get("/jobs", response_model=list[JobStatus], summary="Список задач")
async def list_jobs():
    return [_job_status(j["task_id"]) for j in jobs.list_jobs() if jobs.get_job(j["task_id"])]


@api_router.get("/jobs/{task_id}", response_model=JobStatus, summary="Статус задачи")
async def get_job(task_id: str):
    return _job_status(task_id)


@api_router.get("/jobs/{task_id}/report", summary="Полный JSON-отчёт")
async def get_job_report(task_id: str):
    _require_completed(task_id)
    try:
        return jobs.get_report(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None


@api_router.get("/jobs/{task_id}/summary", summary="Текстовая справка для руководства")
async def get_job_summary(task_id: str):
    out = _require_completed(task_id)
    path = out / "executive_summary.md"
    if not path.exists():
        report = jobs.get_report(task_id)
        text = report.get("summary_text", "")
        if not text:
            raise HTTPException(404, "Справка не найдена")
        return PlainTextResponse(text, media_type="text/markdown")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@api_router.get("/jobs/{task_id}/summary/briefs", summary="Справки по Top-3 и Top-10")
async def get_job_municipality_briefs(task_id: str):
    out = _require_completed(task_id)
    path = out / "municipality_briefs.md"
    if not path.exists():
        raise HTTPException(404, "Справки по муниципалитетам не найдены — перезапустите обработку")
    return PlainTextResponse(path.read_text(encoding="utf-8"), media_type="text/markdown")


@api_router.get("/jobs/{task_id}/excel", summary="Скачать полный Excel-отчёт")
async def download_excel(task_id: str):
    out = _require_completed(task_id)
    path = out / "report_top_districts.xlsx"
    if not path.exists():
        raise HTTPException(404, "Excel-отчёт не найден")
    return FileResponse(path, filename="report_top_districts.xlsx")


@api_router.get("/jobs/{task_id}/excel/top10", summary="Скачать Excel по Top-10")
async def download_excel_top10(task_id: str):
    out = _require_completed(task_id)
    path = out / "report_top10.xlsx"
    if not path.exists():
        try:
            report = jobs.get_report(task_id)
            path = build_top10_excel_from_report(report, out)
        except FileNotFoundError:
            raise HTTPException(404, "Отчёт Top-10 не найден") from None
    return FileResponse(path, filename="report_top10.xlsx")


@api_router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Данные дашборда по последней или указанной задаче",
)
async def get_dashboard(task_id: str | None = None):
    resolved_id = task_id
    try:
        if task_id:
            report = jobs.get_report(task_id)
        else:
            completed = [
                j for j in jobs.list_jobs() if j.get("status") == "completed"
            ]
            if not completed:
                raise HTTPException(404, "Нет завершённых задач. Загрузите датасет.")
            completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
            resolved_id = completed[0]["task_id"]
            report = jobs.get_report(resolved_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача ещё не готова: {exc.status}") from exc
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None
    if resolved_id:
        enrich_report_period(report, jobs.job_path(resolved_id) / "cache")
    return build_dashboard(report)


@api_router.get(
    "/districts/{district_id}/report",
    response_model=DistrictReportResponse,
    summary="Отчёт по муниципалитету",
)
async def get_district_report(district_id: int, task_id: str | None = None):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    try:
        report = jobs.get_report(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача ещё не готова: {exc.status}") from exc
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None

    custom_summary = jobs.get_district_summary(task_id, district_id)
    result = build_district_report(
        report,
        district_id,
        analytical_summary=custom_summary,
        labeled_df=jobs.get_labeled_df(task_id),
    )
    if result is None:
        raise HTTPException(404, f"Район с id={district_id} не найден")
    return result


def _collect_district_reports(report: dict, task_id: str) -> list[DistrictReport]:
    labeled_df = jobs.get_labeled_df(task_id)
    districts: list[DistrictReport] = []
    for row in report.get("all", []):
        district_id = int(row.get("district_id", row.get("rank", 0)))
        custom_summary = jobs.get_district_summary(task_id, district_id)
        result = build_district_report(
            report,
            district_id,
            analytical_summary=custom_summary,
            labeled_df=labeled_df,
        )
        if result is not None:
            districts.append(result.data)
    return districts


def _district_report_pdf_response(data: DistrictReport) -> Response:
    try:
        pdf_bytes = build_district_pdf(data)
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": content_disposition_header(
                data.district_id,
                data.district_name,
            ),
        },
    )


@api_router.get(
    "/districts/{district_id}/report.pdf",
    summary="PDF-отчёт по муниципалитету",
)
async def get_district_report_pdf(district_id: int, task_id: str | None = None):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    try:
        report = jobs.get_report(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Задача ещё не готова: {exc.status}") from exc
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None

    custom_summary = jobs.get_district_summary(task_id, district_id)
    result = build_district_report(
        report,
        district_id,
        analytical_summary=custom_summary,
        labeled_df=jobs.get_labeled_df(task_id),
    )
    if result is None:
        raise HTTPException(404, f"Район с id={district_id} не найден")
    return _district_report_pdf_response(result.data)


@api_router.post(
    "/reports/district/pdf",
    summary="PDF-отчёт по переданным данным (demo / без task_id)",
)
async def post_district_report_pdf(data: DistrictReport):
    return _district_report_pdf_response(data)


@api_router.get(
    "/jobs/{task_id}/report.pdf",
    summary="Сводный PDF по всем муниципалитетам задачи",
)
async def get_region_report_pdf(task_id: str):
    _require_completed(task_id)
    try:
        report = jobs.get_report(task_id)
    except FileNotFoundError:
        raise HTTPException(404, "Отчёт ещё не готов") from None

    districts = _collect_district_reports(report, task_id)
    if not districts:
        raise HTTPException(404, "Нет данных по муниципалитетам")

    try:
        pdf_bytes = build_region_pdf(districts, executive_summary=report.get("summary_text", ""))
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition_region_header()},
    )


@api_router.post(
    "/reports/region/pdf",
    summary="Сводный PDF по списку муниципалитетов (demo)",
)
async def post_region_report_pdf(body: RegionPdfRequest):
    if not body.districts:
        raise HTTPException(400, "Список муниципалитетов пуст")
    try:
        pdf_bytes = build_region_pdf(body.districts, executive_summary=body.executive_summary)
    except Exception as exc:
        raise HTTPException(500, f"Не удалось сформировать PDF: {exc}") from exc
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition_region_header()},
    )


@api_router.post(
    "/reports/generate",
    response_model=GenerateReportResponse,
    summary="Генерация подробного LLM-отчёта по району",
)
async def generate_district_report(
    request: GenerateReportRequest,
    background_tasks: BackgroundTasks,
    task_id: str | None = None,
    model: str | None = None,
):
    if not task_id:
        completed = [j for j in jobs.list_jobs() if j.get("status") == "completed"]
        if not completed:
            raise HTTPException(404, "Нет завершённых задач")
        completed.sort(key=lambda j: j.get("created_at") or "", reverse=True)
        task_id = completed[0]["task_id"]

    try:
        jobs.require_completed(task_id)
    except KeyError:
        raise HTTPException(404, "Задача не найдена") from None
    except jobs.JobNotReadyError as exc:
        raise HTTPException(409, f"Статус: {exc.status}") from exc

    gen_task_id = f"report-{uuid.uuid4().hex[:8]}"
    _district_tasks[gen_task_id] = {
        "task_id": gen_task_id,
        "status": "processing",
        "message": "Генерация отчёта…",
        "district_id": request.district_id,
        "parent_task_id": task_id,
    }

    def _run():
        try:
            start = request.start_date.isoformat() if request.start_date else None
            end = request.end_date.isoformat() if request.end_date else None
            jobs.generate_district_report(
                task_id,
                request.district_id,
                start_date=start,
                end_date=end,
                model=model,
            )
            _district_tasks[gen_task_id]["status"] = "completed"
            _district_tasks[gen_task_id]["message"] = "Отчёт готов"
        except Exception as exc:
            _district_tasks[gen_task_id]["status"] = "failed"
            _district_tasks[gen_task_id]["message"] = str(exc)

    background_tasks.add_task(_run)
    return GenerateReportResponse(
        task_id=gen_task_id,
        status="processing",
        message="Отчёт генерируется, проверьте /districts/{id}/report после завершения",
    )


@api_router.get(
    "/reports/generate/{gen_task_id}",
    response_model=GenerateReportResponse,
    summary="Статус генерации отчёта по району",
)
async def get_generate_status(gen_task_id: str):
    task = _district_tasks.get(gen_task_id)
    if not task:
        raise HTTPException(404, "Задача генерации не найдена")
    return GenerateReportResponse(
        task_id=gen_task_id,
        status=task["status"],
        message=task.get("message", ""),
    )


app.include_router(api_router)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=True)
