from rest_framework import serializers
from .models import Job

class JobCreateSerializer(serializers.ModelSerializer):
    """
    POST /api/jobs
    - uploaded_file: 只允许 docx
    - ai_mode: NONE | AI_DIRECT | HYBRID
    - provider: NONE | GPT | DEEPSEEK | QWEN
    """
    uploaded_file = serializers.FileField(write_only=True)
    ai_mode = serializers.ChoiceField(choices=["NONE", "AI_DIRECT", "HYBRID"], default="NONE")
    provider = serializers.ChoiceField(choices=["NONE", "GPT", "DEEPSEEK", "QWEN"], default="NONE")

    class Meta:
        model = Job
        fields = ("uploaded_file", "ai_mode", "provider")

    def validate_uploaded_file(self, f):
        name = (getattr(f, "name", "") or "").lower()
        if not name.endswith(".docx"):
            raise serializers.ValidationError("Only .docx files are allowed.")
        return f


class JobStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "status", "progress", "ai_mode", "provider", "error_message", "created_at", "result_file")


class JobDownloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = ("id", "result_file")
