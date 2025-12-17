// src/api/client.js
export const API_BASE = "http://127.0.0.1:8000/api";

function withBase(url) {
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return API_BASE + url;
}

export async function httpJson(url, options = {}) {
  const res = await fetch(withBase(url), options);

  const text = await res.text();
  let data = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = null; }

  if (!res.ok) {
    const msg =
      (data && (data.detail || data.message)) ? (data.detail || data.message) : `HTTP ${res.status}`;
    throw new Error(msg);
  }
  return data;
}

export function apiGet(url) {
  return httpJson(url, { method: "GET" });
}

export function apiPost(url, body) {
  // body 可以是 FormData 或 JSON string
  const opts = { method: "POST", body };

  // 如果你未来想支持 JSON：apiPost("/x", JSON.stringify(obj))
  // 这里不强行加 Content-Type，避免破坏 FormData
  return httpJson(url, opts);
}
