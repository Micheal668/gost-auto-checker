import uuid
from django.db import models

class JobEvent(models.Model):
    class Type(models.TextChoices):
        UPLOAD = "UPLOAD"
        DOWNLOAD = "DOWNLOAD"
        CHECK_START = "CHECK_START"
        CHECK_DONE = "CHECK_DONE"
        CHECK_FAILED = "CHECK_FAILED"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    job = models.ForeignKey("jobs.Job", on_delete=models.CASCADE, related_name="events")
    type = models.CharField(max_length=32, choices=Type.choices)
    ok = models.BooleanField(default=True)
    message = models.TextField(null=True, blank=True)
    meta = models.JSONField(default=dict, blank=True)  # 存 ip/user-agent/文件名等
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.created_at} {self.type} ok={self.ok} job={self.job_id}"
