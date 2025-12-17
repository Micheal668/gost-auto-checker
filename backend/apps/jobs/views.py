import os
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404

from .models import Job, JobEvent
from .serializers import JobCreateSerializer, JobStatusSerializer
from .tasks import run_check_job

from django.utils import timezone
import logging


ALLOWED_EXT = ".docx"

class JobCreateView(APIView):
    def post(self, request):
        f = request.FILES.get("uploaded_file")
        if not f:
            return Response({"message": "No file uploaded"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ 扩展名校验（不区分大小写）
        if not f.name.lower().endswith(ALLOWED_EXT):
            return Response({"message": "Only .docx is allowed"}, status=status.HTTP_400_BAD_REQUEST)

        # ✅ 用 serializer 验证并保存（确保 uploaded_file 真正写入 Job）
        ser = JobCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        # 这里强制写入状态/进度（不依赖前端输入）
        job = ser.save(status=Job.Status.PENDING, progress=0)

        # ✅ 异步执行
        run_check_job.delay(str(job.id))

        return Response(
            {"job_id": str(job.id), "status": job.status, "progress": job.progress},
            status=status.HTTP_201_CREATED
        )


class JobStatusView(APIView):
    def get(self, request, job_id: str):
        job = get_object_or_404(Job, id=job_id)
        serializer = JobStatusSerializer(job)
        return Response(serializer.data)


logger = logging.getLogger(__name__)

class JobDownloadView(APIView):
    def get(self, request, job_id: str):
        job = get_object_or_404(Job, id=job_id)

        # 1) 未完成：409 + 记录失败
        if job.status != Job.Status.DONE:
            JobEvent.objects.create(
                job=job,
                type=JobEvent.Type.DOWNLOAD,
                ok=False,
                message="Result not ready",
                meta={"status": job.status, "progress": job.progress, "ip": request.META.get("REMOTE_ADDR")},
            )
            job.last_download_ok = False
            job.last_download_error = "Result not ready"
            job.last_download_at = timezone.now()
            job.save(update_fields=["last_download_ok", "last_download_error", "last_download_at"])

            return Response(
                {"message": "Result not ready", "status": job.status, "progress": job.progress},
                status=status.HTTP_409_CONFLICT,
            )

        # 2) DONE 但没挂文件：404 + 记录失败
        if not job.result_file:
            JobEvent.objects.create(
                job=job,
                type=JobEvent.Type.DOWNLOAD,
                ok=False,
                message="Result file not set",
                meta={"ip": request.META.get("REMOTE_ADDR")},
            )
            job.last_download_ok = False
            job.last_download_error = "Result file not set"
            job.last_download_at = timezone.now()
            job.save(update_fields=["last_download_ok", "last_download_error", "last_download_at"])
            raise Http404("Result file not set")

        # 3) 用 storage.open：兼容本地/未来上云存储
        try:
            fh = job.result_file.open("rb")
        except FileNotFoundError:
            JobEvent.objects.create(
                job=job,
                type=JobEvent.Type.DOWNLOAD,
                ok=False,
                message="Result file missing",
                meta={"path": getattr(job.result_file, "name", None)},
            )
            job.last_download_ok = False
            job.last_download_error = "Result file missing"
            job.last_download_at = timezone.now()
            job.save(update_fields=["last_download_ok", "last_download_error", "last_download_at"])
            raise Http404("Result file missing")
        except Exception as e:
            JobEvent.objects.create(job=job, type=JobEvent.Type.DOWNLOAD, ok=False, message=f"open failed: {e}")
            job.last_download_ok = False
            job.last_download_error = f"open failed: {e}"
            job.last_download_at = timezone.now()
            job.save(update_fields=["last_download_ok","last_download_error","last_download_at"])
            raise Http404("Result file missing")

        # 4) 成功下载：计数 + 时间 + 日志
        JobEvent.objects.create(
            job=job,
            type=JobEvent.Type.DOWNLOAD,
            ok=True,
            message="Download ok",
            meta={"ip": request.META.get("REMOTE_ADDR")},
        )
        job.download_count = (job.download_count or 0) + 1
        job.last_download_ok = True
        job.last_download_error = None
        job.last_download_at = timezone.now()
        job.save(update_fields=["download_count", "last_download_ok", "last_download_error", "last_download_at"])

        download_name = f"gost_result_{job_id}.docx"
        return FileResponse(fh, as_attachment=True, filename=download_name)
