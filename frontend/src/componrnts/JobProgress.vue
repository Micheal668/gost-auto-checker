<!-- src/views/UploadView.vue -->
<template>
  <div>
    <input type="file" @change="onFile" />
    <button @click="upload">Upload</button>

    <!-- 关键：在页面里使用 JobProgress -->
    <JobProgress :jobId="jobId" />
  </div>
</template>

<script>
import JobProgress from "../components/JobProgress.vue"

export default {
  components: { JobProgress },
  data() {
    return {
      file: null,
      jobId: null
    }
  },
  methods: {
    onFile(e) {
      this.file = e.target.files[0]
    },
    async upload() {
      const fd = new FormData()
      fd.append("file", this.file)

      const res = await fetch("http://127.0.0.1:8000/api/jobs", {
        method: "POST",
        body: fd
      })
      const data = await res.json()

      // 🔥 这一行是“进度条启动开关”
      this.jobId = data.job_id
    }
  }
}
</script>
