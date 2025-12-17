from django.contrib import admin
from .models import Job, JobEvent

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "status",
        "progress",
        "provider",
        "download_count",
        "last_download_ok",
        "created_at",
    )

    def download_count(self, obj):
        return obj.events.filter(type="DOWNLOAD", ok=True).count()
    download_count.short_description = "Downloads"

    def last_download_ok(self, obj):
        last = obj.events.filter(type__in=["DOWNLOAD", "DOWNLOAD_FAILED"]).first()
        return last.ok if last else None
    last_download_ok.boolean = True

@admin.register(JobEvent)
class JobEventAdmin(admin.ModelAdmin):
    list_display = ("created_at","type","ok","job","message")
    list_filter = ("type","ok")
    search_fields = ("job__id","message")
    readonly_fields = ("created_at",)
