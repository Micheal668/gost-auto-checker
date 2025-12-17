import os
import uuid
from django.db import models
from django.utils import timezone


def uploads_path(instance, filename: str) -> str:
    """
    uploads/原文件名__本地时间戳.ext
    例：report__20251215_161427.docx
    """
    base, ext = os.path.splitext(filename)
    ext = (ext or "").lower()

    # 只允许 docx（双保险：view/serializer + model 层）
    if ext != ".docx":
        ext = ".docx"

    # 清理文件名，避免路径注入/特殊字符
    safe_base = (base or "upload").strip()
    safe_base = safe_base.replace("/", "_").replace("\\", "_")
    safe_base = safe_base.replace(" ", "_")

    ts = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    return f"uploads/{safe_base}__{ts}{ext}"


def results_path(safe_base: str) -> str:
    # 结果文件也可控：results/gost_result_<jobid>.docx
    ts = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    return f"results/result_{safe_base}_{ts}.docx"


class Job(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING"
        RUNNING = "RUNNING"
        DONE = "DONE"
        FAILED = "FAILED"

    upload_ok = models.BooleanField(default=True)
    upload_error = models.TextField(null=True, blank=True)

    download_count = models.PositiveIntegerField(default=0)
    last_download_at = models.DateTimeField(null=True, blank=True)
    last_download_ok = models.BooleanField(null=True, blank=True)
    last_download_error = models.TextField(null=True, blank=True)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    progress = models.PositiveSmallIntegerField(default=0)

    ai_mode = models.CharField(max_length=16, default="NONE")     # NONE | AI_DIRECT | HYBRID
    provider = models.CharField(max_length=16, default="NONE")    # GPT | DEEPSEEK | QWEN | NONE
    original_filename = models.CharField(max_length=255, blank=True, default="")
    uploaded_file = models.FileField(upload_to=uploads_path)
    result_file = models.FileField(upload_to=results_path, null=True, blank=True)

    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # ✅ 下载统计字段
    download_count = models.PositiveIntegerField(default=0)
    last_download_ok = models.BooleanField(null=True, blank=True)
    last_download_error = models.TextField(null=True, blank=True)
    last_download_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.id} {self.status} {self.progress}%"

class JobEvent(models.Model):
    class Type(models.TextChoices):
        UPLOAD = "UPLOAD"
        CHECK_START = "CHECK_START"
        CHECK_DONE = "CHECK_DONE"
        CHECK_FAILED = "CHECK_FAILED"
        DOWNLOAD = "DOWNLOAD"
        DOWNLOAD_FAILED = "DOWNLOAD_FAILED"

    job = models.ForeignKey("Job", on_delete=models.CASCADE, related_name="events")
    type = models.CharField(max_length=32, choices=Type.choices)
    ok = models.BooleanField(default=True)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    meta = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at} {self.job_id} {self.type} ok={self.ok}"

