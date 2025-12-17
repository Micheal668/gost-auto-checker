from celery import shared_task
from django.conf import settings
from django.db import close_old_connections
from pathlib import Path
from django.utils import timezone
from apps.checker.engine.word_to_pdf import docx_to_pdf
from apps.jobs.models import Job
from apps.checker.engine.rule_loader import load_rules
from apps.checker.engine.docx_extractor import extract_docx_snapshot
from apps.checker.engine.hard_rules import run_hard_rules, run_rule
from apps.checker.engine.result_writer import write_result
from .models import JobEvent



RUNTIME_RULESET_PATH = (
    settings.BASE_DIR / "apps" / "checker" / "standards" / "gost_7_32_2017.runtime.json"
)

def _set_progress(job_id, progress=None, status=None, error=None, result_file=None):
    update = {}

    if progress is not None:
        update["progress"] = int(progress)
    if status is not None:
        update["status"] = status
    if error is not None:
        update["error_message"] = error

    # ✅ 这里必须叫 result_file，因为 model 字段就是 result_file
    if result_file is not None:
        update["result_file"] = result_file

    if update:
        Job.objects.filter(id=job_id).update(**update)
    """
    统一落库：只更新需要变动的字段。
    result_file 传相对 MEDIA_ROOT 的路径，如：results/xxx.docx
    """

# def _to_media_relative(path_str: str) -> str:
#     media_root = str(settings.MEDIA_ROOT).rstrip("/") + "/"
#     p = str(path_str)
#     return p.replace(media_root, "")

@shared_task(bind=True)
def run_check_job(self, job_id: str):
    close_old_connections()
    job = Job.objects.get(id=job_id)

    # 起始事件 + 起始状态
    JobEvent.objects.create(job=job, type=JobEvent.Type.CHECK_START, ok=True, message="Check started")
    _set_progress(job.id, progress=0, status=Job.Status.RUNNING, error=None, result_file=None)

    try:
        # 阶段 1：读取规则（10%）
        runtime = load_rules(str(RUNTIME_RULESET_PATH))
        _set_progress(job.id, progress=10)

        # 阶段 2：解析 docx（20%）
        doc_path = job.uploaded_file.path
        snap = extract_docx_snapshot(doc_path)
        # result_rel = write_result(settings.MEDIA_ROOT, str(job.id), issues, snapshot=snap)

        _set_progress(job.id, progress=20)

        # 阶段 3：执行规则（20% -> 90%，按 10% 刷新）
        rules = runtime.get("rules", []) or []
        total = max(len(rules), 1)

        issues: list[dict] = []
        next_tick = 30  # 30/40/.../90

        if rules:
            for idx, rule in enumerate(rules, start=1):
                try:
                    issues.extend(run_rule(snap, rule))
                except Exception as rule_exc:
                    # 单条规则失败：不影响全局（降级一条 issue）
                    issues.append({
                        "page": "?",
                        "severity": "NEED_REVIEW",
                        "category": "ENGINE",
                        "message": f"Rule {rule.get('id', '?')} failed: {rule_exc}",
                        "suggestion": "Проверьте правило/реализацию или отметьте для ручной проверки.",
                    })

                percent = 20 + int((idx / total) * 70)  # 20..90
                if percent >= next_tick:
                    _set_progress(job.id, progress=next_tick)
                    next_tick += 10

            _set_progress(job.id, progress=90)
        else:
            # 兜底：无规则也给 MVP 输出
            issues = run_hard_rules(runtime, snap)
            _set_progress(job.id, progress=90)

        # 阶段 4：写结果 docx（100%）
        # result_abs_path = Path(write_result(settings.MEDIA_ROOT, str(job.id), issues))
        # media_root = Path(settings.MEDIA_ROOT)
        # result_abs_path = Path(write_result(settings.MEDIA_ROOT, str(job.id), issues))
        # media_root = Path(settings.MEDIA_ROOT)
        # try:
        #     result_rel_path = result_abs_path.relative_to(media_root)
        # except ValueError:
        #     results_dir = media_root / "results"
        #     results_dir.mkdir(parents=True, exist_ok=True)
        #     forced = results_dir / result_abs_path.name
        #     if result_abs_path.exists() and forced.resolve() != result_abs_path.resolve():
        #         forced.write_bytes(result_abs_path.read_bytes())
        #     result_rel_path = forced.relative_to(media_root)
        result_rel = write_result(
            settings.MEDIA_ROOT,
            str(job.id),
            issues,
            snapshot=snap,   # ✅ 关键：把 anchor_map 输出到结果里
        )

        # 落库就用相对路径（FileField 存 name）
        JobEvent.objects.create(job=job, type=JobEvent.Type.CHECK_DONE, ok=True, message="Check done")
        _set_progress(job.id, progress=100, status=Job.Status.DONE, result_file=result_rel)
        # JobEvent.objects.create(job=job, type=JobEvent.Type.CHECK_DONE, ok=True, message="Check done")
        # _set_progress(job.id, progress=100, status=Job.Status.DONE, result_file=str(result_rel_path))

    except Exception as exc:
        error_msg = f"{type(exc).__name__}: {exc}"
        JobEvent.objects.create(job=job, type=JobEvent.Type.CHECK_FAILED, ok=False, message=error_msg)
        _set_progress(job.id, status=Job.Status.FAILED, error=error_msg, progress=100)
        raise
    finally:
        close_old_connections()