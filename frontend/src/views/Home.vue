<template>
  <div class="container">
    <div class="card">
      <h2>{{ t("title") }}</h2>

      <div class="row" style="margin-top: 10px;">
        <div>
          <label>{{ t("lang") }}</label><br />
          <select v-model="lang" @change="changeLang">
            <option value="zh">中文</option>
            <option value="en">English</option>
            <option value="ru">Русский</option>
          </select>
        </div>

        <div>
          <label>{{ t("aiMode") }}</label><br />
          <select v-model="aiMode">
            <option value="NONE">NONE</option>
            <option value="AI_DIRECT" disabled>AI_DIRECT (coming)</option>
            <option value="HYBRID" disabled>HYBRID (coming)</option>
          </select>
        </div>

        <div>
          <label>{{ t("provider") }}</label><br />
          <select v-model="provider" :disabled="aiMode === 'NONE'">
            <option value="NONE">NONE</option>
            <option value="GPT">GPT</option>
            <option value="DEEPSEEK">DEEPSEEK</option>
            <option value="QWEN">QWEN</option>
          </select>
        </div>

        <div style="min-width: 260px;">
          <label>{{ t("file") }}</label><br />
          <input
          ref="fileInput"pickFile() {this.$refs.fileInput && this.$refs.fileInput.click();},
          type="file"
          accept=".docx"
          @change="onFile"
          style="display:none"
        />

        <button type="button" @click="pickFile">
          {{ t("chooseFile") }}
        </button>

        <span style="margin-left:10px">
          {{ file ? file.name : t("noFile") }}
        </span>

        </div>

        <div>
          <button :disabled="!file || running" @click="start">
            {{ t("start") }}
          </button>
        </div>
      </div>

      <div class="err" v-if="error">{{ error }}</div>

      <div v-if="jobId" style="margin-top: 16px;">
        <div class="row">
          <span class="badge">{{ t("status") }}: {{ jobStatus }}</span>
          <span class="badge">{{ t("progress") }}: {{ progress }}%</span>
          <button :disabled="running" @click="refresh">{{ t("refresh") }}</button>
          <button :disabled="!downloadReady" @click="download">{{ t("download") }}</button>
        </div>

        <div class="progress" style="margin-top: 10px;">
          <div :style="{ width: progress + '%' }"></div>
        </div>

        <div class="err" v-if="jobError">{{ jobError }}</div>
      </div>
    </div>
  </div>
</template>

<script>
import { useI18n } from "vue-i18n";
import { createJob, getJob, downloadJob } from "../api/jobs";

export default {
  setup() {
    const { t, locale } = useI18n();
    return { t, locale };
  },
  data() {
    return {
      lang: "zh",
      aiMode: "NONE",
      provider: "NONE",
      file: null,
      error: null,

      jobId: null,
      jobStatus: null,
      progress: 0,
      jobError: null,
      downloadReady: false,

      timer: null
    };
  },
  computed: {
    running() {
      return this.jobStatus === "PENDING" || this.jobStatus === "RUNNING";
    }
  },
  methods: {
    changeLang() {
      this.locale = this.lang;
    },
    pickFile() {
  this.$refs.fileInput && this.$refs.fileInput.click();
},


    onFile(e) {
      this.error = null;
      const f = e.target.files && e.target.files[0];
      if (!f) return;

      if (!f.name.toLowerCase().endsWith(".docx")) {
        this.file = null;
        this.error = this.t("errDocx");
        alert(this.t("errDocx"));
        return;
      }
      this.file = f;
    },

    async start() {
      try {
        this.error = null;
        this.jobError = null;
        this.jobId = null;
        this.jobStatus = null;
        this.progress = 0;
        this.downloadReady = false;

        const res = await createJob({
          file: this.file,
          ai_mode: this.aiMode,
          provider: this.provider
        });

        this.jobId = res.job_id;
        await this.refresh();

        if (this.timer) clearInterval(this.timer);
        this.timer = setInterval(() => this.refresh(), 1500);
      } catch (e) {
        this.error = e.message || String(e);
        alert(this.error);
      }
    },

    async refresh() {
      if (!this.jobId) return;
      try {
        const r = await getJob(this.jobId);
        this.jobStatus = r.status;
        this.progress = r.progress;
        this.jobError = r.error_message;

        this.downloadReady = (r.status === "DONE") && !!r.result_file;

        if (r.status === "DONE" || r.status === "FAILED") {
          if (this.timer) {
            clearInterval(this.timer);
            this.timer = null;
          }
        }
      } catch (e) {
        this.jobError = e.message || String(e);
      }
    },

    async download() {
      if (!this.jobId) return;
      try {
        await downloadJob(this.jobId);
      } catch (e) {
      this.jobError = e.message || String(e);
      alert(this.jobError);
      }
    }

  },

  beforeUnmount() {
    if (this.timer) clearInterval(this.timer);
  }
};
</script>
