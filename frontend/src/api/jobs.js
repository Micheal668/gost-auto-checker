import { API_BASE, httpJson } from "./client";


export async function createJob({ file, ai_mode, provider }) {
  const fd = new FormData();
  fd.append("uploaded_file", file);
  fd.append("ai_mode", ai_mode);
  fd.append("provider", provider);

  return httpJson(`${API_BASE}/jobs`, { method: "POST", body: fd });
}

export async function getJob(jobId) {
  
  return httpJson(`${API_BASE}/jobs/${jobId}`, { method: "GET" });
}

// export function downloadJob(jobId) {
//   window.location.href = `${API_BASE}/jobs/${jobId}/download`;
// }

function filenameFromDisposition(cd, fallback = "result.docx") {
  if (!cd) return fallback;
  const m = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(cd);
  return m ? decodeURIComponent(m[1].replace(/"/g, "")) : fallback;
}

export async function downloadJob(jobId) {
  const url = `${API_BASE}/jobs/${jobId}/download`;
  const res = await fetch(url, { method: "GET" });
  if (!res.ok) throw new Error(`Download failed: HTTP ${res.status}`);

  const blob = await res.blob();
  const cd = res.headers.get("content-disposition");
  const name = filenameFromDisposition(cd, `${jobId}.docx`);

  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}