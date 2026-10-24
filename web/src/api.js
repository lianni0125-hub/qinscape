const fallbackCapabilities = {
  gpu: { available: false, name: null, memory_gb: null },
  models: { text2midi: false, llm: false, vocal: false },
  renderers: { fluidsynth: false },
  mode: "cpu_preview",
};
export async function api(path, options = {}) {
  const r = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!r.ok) {
    const e = await r.json().catch(() => ({})),
      d = e.detail;
    throw new Error(
      typeof d === "string" ? d : d?.message || `请求失败 ${r.status}`,
    );
  }
  return r.json();
}
export async function capabilities() {
  try {
    return await api("/capabilities");
  } catch {
    return fallbackCapabilities;
  }
}
export async function setupStatus() {
  const response = await fetch("/api/setup");
  if (!response.ok) throw new Error("无法读取创作资源状态");
  return response.json();
}
export async function startSetup(component = null) {
  return api("/setup/start", { method: "POST", body: JSON.stringify({ component }) });
}
export async function uploadSetupPackage(component, file) {
  const form = new FormData(); form.append("file", file);
  const response = await fetch(`/api/setup/components/${component}/package`, { method: "POST", body: form });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.detail || `安装包导入失败 ${response.status}`);
  return body;
}
export async function updateStatus() {
  const response = await fetch("/api/update");
  if (!response.ok) throw new Error("无法读取版本状态");
  return response.json();
}
export async function checkUpdate() {
  return api("/update/check", { method: "POST", body: "{}" });
}
export async function startUpdate() {
  return api("/update/start", { method: "POST", body: "{}" });
}
export async function restartUpdate() {
  return api("/update/restart", { method: "POST", body: "{}" });
}
export async function catalog() {
  try {
    return await api("/catalog");
  } catch {
    return {
      ensemble_styles: [
        { id: "silk_bamboo", name: "丝竹清和", instruments: ["笛", "箫", "二胡", "柔弦"] },
        { id: "plucked", name: "弹拨疏影", instruments: ["扬琴", "竖琴", "三弦"] },
        { id: "clear_space", name: "清空入境", instruments: ["箫", "竖琴", "气声合唱"] },
        { id: "chamber", name: "东方室内乐", instruments: ["长笛", "双簧管", "大提琴"] },
        { id: "orchestral", name: "山河管弦", instruments: ["木管", "弦乐", "圆号"] },
      ],
      instrument_groups: [
        { id: "winds", name: "吹管", instruments: ["箫", "笛", "长笛", "双簧管"] },
        { id: "plucked", name: "弹拨", instruments: ["筝", "扬琴", "三弦", "竖琴", "西塔琴", "拇指琴"] },
        { id: "strings", name: "拉弦", instruments: ["二胡", "小提琴", "大提琴", "柔弦"] },
        { id: "space", name: "空间声部", instruments: ["气声合唱", "暖音垫", "圆号"] },
        { id: "accents", name: "点景与节律", instruments: ["木鱼", "钟铃", "太鼓"] },
      ],
      voices: [],
    };
  }
}
export async function plan(payload) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 30000);
  try {
    return await api("/sessions/plan", {
      method: "POST",
      body: JSON.stringify(payload),
      signal: controller.signal,
    });
  } catch {
    return localPlan(payload);
  } finally {
    window.clearTimeout(timeout);
  }
}
export async function generate(payload) {
  return api("/jobs", { method: "POST", body: JSON.stringify(payload) });
}
export async function preflight(payload) {
  return api("/preflight", { method: "POST", body: JSON.stringify(payload) });
}
export async function draftLyrics(payload) {
  return api("/lyrics/draft", { method: "POST", body: JSON.stringify(payload) });
}
export async function promptSuggestions(payload, signal) {
  return api("/suggestions", { method: "POST", body: JSON.stringify(payload), signal });
}
export async function reviseSession(id, patch) {
  return api(`/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}
export async function job(id) {
  return api(`/jobs/${id}`);
}
export async function listJobs() {
  return api("/jobs");
}
export async function deleteJob(id) {
  const r = await fetch(`/api/jobs/${id}`, { method: "DELETE" });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || "删除作品失败");
  }
}
export async function updateJobTitle(id, title) {
  return api(`/jobs/${id}/title`, { method: "PATCH", body: JSON.stringify({ title }) });
}
export async function listVoices() {
  return api("/voices");
}
export async function uploadVoice(form) {
  const r = await fetch("/api/voices", { method: "POST", body: form });
  if (!r.ok) {
    const body = await r.json().catch(() => ({}));
    throw new Error(body.detail || `上传失败 ${r.status}`);
  }
  return r.json();
}
export async function deleteVoice(id) {
  const r = await fetch(`/api/voices/${id}`, { method: "DELETE" });
  if (!r.ok) throw new Error("删除失败");
}
function localPlan(p) {
  const sad = /悲|难过|伤心|失落/.test(p.prompt);
  return {
    session_id: crypto.randomUUID(),
    card: {
      mode: p.mode,
      current: sad ? "悲伤 · 尚未细分" : "等待理解",
      target: sad ? "被容纳 · 慢慢稳定" : "由你的描述展开",
      method: sad ? "和 → 养" : "写意展开",
      imagery: p.imagery?.length ? p.imagery : ["远山", "微风"],
      sound: sad ? ["疏缓", "留白", "温和展开"] : ["清润", "有呼吸"],
      avoid: sad ? ["突然明快", "强烈高潮"] : [],
      prompt: p.prompt,
    },
    questions: sad
      ? [
          {
            id: "direction",
            text: "你希望音乐怎样陪伴这份悲伤？",
            options: ["静静陪伴", "慢慢释放", "走向安定", "给我一点力量"],
          },
        ]
      : [],
    ready: true,
    source: "browser_preview",
  };
}
