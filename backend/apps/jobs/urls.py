from django.urls import path
from .views import JobCreateView, JobStatusView, JobDownloadView

urlpatterns = [
    path("jobs", JobCreateView.as_view(), name="job-create"),
    path("jobs/<uuid:job_id>", JobStatusView.as_view(), name="job-status"),
    path("jobs/<uuid:job_id>/download", JobDownloadView.as_view(), name="job-download"),
]
