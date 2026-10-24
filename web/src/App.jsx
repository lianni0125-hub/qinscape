import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  ArrowLeft,
  BookOpen,
  Check,
  ChevronRight,
  Copy,
  Feather,
  Headphones,
  Leaf,
  Music2,
  Mic2,
  Pause,
  Play,
  RotateCcw,
  Sparkles,
  Square,
  Trash2,
  Upload,
  Waves,
  X,
} from "lucide-react";
import {
  capabilities,
  catalog,
  generate,
  job,
  listJobs,
  deleteJob,
  updateJobTitle,
  listVoices,
  plan,
  preflight,
  uploadVoice,
  deleteVoice,
  draftLyrics,
  promptSuggestions,
  setupStatus,
  startSetup,
  uploadSetupPackage,
  updateStatus,
  checkUpdate,
  startUpdate,
  restartUpdate,
} from "./api.js";

function formatAudioTime(value) {
  if (!Number.isFinite(value)) return "0:00";
  const minutes = Math.floor(value / 60);
  const seconds = Math.floor(value % 60).toString().padStart(2, "0");
  return `${minutes}:${seconds}`;
}
function formatChosenDuration(value) {
  const minutes = Math.floor(value / 60);
  const seconds = value % 60;
  if (!minutes) return `${seconds} 秒`;
  return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分钟`;
}

function SetupScreen({ value, error, onRefresh, onClose = null }) {
  const [actionError, setActionError] = useState("");
  const [starting, setStarting] = useState(false);
  const components = Object.entries(value?.components || {});
  const installing = Boolean(value?.active);
  const overall = components.length ? Math.round(components.reduce((sum, [, item]) => sum + (item.progress || 0), 0) / components.length) : 0;
  async function begin(component = null) {
    setActionError(""); setStarting(true);
    try { await startSetup(component); onRefresh(); }
    catch (reason) { setActionError(reason.message); }
    finally { setStarting(false); }
  }
  async function importPackage(component, event) {
    const file = event.target.files?.[0]; event.target.value = "";
    if (!file) return;
    setActionError("");
    try { await uploadSetupPackage(component, file); onRefresh(); }
    catch (reason) { setActionError(reason.message); }
  }
  return (
    <main className={`setup-shell ${onClose ? "setup-overlay" : ""}`}>
      <div className="setup-water" />
      <section className="setup-card">
        {onClose && <button className="icon setup-close" onClick={onClose} aria-label="关闭创作资源"><X /></button>}
        <Logo />
        <span className="setup-eyebrow">初次准备</span>
        <h1>琴境正在备齐创作的声音</h1>
        <p>可以留在此处，下载中断后也可从当前资源重试。</p>
        <div className="setup-overall"><i style={{ width: `${overall}%` }} /><span>{overall}%</span></div>
        <div className="setup-context">
          <span className={value?.gpu?.available ? "ready" : "warn"}>{value?.gpu?.available ? `${value.gpu.name} · ${value.gpu.memory_gb} GB` : "未检测到 CUDA 显卡"}</span>
          <span className={value?.disk?.free_gb >= value?.disk?.required_gb ? "ready" : "warn"}>剩余 {value?.disk?.free_gb ?? "—"} GB</span>
        </div>
        <div className="setup-list">
          {components.map(([id, item]) => (
            <article className={`setup-item ${item.status}`} key={id}>
              <span className="setup-state">{item.status === "ready" ? <Check /> : item.status === "installing" ? <Waves /> : item.status === "failed" ? "!" : "·"}</span>
              <div className="setup-copy"><b>{item.name}</b><small>{item.message} · {item.size}{item.required ? " · 核心" : " · 可选"}</small>{item.error && <em>{item.error}</em>}<div className="setup-line"><i style={{ width: `${item.progress || 0}%` }} /></div></div>
              <div className="setup-actions">
                {item.status !== "ready" && <button type="button" disabled={installing || starting} onClick={() => begin(id)}>{item.status === "failed" ? "再试一次" : "部署"}</button>}
                {item.status !== "ready" && <label><Upload />手动部署<input type="file" onChange={(event) => importPackage(id, event)} /></label>}
              </div>
            </article>
          ))}
        </div>
        {(actionError || error) && <div className="setup-error"><b>这一次没有完成</b><span>{actionError || error}</span><button onClick={onRefresh}>重新检查</button></div>}
        <div className="setup-footer">
          <button className="primary" disabled={installing || starting} onClick={() => begin(null)}>{installing ? "正在准备……" : "开始准备全部资源"}</button>
          <small>装好核心资源后即可进入；歌声与预设人声可以之后单独补齐。</small>
        </div>
      </section>
    </main>
  );
}

function UpdateModal({ value, onClose, onRefresh }) {
  const [error, setError] = useState("");
  const active = ["downloading", "verifying", "installing", "restarting"].includes(value.status);
  async function install() {
    setError("");
    try { await startUpdate(); onRefresh(); }
    catch (reason) { setError(reason.message); }
  }
  async function restart() {
    setError("");
    try { await restartUpdate(); onRefresh(); }
    catch (reason) { setError(reason.message); }
  }
  return createPortal(
    <div className="veil update-shade" role="dialog" aria-modal="true" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <section className="update-card">
        <button className="icon" onClick={onClose} aria-label="关闭"><X /></button>
        <span className="update-mark"><Sparkles /></span>
        <span className="eyebrow">琴境更新</span>
        <h2>{value.latest_version ? `新版本 ${value.latest_version}` : "版本更新"}</h2>
        <p>{value.message}</p>
        {Boolean(value.notes?.length) && <ul>{value.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
        <div className="update-progress"><i style={{ width: `${value.progress || 0}%` }} /></div>
        <div className="update-meta"><span>当前 {value.current_version}</span><b>{value.progress || 0}%</b></div>
        {(value.error || error) && <div className="update-error">{value.error || error}</div>}
        {value.status !== "complete" && <button className="primary update-action" disabled={active} onClick={install}>{active ? "正在更新……" : value.status === "failed" ? "重新尝试" : "更新琴境"}</button>}
        {value.status === "complete" && <button className="primary update-action" onClick={restart}>完成更新并重启</button>}
        <small>可以随时关闭，不更新也不影响现有功能。作品、模型与人声库不会被覆盖。</small>
      </section>
    </div>, document.body,
  );
}

function artifactDownload(work, kind) {
  return work?.id ? `/api/jobs/${work.id}/download/${kind}` : work?.artifacts?.[kind];
}

function AudioPreview({ work, source, kind, onClose }) {
  const audio = useRef(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);

  useEffect(() => {
    const closeOnEscape = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("keydown", closeOnEscape);
      audio.current?.pause();
    };
  }, [onClose]);

  async function toggle() {
    if (!audio.current) return;
    if (audio.current.paused) {
      try { await audio.current.play(); } catch { return; }
    } else audio.current.pause();
  }

  function seek(event) {
    const next = Number(event.target.value);
    if (audio.current) audio.current.currentTime = next;
    setCurrent(next);
  }

  return (
    <div className="confirm-shade audio-shade" role="dialog" aria-modal="true" aria-labelledby="audio-preview-title">
      <div className="audio-card">
        <button type="button" className="title-close" onClick={onClose} aria-label="关闭试听"><X /></button>
        <span className="eyebrow">{kind === "song" ? "有声之作" : "纯音乐"}</span>
        <h3 id="audio-preview-title">{work.title || "未题之作"}</h3>
        <p>循着声音，回到这段心境</p>
        <div className="audio-player">
          <button type="button" className="audio-toggle" onClick={toggle} aria-label={playing ? "暂停" : "播放"}>
            {playing ? <Pause fill="currentColor" /> : <Play fill="currentColor" />}
          </button>
          <div className="audio-track-wrap">
            <input className="audio-track" type="range" min="0" max={duration || 0} step="0.01" value={Math.min(current, duration || 0)} onChange={seek} style={{ "--audio-progress": `${duration ? (current / duration) * 100 : 0}%` }} aria-label="播放进度" />
            <div className="audio-times"><span>{formatAudioTime(current)}</span><span>{formatAudioTime(duration)}</span></div>
          </div>
        </div>
        <audio ref={audio} src={source} preload="metadata" onLoadedMetadata={(event) => setDuration(event.currentTarget.duration || 0)} onTimeUpdate={(event) => setCurrent(event.currentTarget.currentTime)} onPlay={() => setPlaying(true)} onPause={() => setPlaying(false)} onEnded={() => { setPlaying(false); setCurrent(0); }} />
        <div className="downloads"><a href={artifactDownload(work, kind)}>下载这一版</a></div>
      </div>
    </div>
  );
}

function normalizeLyricDraft(draft) {
  if (!draft || !Array.isArray(draft.lines)) return draft;
  const recovered = [];
  const lines = draft.lines.map((line) => {
    if (typeof line === "string") return line;
    if (line && Array.isArray(line.phrases)) {
      recovered.push(line);
      return line.phrases.map((part) => String(part).trim()).filter(Boolean).join("");
    }
    return "";
  }).filter(Boolean);
  return { ...draft, lines, prosody: Array.isArray(draft.prosody) && draft.prosody.length ? draft.prosody : recovered };
}

function LyricsPreview({ work, source, onClose }) {
  const cardRef = useRef(null);
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const closeOnEscape = (event) => { if (event.key === "Escape") onClose(); };
    const closeOutside = (event) => {
      if (cardRef.current && !cardRef.current.contains(event.target)) onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    document.addEventListener("pointerdown", closeOutside);
    fetch(source, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error("歌词暂时无法打开");
        return response.text();
      })
      .then((value) => {
        // lyrics.json also carries private arrangement metadata such as
        // vocal_sections. The reader should show the authored lyric only.
        try {
          const parsed = JSON.parse(value);
          const lines = Array.isArray(parsed?.lines) ? parsed.lines : [];
          setText(lines.map((line) => String(line).trim()).filter(Boolean).join("\n\n"));
        } catch {
          setText(value.trim());
        }
      })
      .catch((reason) => { if (reason.name !== "AbortError") setError(reason.message); })
      .finally(() => setLoading(false));
    return () => {
      controller.abort();
      window.removeEventListener("keydown", closeOnEscape);
      document.removeEventListener("pointerdown", closeOutside);
    };
  }, [source, onClose]);

  async function copyLyrics() {
    if (!text) return;
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setError("未能复制，请稍后重试");
    }
  }

  return createPortal(
    <div className="confirm-shade lyrics-shade" role="dialog" aria-modal="true" aria-labelledby="lyrics-preview-title">
      <div className="lyrics-card" ref={cardRef}>
        <span className="eyebrow">词页</span>
        <h3 id="lyrics-preview-title">{work.title || "未题之作"}</h3>
        <span className="lyrics-ornament" aria-hidden="true"><i /></span>
        <div className="lyrics-scroll">
          {loading && <p className="lyrics-message">正在展卷…</p>}
          {!loading && error && !text && <p className="lyrics-message">{error}</p>}
          {!loading && text && <div className="lyrics-text">{text}</div>}
        </div>
        <div className="lyrics-footer">
          <small>{error && text ? error : "琴境 · 此作歌词"}</small>
          <button type="button" className={copied ? "lyrics-copy copied" : "lyrics-copy"} onClick={copyLyrics} disabled={!text}>
            {copied ? <Check /> : <Copy />}{copied ? "已复制" : "复制全文"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}

function VoiceRequiredModal({ onClose }) {
  function openVoiceLibrary() {
    onClose();
    window.dispatchEvent(new Event("qinscape:open-voice-library"));
  }
  return (
    <div className="veil voice-required-shade" role="dialog" aria-modal="true" aria-labelledby="voice-required-title" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="voice-required-card">
        <span className="voice-required-mark"><Mic2 /></span>
        <span className="eyebrow">先留下一种声音</span>
        <h2 id="voice-required-title">人声库还是空的</h2>
        <p>加入歌词与人声前，需要先收藏一段清晰的参考演唱。上传后，再回来选择这次作品的声线。</p>
        <div className="voice-required-actions">
          <button type="button" className="quiet-button" onClick={onClose}>暂不加入</button>
          <button type="button" className="open-voice-library" onClick={openVoiceLibrary}>前往人声库</button>
        </div>
      </div>
    </div>
  );
}
const suggestionPools = {
  xieyi: [
    "雨后的空山，云正在散", "松风穿过月下石径", "一叶舟沿春水缓缓远去",
    "远处有水声穿过竹林", "月光落在无人经过的石阶上", "薄雾里偶尔传来一声鹤鸣",
    "让暮色从山脊逐层落下", "保留风停之后的大片留白", "清泉绕过长满青苔的旧石",
  ],
  tiaoxin: [
    "我有些悲伤，想先安静一会", "最近心里很乱，希望慢慢稳定", "有点疲惫，想找回一点力量",
    "心里压着火，想让它有地方流动", "有些害怕，希望声音稳稳陪着", "我对一件事很自责，想先松开一点",
    "我像是没什么感觉，想慢慢找回波动", "有些思念放不下，想留一处安放", "心绪太兴奋了，想慢慢收回来",
    "我有些迷茫，希望先听见一个方向", "压力堆得很满，想给自己留出空隙", "我还说不清，只想静静听一会",
  ],
};
const contextualSuggestions = {
  雨: ["保留雨后的潮湿与静意", "让檐下余响慢慢隐去", "在远处添一线初晴"],
  山: ["让山色由近处退向远方", "加入若隐若现的空谷回声", "让云雾沿山脊缓缓散开"],
  月: ["让月色落在更安静的地方", "保留夜深之后的大片留白", "加入一缕很远的风声"],
  水: ["让水声成为全曲的暗线", "加入一叶缓慢远去的舟", "让波纹一层层归于平静"],
  悲: ["希望音乐先陪伴，不急着改变", "让哀伤被轻轻承接住", "再慢慢走向可以呼吸的安定"],
  累: ["先给我稳定的支撑", "不要催促，只恢复一点生机", "让声音温厚而有呼吸"],
  乱: ["让节奏逐段变得简单", "先承接纷乱，再慢慢收束", "希望最后落在稳定的中心"],
  难过: ["先陪我停在这里，不急着转晴", "希望哀意被接住，再慢慢变轻", "保留一点低回，也留一点出口"],
  伤心: ["先陪我停在这里，不急着转晴", "希望哀意被接住，再慢慢变轻", "保留一点低回，也留一点出口"],
  孤独: ["希望声音靠近一些，但不要拥挤", "给我一处安静而温暖的回应", "让远处的声部慢慢来到身边"],
  委屈: ["先承接这份难言，不急着解释", "让紧绷一点点松开，不必强忍", "希望声音温和，却有支撑"],
  烦: ["让节奏逐段变得简单", "先把拥挤的念头一层层放下", "不要尖锐和突然的声音"],
  睡不着: ["让声音缓慢、重复而可预测", "不要明显高潮，只留平稳起伏", "希望思绪跟着节奏慢慢变远"],
  生气: ["先让这股力量有地方流动", "不压住它，也不让它继续升高", "希望节奏有力，但不尖锐"],
  愤怒: ["先让这股力量有地方流动", "不压住它，也不让它继续升高", "希望节奏有力，但不尖锐"],
  害怕: ["让声音稳定可预测，不突然逼近", "先给我一个可以停留的中心", "希望远处的声部慢慢靠近"],
  不安: ["让声音稳定可预测，不突然逼近", "先给我一个可以停留的中心", "希望起伏缓慢而有边界"],
  自责: ["不急着说服我，先让心绪松一点", "保留反思，但不反复下沉", "希望声音温和而有承托"],
  后悔: ["让过去被看见，也留一点向前的空间", "不反复强化遗憾", "希望收束时稳稳落下"],
  麻木: ["不强行振作，只唤回一点微弱波动", "从稳定的低声部慢慢展开", "不要过度热烈或甜美"],
  空洞: ["先给空白一个可以停留的轮廓", "只加入很微弱的生机", "让声音疏而不冷"],
  思念: ["让思念有一处安放，不急着告别", "保留远近之间的回应", "希望最后只留一点余温"],
  压力: ["先把拥挤的层次一点点减掉", "给呼吸和沉默留出位置", "希望声音稳定，不再增加任务感"],
  迷茫: ["不急着得出答案，先出现一条路", "让旋律从游离慢慢找到中心", "结尾保留开放，但不失去方向"],
  兴奋: ["保留这份明亮，再慢慢收回呼吸", "不要突然压低，只让节奏逐渐疏开", "希望最后明亮而安定"],
};
function randomSuggestions(mode, prompt = "", exclude = []) {
  const contextual = [...new Set(Object.entries(contextualSuggestions).flatMap(([key, values]) => prompt.includes(key) ? values : []))].filter((item) => !exclude.includes(item));
  const general = (suggestionPools[mode] || []).filter((item) => !exclude.includes(item) && !contextual.includes(item));
  for (let index = contextual.length - 1; index > 0; index -= 1) {
    const next = Math.floor(Math.random() * (index + 1));
    [contextual[index], contextual[next]] = [contextual[next], contextual[index]];
  }
  for (let index = general.length - 1; index > 0; index -= 1) {
    const next = Math.floor(Math.random() * (index + 1));
    [general[index], general[next]] = [general[next], general[index]];
  }
  return [...contextual.slice(0, 2), ...general].slice(0, 3);
}
const directions = ["静静陪伴", "慢慢释放", "走向安定", "给我一点力量"];
const CREATION_STAGES = {
  waiting: ["创作已入列，正在等待琴席", "正在为这段声音留出完整的生成空间", "前一段创作结束后，就会轮到你"],
  compiling: ["正在把琴心卡整理成全曲结构", "五音路径正在落入段落与呼吸", "正在确定起承转合的远近层次"],
  text2midi: ["旋律正在沿着五音路径生长", "正在寻找自然的句读与留白", "局部动机正在汇成一条完整声线"],
  skill_shaping: ["正在依照古曲结构塑形", "全曲与局部的呼吸正在彼此照应", "正在收束过密的音符，让旋律留得住气息"],
  arrangement: ["正在安排主奏、回应与铺底", "乐器会依次进入，不让声音拥挤", "正在让主音与主奏彼此照应"],
  rendering: ["正在把 MIDI 渲染成可以聆听的声音", "音色、力度与空间正在逐层显现", "正在裁去开头的空白，并保留自然余韵"],
  lyrics: ["正在让歌词贴合曲式与句法", "字句正在寻找适合歌唱的呼吸", "正在核对歌词与旋律的长度"],
  mixing: ["正在让歌声与器乐相遇", "正在平衡人声、主奏与远处的声部", "最后的音量与余韵正在收拢"],
};
let modalCopy = {};

function CreationProgress({ progress }) {
  const [phrase, setPhrase] = useState(0);
  const [elapsed, setElapsed] = useState(0);
  const stage = progress?.stage || "waiting";
  const phrases = CREATION_STAGES[stage] || ["结构、旋律、音色与呼吸正在逐层生成"];
  useEffect(() => {
    setPhrase(0); setElapsed(0);
    const phraseTimer = window.setInterval(() => setPhrase((value) => value + 1), 4600);
    const elapsedTimer = window.setInterval(() => setElapsed((value) => value + 1), 1000);
    return () => { window.clearInterval(phraseTimer); window.clearInterval(elapsedTimer); };
  }, [stage]);
  const percent = Math.max(0, Math.min(100, Math.round((progress?.progress || 0) * 100)));
  const slowAfter = { waiting: 120, compiling: 90, text2midi: 420, skill_shaping: 120, arrangement: 120, rendering: 300, lyrics: 180, mixing: 1200 }[stage] || 300;
  return (
    <div className="creating">
      <div className="creation-orbit"><Music2 /></div>
      <span className="creation-eyebrow">琴境正在创作</span>
      <h2>音乐正在生长</h2>
      <p className="creation-phrase" key={`${stage}-${phrase}`}>{phrases[phrase % phrases.length]}</p>
      <div className="progress" aria-label={`生成进度 ${percent}%`}><i style={{ width: `${percent}%` }} /></div>
      <div className="progress-meta"><b>{percent}%</b><span>{stage === "waiting" ? "等待开始" : "这一阶段仍在正常运行"}</span></div>
      {elapsed > slowAfter && <p className="slow-note">这一阶段比平时久一些，系统仍在回应；若任务失败，会在这里说明具体原因。</p>}
    </div>
  );
}

async function readJobWithRetry(id) {
  let lastError;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try { return await job(id); }
    catch (error) {
      lastError = error;
      if (attempt < 2) await new Promise((resolve) => window.setTimeout(resolve, 1800));
    }
  }
  throw lastError;
}
function WaterField() {
  const [pulse, setPulse] = useState(null);
  const audioRef = useRef(null);
  const soundReady = useRef(false);

  useEffect(() => {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (AudioContext) {
      audioRef.current = new AudioContext();
      audioRef.current.resume().then(() => {
        soundReady.current = audioRef.current?.state === "running";
      }).catch(() => {});
    }
    const unlock = () => {
      if (!audioRef.current) {
        if (AudioContext) audioRef.current = new AudioContext();
      }
      audioRef.current?.resume().then(() => { soundReady.current = true; });
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
    };
    window.addEventListener("pointerdown", unlock, { passive: true });
    window.addEventListener("keydown", unlock);
    return () => {
      window.removeEventListener("pointerdown", unlock);
      window.removeEventListener("keydown", unlock);
      audioRef.current?.close();
    };
  }, []);

  useEffect(() => {
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) return undefined;
    let timer;
    const chime = () => {
      const context = audioRef.current;
      if (!context || context.state !== "running") return;
      const pairs = [[523.25,659.25],[587.33,783.99],[659.25,880],[523.25,783.99]];
      const notes = pairs[Math.floor(Math.random() * pairs.length)];
      const now = context.currentTime;
      const filter = context.createBiquadFilter();
      const dry = context.createGain();
      const delay = context.createDelay(1);
      const feedback = context.createGain();
      const wet = context.createGain();
      filter.type = "lowpass";
      filter.frequency.value = 4200;
      filter.Q.value = .35;
      dry.gain.value = .72;
      delay.delayTime.value = .42;
      feedback.gain.value = .23;
      wet.gain.value = .27;
      filter.connect(dry);
      dry.connect(context.destination);
      filter.connect(delay);
      delay.connect(feedback);
      feedback.connect(delay);
      delay.connect(wet);
      wet.connect(context.destination);
      notes.forEach((frequency, index) => {
        const start = now + index * .46;
        [[1,.017,3.8],[2.01,.0052,2.7],[3.98,.0018,1.65]].forEach(([ratio, volume, decay]) => {
          const oscillator = context.createOscillator();
          const gain = context.createGain();
          oscillator.type = "sine";
          oscillator.frequency.value = frequency * ratio;
          oscillator.detune.value = ratio > 1 ? (index ? -2 : 2) : 0;
          gain.gain.setValueAtTime(.0001, start);
          gain.gain.exponentialRampToValueAtTime(volume, start + .025);
          gain.gain.exponentialRampToValueAtTime(.0001, start + decay);
          oscillator.connect(gain);
          gain.connect(filter);
          oscillator.start(start);
          oscillator.stop(start + decay + .08);
        });
      });
    };
    const ripple = () => {
      if (document.visibilityState === "visible") {
        setPulse({ key: Date.now(), x: 20 + Math.random() * 60, y: 20 + Math.random() * 60 });
        if (soundReady.current) chime();
      }
      timer = window.setTimeout(ripple, 8000 + Math.random() * 4000);
    };
    timer = window.setTimeout(ripple, 3600);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div className="water-field" aria-hidden="true">
      <span className="water-orb orb-one"><i /><i /></span>
      <span className="water-orb orb-two"><i /><i /></span>
      {pulse && <span key={pulse.key} className="wandering-ripple" style={{ left: `${pulse.x}%`, top: `${pulse.y}%` }} />}
    </div>
  );
}
function Logo() {
  const [open, setOpen] = useState(false),
    [voiceOpen, setVoiceOpen] = useState(false),
    [resourcesOpen, setResourcesOpen] = useState(false),
    [resources, setResources] = useState(null),
    [resourceError, setResourceError] = useState(""),
    [updateOpen, setUpdateOpen] = useState(false),
    [updateInfo, setUpdateInfo] = useState(null),
    [works, setWorks] = useState([]),
    [pendingDelete, setPendingDelete] = useState(null),
    [deleting, setDeleting] = useState(false),
    [workError, setWorkError] = useState(""),
    [editingTitle, setEditingTitle] = useState(null),
    [titleDraft, setTitleDraft] = useState(""),
    [audioPreview, setAudioPreview] = useState(null),
    [lyricsPreview, setLyricsPreview] = useState(null);
  const refreshResources = () => setupStatus().then((next) => { setResources(next); setResourceError(""); }).catch((reason) => setResourceError(reason.message));
  const refreshUpdate = () => updateStatus().then(setUpdateInfo).catch(() => {});
  useEffect(() => {
    const openVoiceLibrary = () => setVoiceOpen(true);
    window.addEventListener("qinscape:open-voice-library", openVoiceLibrary);
    return () => window.removeEventListener("qinscape:open-voice-library", openVoiceLibrary);
  }, []);
  useEffect(() => {
    if (!resourcesOpen || !resources?.active) return undefined;
    const timer = window.setInterval(refreshResources, 1200);
    return () => window.clearInterval(timer);
  }, [resourcesOpen, resources?.active]);
  useEffect(() => {
    refreshUpdate();
    const slow = window.setInterval(refreshUpdate, 60000);
    return () => window.clearInterval(slow);
  }, []);
  useEffect(() => {
    if (!["downloading", "verifying", "installing", "restarting"].includes(updateInfo?.status)) return undefined;
    const timer = window.setInterval(refreshUpdate, 1000);
    return () => window.clearInterval(timer);
  }, [updateInfo?.status]);
  async function show() {
    setOpen(true);
    try {
      setWorks(await listJobs());
    } catch {
      setWorks([]);
    }
  }
  async function confirmDelete() {
    if (!pendingDelete) return;
    setDeleting(true);
    setWorkError("");
    try {
      await deleteJob(pendingDelete.id);
      setWorks((items) => items.filter((item) => item.id !== pendingDelete.id));
      setPendingDelete(null);
    } catch (e) {
      setWorkError(e.message);
    } finally {
      setDeleting(false);
    }
  }
  async function saveTitle(work) {
    const value=titleDraft.trim();
    if (!value || value===work.title) { setEditingTitle(null); return; }
    setWorkError("");
    try {
      const updated=await updateJobTitle(work.id,value);
      setWorks((items)=>items.map((item)=>item.id===work.id?{...item,...updated}:item));
      setEditingTitle(null);
    } catch(e) { setWorkError(e.message); }
  }
  return (
    <>
      <div className="brand">
        <span className="seal" aria-hidden="true">
          <svg viewBox="0 0 48 48">
            <g className="pipa-mark">
              <rect className="mark-frame" x="2.5" y="2.5" width="43" height="43" rx="2.6" />
              <g className="pipa-figure" transform="rotate(-12 18 24)">
                <path className="pipa-body" d="M16.1 7.8c1.1-1 2.9-.8 3.9.4l-1.2 10.2c-.3 3.1 4.9 5.7 6.5 10.6 2 6.2-1.8 11.1-6.5 11.9-4.6.8-8.7-2.4-8.4-8 .3-6.4 5.6-10.7 5.8-14.6Z" />
                <path className="pipa-string" d="M17.9 8.8c-.3 8.9-.7 18.6-.8 27.9" />
                <path className="pipa-detail" d="M15.5 13.4h3.8m-4 3h3.7m-5.2 11.8c2.5.7 5.3.5 7.8-.7" />
              </g>
              <path className="water water-one" d="M27.8 19.1c4-3 7.5 2.4 13.8-.5" />
              <path className="water water-two" d="M28.2 26.3c4.8-3.1 7.8 2.6 14.1-.5" />
              <path className="water water-three" d="M27.7 33.5c4.1-2.3 7.6 2 13.9-.2" />
            </g>
          </svg>
        </span>
        <div>
          <b>琴境</b>
          <small>QINSCAPE</small>
        </div>
        {(updateInfo?.available || ["downloading", "verifying", "installing", "failed", "complete", "restarting"].includes(updateInfo?.status)) && <button className="update-pill" onClick={() => setUpdateOpen(true)}><i />版本更新</button>}
      </div>
      <nav className="header-tools" aria-label="个人收藏">
        <button className="header-tool" onClick={show} title="我的琴境">
          <BookOpen /><span>我的琴境</span>
        </button>
        <button className="header-tool" onClick={() => setVoiceOpen(true)} title="我的人声库">
          <Mic2 /><span>我的人声库</span>
        </button>
        <button className="header-tool" onClick={() => { setResourcesOpen(true); refreshResources(); }} title="创作资源">
          <RotateCcw /><span>创作资源</span>
        </button>
      </nav>
      {voiceOpen && <VoiceLibrary onClose={() => setVoiceOpen(false)} />}
      {resourcesOpen && resources && createPortal(<SetupScreen value={resources} error={resourceError} onRefresh={refreshResources} onClose={() => setResourcesOpen(false)} />, document.body)}
      {updateOpen && updateInfo && <UpdateModal value={updateInfo} onClose={() => setUpdateOpen(false)} onRefresh={refreshUpdate} />}
      {open && createPortal(
        <div className="veil library works-library" role="dialog" aria-modal="true">
          <div className="modal works-modal">
            <button className="icon" onClick={() => setOpen(false)}>
              <X />
            </button>
            <span className="eyebrow">作品留存</span>
            <h2>我的琴境</h2>
            {works.length === 0 ? (
              <p>还没有生成完成的作品。你的第一段琴声会留在这里。</p>
            ) : (
              <div className="work-list">
                {works.map((w) => (
                  <article key={w.id}>
                    <span>
                      {w.status === "complete"
                        ? "已完成"
                        : w.status === "failed"
                          ? "未完成"
                          : "生成中"}
                    </span>
                    <div className="work-name">
                      <button className="work-title" onClick={()=>{setEditingTitle(w.id);setTitleDraft(w.title||'未题之作');}} title="点击修改标题">{w.title||'未题之作'}</button>
                    </div>
                    <small>{w.stage}</small>
                    <button className="work-delete" onClick={() => { setWorkError(""); setPendingDelete(w); }} aria-label="删除作品" title="删除作品"><Trash2 /></button>
                    <div className="work-files">
                      {Object.entries(w.artifacts || {})
                        .filter(([k]) =>
                          ["midi", "instrumental", "song", "lyrics"].includes(
                            k,
                          ),
                        )
                        .map(([k, v]) => {
                          const label = { midi: "MIDI", instrumental: "纯音乐", song: "歌曲", lyrics: "歌词" }[k];
                          return ["instrumental", "song"].includes(k)
                            ? <button type="button" className="work-audio-link" key={k} onClick={() => setAudioPreview({ work: w, source: v, kind: k })}>{label}</button>
                            : k === "lyrics"
                              ? <button type="button" className="work-audio-link" key={k} onClick={() => setLyricsPreview({ work: w, source: v })}>{label}</button>
                              : <a key={k} href={artifactDownload(w, k)}>{label}</a>;
                        })}
                    </div>
                  </article>
                ))}
              </div>
            )}
            {workError && <p className="form-error">{workError}</p>}
            {pendingDelete && (
              <div className="confirm-shade" role="alertdialog" aria-modal="true" aria-labelledby="delete-work-title">
                <div className="confirm-card">
                  <span className="confirm-mark"><Trash2 /></span>
                  <h3 id="delete-work-title">让这段作品离开吗？</h3>
                  <p>删除后，相关音频、MIDI 与歌词将无法找回。</p>
                  <div><button className="quiet-button" disabled={deleting} onClick={() => setPendingDelete(null)}>再留一会</button><button className="danger-button" disabled={deleting} onClick={confirmDelete}>{deleting ? "正在删除…" : "确认删除"}</button></div>
                </div>
              </div>
            )}
            {editingTitle && (() => {
              const work = works.find((item) => item.id === editingTitle);
              if (!work) return null;
              return (
                <div className="confirm-shade title-shade" role="dialog" aria-modal="true" aria-labelledby="edit-work-title">
                  <form className="title-card" onSubmit={(event) => { event.preventDefault(); saveTitle(work); }}>
                    <button type="button" className="title-close" onClick={() => setEditingTitle(null)} aria-label="关闭"><X /></button>
                    <span className="eyebrow">为此刻留名</span>
                    <h3 id="edit-work-title">修改作品标题</h3>
                    <input autoFocus maxLength="40" value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} onKeyDown={(event) => { if (event.key === 'Escape') setEditingTitle(null); }} />
                    <small>初题　{work.original_title || work.title || '未题之作'}</small>
                    <div className="title-actions">
                      <button type="button" className="quiet-button" onClick={() => setEditingTitle(null)}>取消</button>
                      <button type="submit" className="save-title-button" disabled={!titleDraft.trim()}>保存新题</button>
                    </div>
                  </form>
                </div>
              );
            })()}
            {audioPreview && <AudioPreview {...audioPreview} onClose={() => setAudioPreview(null)} />}
            {lyricsPreview && <LyricsPreview {...lyricsPreview} onClose={() => setLyricsPreview(null)} />}
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
function VoiceLibrary({ onClose }) {
  const [voices, setVoices] = useState([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [sourceMode, setSourceMode] = useState("upload"),
    [recording, setRecording] = useState("idle"),
    [recordSeconds, setRecordSeconds] = useState(0),
    [recordLevel, setRecordLevel] = useState(0),
    [recordBlob, setRecordBlob] = useState(null),
    [recordUrl, setRecordUrl] = useState(""),
    [submitStage, setSubmitStage] = useState("");
  const recorderRef = useRef(null), streamRef = useRef(null), timerRef = useRef(null), audioContextRef = useRef(null), meterFrameRef = useRef(null), chunksRef = useRef([]), waveformCanvasRef = useRef(null), levelHistoryRef = useRef([]);
  const refresh = () => listVoices().then(setVoices).catch(() => setVoices([]));
  useEffect(() => {
    refresh();
    return () => {
      window.clearInterval(timerRef.current);window.cancelAnimationFrame(meterFrameRef.current);
      if(recorderRef.current?.state!=="inactive")recorderRef.current?.stop();streamRef.current?.getTracks().forEach((track) => track.stop());audioContextRef.current?.close().catch(() => {});
    };
  }, []);
  useEffect(()=>()=>{if(recordUrl)URL.revokeObjectURL(recordUrl);},[recordUrl]);
  function clearRecording() {
    if (recordUrl) URL.revokeObjectURL(recordUrl);
    levelHistoryRef.current=[];setRecordBlob(null);setRecordUrl("");setRecordSeconds(0);setRecordLevel(0);setRecording("idle");
  }
  function stopRecording() {
    const recorder=recorderRef.current;
    if (recorder && recorder.state!=="inactive") recorder.stop();
    window.clearInterval(timerRef.current);window.cancelAnimationFrame(meterFrameRef.current);
    streamRef.current?.getTracks().forEach((track) => track.stop());audioContextRef.current?.close().catch(() => {});
    streamRef.current=null;audioContextRef.current=null;setRecordLevel(0);
  }
  async function startRecording() {
    setError("");clearRecording();
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { setError("当前浏览器不支持直接录音，请改用上传音频。"); return; }
    try {
      const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:false},video:false});streamRef.current=stream;
      const mime=["audio/webm;codecs=opus","audio/webm","audio/ogg;codecs=opus"].find((type)=>MediaRecorder.isTypeSupported(type))||"";
      const recorder=new MediaRecorder(stream,mime?{mimeType:mime}:undefined);recorderRef.current=recorder;chunksRef.current=[];
      recorder.ondataavailable=(event)=>{if(event.data.size)chunksRef.current.push(event.data);};
      recorder.onstop=()=>{const blob=new Blob(chunksRef.current,{type:recorder.mimeType||"audio/webm"});const url=URL.createObjectURL(blob);setRecordBlob(blob);setRecordUrl(url);setRecording("ready");};
      const AudioContext=window.AudioContext||window.webkitAudioContext;const context=new AudioContext();audioContextRef.current=context;const analyser=context.createAnalyser();analyser.fftSize=512;analyser.smoothingTimeConstant=.72;context.createMediaStreamSource(stream).connect(analyser);const data=new Uint8Array(analyser.fftSize);
      const meter=()=>{analyser.getByteTimeDomainData(data);let energy=0;for(const value of data){const sample=(value-128)/128;energy+=sample*sample;}const rms=Math.sqrt(energy/data.length);const db=20*Math.log10(Math.max(rms,.00001));const level=Math.max(0,Math.min(100,Math.round((db+58)/48*100)));setRecordLevel(level);const history=levelHistoryRef.current;history.push(level);if(history.length>84)history.shift();const canvas=waveformCanvasRef.current;if(canvas){const ratio=window.devicePixelRatio||1,width=canvas.clientWidth,height=canvas.clientHeight;if(canvas.width!==Math.round(width*ratio)||canvas.height!==Math.round(height*ratio)){canvas.width=Math.round(width*ratio);canvas.height=Math.round(height*ratio);}const ctx=canvas.getContext("2d");ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);const middle=height/2,step=width/84,offset=84-history.length;ctx.beginPath();history.forEach((item,index)=>{const x=(offset+index+.5)*step;const amplitude=Math.max(.7,(item/100)*(height*.44));if(index===0)ctx.moveTo(x,middle-amplitude);else ctx.lineTo(x,middle-amplitude);});for(let index=history.length-1;index>=0;index--){const item=history[index],x=(offset+index+.5)*step,amplitude=Math.max(.7,(item/100)*(height*.44));ctx.lineTo(x,middle+amplitude);}ctx.closePath();const fill=ctx.createLinearGradient(0,0,0,height);fill.addColorStop(0,"rgba(91,122,103,.48)");fill.addColorStop(.5,"rgba(119,145,129,.12)");fill.addColorStop(1,"rgba(91,122,103,.48)");ctx.fillStyle=fill;ctx.fill();ctx.beginPath();ctx.moveTo(0,middle);ctx.lineTo(width,middle);ctx.strokeStyle="rgba(89,112,98,.13)";ctx.lineWidth=1;ctx.stroke();}meterFrameRef.current=window.requestAnimationFrame(meter);};meter();
      recorder.start(500);setRecording("recording");setRecordSeconds(0);
      timerRef.current=window.setInterval(()=>setRecordSeconds((value)=>{const next=value+1;if(next>=60)window.setTimeout(stopRecording,0);return Math.min(next,60);}),1000);
    } catch { setError("没有取得麦克风权限。请允许访问麦克风，或改用上传音频。"); }
  }
  function togglePause() {
    const recorder=recorderRef.current;if(!recorder)return;
    if(recorder.state==="recording"){recorder.pause();setRecording("paused");window.clearInterval(timerRef.current);}
    else if(recorder.state==="paused"){recorder.resume();setRecording("recording");timerRef.current=window.setInterval(()=>setRecordSeconds((value)=>{const next=value+1;if(next>=60)window.setTimeout(stopRecording,0);return Math.min(next,60);}),1000);}
  }
  async function submit(event) {
    event.preventDefault();
    const formElement=event.currentTarget;
    const form=new FormData(formElement);
    if (!String(form.get("name")||"").trim()) { setError("请先为这段声音取一个名称。"); return; }
    if (String(form.get("transcript")||"").trim().length<2) { setError("请填写音频中实际唱出的文字。"); return; }
    if (!form.get("consent")) { setError("请确认声音授权说明后再收录。"); return; }
    if (sourceMode==="upload" && !(form.get("audio")?.size)) { setError("请选择需要收录的 WAV 或 FLAC 音频。"); return; }
    if (sourceMode==="record" && (!recordBlob || recordSeconds<5)) { setError("请先完成一段至少 5 秒的演唱录音。"); return; }
    setBusy(true);
    setSubmitStage("正在上传并听取这段声音…");
    setError("");
    try {
      if(sourceMode==="record")form.append("audio",recordBlob,"recording.webm");
      window.setTimeout(()=>setSubmitStage("正在检查时长、音量与清晰度…"),500);
      await uploadVoice(form);
      formElement.reset();
      clearRecording();
      await refresh();
      window.dispatchEvent(new Event("qinscape:voices-changed"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setSubmitStage("");
    }
  }
  async function remove(id) {
    if (!window.confirm("确定从人声库中删除这个声音吗？")) return;
    setBusy(true);
    setError("");
    try {
      await deleteVoice(id);
      await refresh();
      window.dispatchEvent(new Event("qinscape:voices-changed"));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return createPortal(
    <div className="veil library voice-library" role="dialog" aria-modal="true">
      <div className="modal voice-modal">
        <button className="icon" onClick={onClose}><X /></button>
        <span className="eyebrow">声音留藏</span>
        <h2>我的人声库</h2>
        <p>留下你本人或已获明确授权的干声演唱。琴境会依照歌词与旋律延展这份声音，参考音频不会对外公开。</p>
        <div className="voice-rules">
          <span className="rules-title">准备一段清澈的声音</span>
          <div className="rule-grid">
            <article><small>来源</small><b>上传或即兴录制</b><span>5–60 秒 · 清晰演唱<br />上传文件 50 MB 以内</span></article>
            <article><small>声音</small><b>一人清晰演唱</b><span>无伴奏、无和声<br />少混响、无明显噪声</span></article>
            <article><small>唱词</small><b>逐字如实填写</b><span>文本必须与音频中的<br />实际唱词完全一致</span></article>
          </div>
        </div>
        <div className="voice-source-tabs" role="tablist"><button type="button" className={sourceMode==="upload"?"active":""} onClick={()=>setSourceMode("upload")}><Upload />上传已有录音</button><button type="button" className={sourceMode==="record"?"active":""} onClick={()=>setSourceMode("record")}><Mic2 />现在录一段</button></div>
        <form className="voice-form" onSubmit={submit} noValidate>
          <label><span>声线名称</span><input name="name" required maxLength="40" placeholder="例：清柔女声" /></label>
          <label><span>语言</span><select name="language" defaultValue="zh"><option value="zh">普通话</option><option value="yue">粤语</option><option value="en">英语</option></select></label>
          <label className="wide"><span>音频中的实际唱词</span><textarea name="transcript" required maxLength="500" rows="3" /></label>
          {sourceMode==="upload" ? <label className="wide"><span>参考音频</span><input name="audio" type="file" required accept=".wav,.flac,audio/wav,audio/flac" /></label> : <><div className="voice-recorder wide">
            <div className={`recording-disc ${recording}`}><i style={{transform:`scale(${.72+recordLevel/260})`}} /></div>
            <div className="recording-copy"><b>{recording==="idle"?"准备好后，唱下此刻的声音":recording==="recording"?"正在聆听你的演唱":recording==="paused"?"录音已暂歇":"这一段声音已经留下"}</b><span>{Math.floor(recordSeconds/60)}:{String(recordSeconds%60).padStart(2,"0")} · 建议 10–30 秒，最长 60 秒</span></div>
            <div className="recording-controls">{recording==="idle"&&<button type="button" onClick={startRecording}><Mic2 />开始录音</button>}{["recording","paused"].includes(recording)&&<><button type="button" onClick={togglePause}>{recording==="paused"?<Play />:<Pause />}{recording==="paused"?"继续":"暂停"}</button><button type="button" className="stop-record" onClick={stopRecording}><Square />完成</button></>}{recording==="ready"&&<button type="button" onClick={clearRecording}><RotateCcw />重录</button>}</div>
            {recordUrl&&<audio controls preload="metadata" src={recordUrl} />}
          </div><div className={`quiet-waveform wide ${recording}`} aria-label="实时响度波形"><canvas ref={waveformCanvasRef} /></div></>}
          <label className="consent wide"><input name="consent" type="checkbox" value="true" required /><span>我确认这是我本人的声音，或已获得声音本人对本项目合成与商业使用的明确授权；我不会用它冒充他人、误导公众或侵害他人权利。</span></label>
          {error && <p className="form-error wide" role="alert">{error}</p>}
          {busy && <div className="voice-checking wide" role="status"><i /><span>{submitStage || "正在检查…"}</span></div>}
          <button className="primary wide" disabled={busy}>{busy ? "请稍候…" : "收入人声库"}</button>
        </form>
        <div className="voice-list">
          {voices.map((v) => <article key={v.id} className={v.source_kind==="preset"?"preset-voice":""}><div><b>{v.name}{v.source_kind==="preset"&&<em>声线体验</em>}</b><small>{v.description?`${v.description} · `:""}{v.duration_seconds} 秒 · {v.sample_rate / 1000} kHz</small></div><audio controls preload="none" src={v.audio_url} />{v.source_kind!=="preset"&&<button disabled={busy} onClick={() => remove(v.id)}>删除</button>}</article>)}
          {!voices.length && <p className="hint">还没有收藏人声。上传或录制后，它会出现在“添加歌词”的声线选择中。</p>}
        </div>
      </div>
    </div>,
    document.body,
  );
}
function Modal({ onClose }) {
  const { title = "此处需要一张显卡", message, items = [], hint = "部署到 AutoDL 后完成配置并重新打开页面即可继续，无需重新填写。" } = modalCopy;
  return (
    <div className="veil" role="dialog" aria-modal="true">
      <div className="modal">
        <button className="icon" onClick={onClose}>
          <X />
        </button>
        <span className="modal-mark">
          <Waves />
        </span>
        <h2>{title}</h2>
        <p>
          {message ||
            "你的构思已经保存。生成 MIDI 或合成人声需要 CUDA GPU；当前设备只提供体验与规划。"}
        </p>
        {items.length > 0 && (
          <div className="device">
            <span>生成前还需要</span>
            <b>{items.join(" · ")}</b>
          </div>
        )}
        <p className="hint">{hint}</p>
        <button className="primary full" onClick={onClose}>
          我知道了
        </button>
      </div>
    </div>
  );
}
function FlowingReply({ children, delay = 560 }) {
  const text = String(children || "");
  const [visible, setVisible] = useState(0);
  const [listening, setListening] = useState(true);

  useEffect(() => {
    setVisible(0);
    setListening(true);
    let interval;
    const start = window.setTimeout(() => {
      setListening(false);
      interval = window.setInterval(() => {
        setVisible((value) => {
          if (value >= text.length) {
            window.clearInterval(interval);
            return value;
          }
          return value + 1;
        });
      }, 38);
    }, delay);
    return () => {
      window.clearTimeout(start);
      window.clearInterval(interval);
    };
  }, [text, delay]);

  return (
    <p className={listening ? "flowing-reply is-listening" : "flowing-reply"} aria-label={text}>
      {listening
        ? <span className="listening-dots" aria-hidden="true"><i /><i /><i /></span>
        : <span aria-hidden="true">{text.slice(0, visible)}</span>}
    </p>
  );
}

function Card({ card, onEdit }) {
  if (!card) return null;
  const toneNames = { gong: "宫", shang: "商", jue: "角", zhi: "徵", yu: "羽" };
  const rows = [
    ["此刻", card.current],
    ["去向", card.target],
    ["主音", toneNames[(card.five_tone_path || ["gong"])[0]] || "宫"],
    ["意象", (card.imagery || []).join(" · ")],
    ["声音", (card.sound || []).join(" · ")],
    ["五音路径", (card.five_tone_path || ["gong"]).map((x) => toneNames[x] || x).join(" → ")],
    ["避免", (card.avoid || []).join(" · ") || "无"],
  ];
  const rationale = `${card.method}。${card.five_tone_rationale || "五音作为传统文化推理的起点"}。不作医疗承诺。`;
  return (
    <section className="intent-card">
      <div className="card-head">
        <span>琴心</span>
        <button onClick={onEdit}>重新诉说</button>
      </div>
      {rows.map(([k, v], index) => (
        <div className="card-row" key={k}>
          <small>{k}</small>
          <span className="card-value-refresh" key={`${k}:${String(v)}`} style={{animationDelay:`${index*55}ms`}}>{v}</span>
        </div>
      ))}
      <details>
        <summary>创作依据</summary>
        <p className="card-rationale-refresh" key={rationale}>{rationale}</p>
      </details>
    </section>
  );
}
function Result({ result, onAgain }) {
  const artifacts = result?.artifacts || {};
  const audio = artifacts.song || artifacts.instrumental;
  const [lyricsOpen, setLyricsOpen] = useState(false);
  return (
    <div className="result">
      <span className="result-mark">
        <Headphones />
      </span>
      <span className="eyebrow">你的音乐已经抵达</span>
      <h2>{result?.title || (artifacts.song ? "有声歌 · 琴境" : "五音古风 · 琴境")}</h2>
      {audio && <audio controls src={audio} />}
      <div className="downloads">
        {Object.entries(artifacts)
          .filter(([k]) =>
            ["midi", "instrumental", "song", "lyrics"].includes(k),
          )
          .map(([k, v]) => k === "lyrics" ? (
            <button type="button" key={k} onClick={() => setLyricsOpen(true)}>查看歌词</button>
          ) : (
            <a href={artifactDownload(result, k)} key={k}>
              {
                {
                  midi: "下载 MIDI",
                  instrumental: "下载纯音乐",
                  song: "下载歌曲",
                }[k]
              }
            </a>
          ))}
      </div>
      {lyricsOpen && <LyricsPreview work={result} source={artifacts.lyrics} onClose={() => setLyricsOpen(false)} />}
      <button className="primary" onClick={onAgain}>
        再生一境
      </button>
    </div>
  );
}

function LyricsBrewing() {
  return (
    <div className="bubble qin-bubble lyric-brewing" role="status">
      <small>琴境</small>
      <div className="lyric-brewing-line">
        <p>正在生成歌词</p>
        <span className="listening-dots" aria-label="正在生成"><i /><i /><i /></span>
      </div>
      <em>把刚才的心绪写成可以歌唱的字句</em>
    </div>
  );
}

const STUDIO_DRAFT_KEY = "qinscape:studio-draft:v1";
function loadStudioDraft() {
  try {
    const draft = JSON.parse(window.localStorage.getItem(STUDIO_DRAFT_KEY) || "null") || {};
    // Older or interrupted sessions can point at a page whose required data was
    // never persisted. Recover to the nearest usable step instead of crashing.
    if (draft.step === "result" && !draft.result?.artifacts) {
      draft.step = draft.card ? "refine" : "input";
      draft.result = null;
    }
    if (draft.step === "creating" && !draft.progress?.id) {
      draft.step = draft.card ? "refine" : "input";
      draft.progress = null;
    }
    return draft;
  } catch {
    return {};
  }
}

function InstrumentChooser({ groups = [], preferred, excluded, lead, onPreferred, onExcluded, onLead }) {
  const wanted = preferred.split(/[、,，]/).map((x) => x.trim()).filter(Boolean);
  const avoided = excluded.split(/[、,，]/).map((x) => x.trim()).filter(Boolean);
  const write = (items, setter) => setter(items.join("、"));
  function toggleWanted(name) {
    const next = wanted.includes(name) ? wanted.filter((x) => x !== name) : [...wanted, name];
    write(next, onPreferred);
    if (avoided.includes(name)) write(avoided.filter((x) => x !== name), onExcluded);
    if (!next.includes(lead)) onLead(next[0] || "");
  }
  function toggleAvoided(name) {
    const next = avoided.includes(name) ? avoided.filter((x) => x !== name) : [...avoided, name];
    write(next, onExcluded);
    if (wanted.includes(name)) write(wanted.filter((x) => x !== name), onPreferred);
    if (lead === name) onLead("");
  }
  return (
    <details className="instrument-chooser" open>
      <summary><span>展开选择乐器</span><small>{wanted.length ? `已选 ${wanted.length} 件` : "也可交给琴境决定"}</small></summary>
      <div className="instrument-summary">
        <span>主奏倾向</span><b>{lead || "由五音与意象决定"}</b>
      </div>
      {groups.map((group) => (
        <section className="instrument-group" key={group.id}>
          <h4>{group.name}</h4>
          <div className="instrument-chips">
            {group.instruments.map((name) => (
              <button type="button" className={wanted.includes(name) ? "wanted" : avoided.includes(name) ? "avoided" : ""} key={name} onClick={() => toggleWanted(name)}>
                {name}<small>{wanted.includes(name) ? "想听" : avoided.includes(name) ? "已避开" : ""}</small>
              </button>
            ))}
          </div>
          <div className="instrument-actions">
            {group.instruments.filter((name) => wanted.includes(name)).map((name) => <button type="button" className={lead === name ? "active" : ""} key={name} onClick={() => onLead(name)}>以{name}主奏</button>)}
          </div>
          <div className="avoid-actions">
            {group.instruments.map((name) => <button type="button" className={avoided.includes(name) ? "active" : ""} key={name} onClick={() => toggleAvoided(name)}>{avoided.includes(name) ? `不听 ${name}` : `避开 ${name}`}</button>)}
          </div>
        </section>
      ))}
      <p className="instrument-note">五音决定声音重心，意象决定音色气质；你的主奏与避开选择会被优先遵守。</p>
    </details>
  );
}

export default function App() {
  const restored = useRef(loadStudioDraft()).current;
  const [mode, setMode] = useState(restored.mode || null),
    [prompt, setPrompt] = useState(restored.prompt || ""),
    [card, setCard] = useState(restored.card || null),
    [questions, setQuestions] = useState(restored.questions || []),
    [dialogueMessages, setDialogueMessages] = useState(restored.dialogueMessages || []),
    [followupDraft, setFollowupDraft] = useState(""),
    [caps, setCaps] = useState(null),
    [modal, setModal] = useState(null),
    [sessionId, setSessionId] = useState(restored.sessionId || null),
    [step, setStep] = useState(restored.step || "input"),
    [arrangement, setArrangement] = useState(restored.arrangement || "ensemble"),
    [ensembleStyle, setEnsembleStyle] = useState(restored.ensembleStyle || "silk_bamboo"),
    [soundCatalog, setSoundCatalog] = useState({ ensemble_styles: [], instrument_groups: [], voices: [] }),
    [duration, setDuration] = useState(restored.duration || 90),
    [lyrics, setLyrics] = useState(Boolean(restored.lyrics)),
    [voice, setVoice] = useState(restored.voice || "instrumental-guide"),
    [vocalBalance, setVocalBalance] = useState(restored.vocalBalance || "natural"),
    [leadInstrument, setLeadInstrument] = useState(restored.leadInstrument || ""),
    [preferredInstruments, setPreferredInstruments] = useState(restored.preferredInstruments || ""),
    [excludedInstruments, setExcludedInstruments] = useState(restored.excludedInstruments || ""),
    [lyricDraft, setLyricDraft] = useState(normalizeLyricDraft(restored.lyricDraft || null)),
    [lyricPreparing, setLyricPreparing] = useState(false),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(restored.progress || null),
    [result, setResult] = useState(restored.result || null),
    [safety, setSafety] = useState(restored.safety || null),
    [voiceRequired, setVoiceRequired] = useState(false),
    [promptHints, setPromptHints] = useState([]),
    [hintVersion, setHintVersion] = useState(0),
    [hintCycle, setHintCycle] = useState(0),
    [setupState, setSetupState] = useState(null),
    [setupError, setSetupError] = useState("");
  const promptInputRef = useRef(null);
  const hintHoverRef = useRef(false);
  const pendingHintsRef = useRef(null);
  const lastHintRequestRef = useRef(0);
  const hintRequestRef = useRef(0);
  const activeComposeRef = useRef(false);
  const dialogueRequestRef = useRef(false);
  const refreshSetup = () => setupStatus().then((next) => { setSetupState(next); setSetupError(""); }).catch((reason) => setSetupError(reason.message));
  useEffect(() => { refreshSetup(); }, []);
  useEffect(() => {
    if (!setupState?.active) return undefined;
    const timer = window.setInterval(refreshSetup, 1200);
    return () => window.clearInterval(timer);
  }, [setupState?.active]);
  useEffect(() => {
    window.localStorage.setItem(STUDIO_DRAFT_KEY, JSON.stringify({
      mode, prompt, card, questions, dialogueMessages, sessionId, step, arrangement, ensembleStyle,
      duration, lyrics, voice, vocalBalance, leadInstrument, preferredInstruments, excludedInstruments,
      lyricDraft, progress, result, safety,
    }));
  }, [mode, prompt, card, questions, dialogueMessages, sessionId, step, arrangement, ensembleStyle, duration, lyrics, voice, vocalBalance, leadInstrument, preferredInstruments, excludedInstruments, lyricDraft, progress, result, safety]);
  useEffect(() => {
    if (activeComposeRef.current || step !== "creating" || !progress?.id || ["complete", "failed"].includes(progress.status)) return undefined;
    let cancelled = false;
    setBusy(true);
    const resume = async () => {
      try {
        let current = await readJobWithRetry(progress.id);
        while (!cancelled && !["complete", "failed"].includes(current.status)) {
          setProgress(current);
          await new Promise((resolve) => window.setTimeout(resolve, 1600));
          current = await readJobWithRetry(progress.id);
        }
        if (cancelled) return;
        setProgress(current);
        if (current.status === "complete") {
          setResult(current);
          setStep("result");
        } else {
          showGenerationFailure(current);
          setStep("refine");
        }
      } catch {
        if (!cancelled) { showGenerationFailure(progress, true); setStep("refine"); }
      } finally {
        if (!cancelled) setBusy(false);
      }
    };
    resume();
    return () => { cancelled = true; };
  }, [step, progress?.id]);
  useEffect(() => {
    capabilities().then(setCaps);
    catalog().then(setSoundCatalog);
    const reload = () => {
      catalog().then(setSoundCatalog);
      listVoices().then((items) => { if (!items.length) setLyrics(false); }).catch(() => {});
    };
    window.addEventListener("qinscape:voices-changed", reload);
    return () => window.removeEventListener("qinscape:voices-changed", reload);
  }, []);
  useEffect(() => {
    if (!mode || card) return;
    setPromptHints(randomSuggestions(mode, prompt));
    setHintVersion((value) => value + 1);
  }, [mode, card]);
  useEffect(() => {
    const text = prompt.trim();
    if (!mode || card || text.length < 4) return undefined;
    const controller = new AbortController();
    const requestId = ++hintRequestRef.current;
    let disposed = false;
    const minimumWait = Math.max(1600, 5000 - (Date.now() - lastHintRequestRef.current));
    const timer = window.setTimeout(async () => {
      if (hintHoverRef.current) return;
      const local = randomSuggestions(mode, text, promptHints);
      lastHintRequestRef.current = Date.now();
      const responseTimer = window.setTimeout(() => controller.abort(), 8000);
      const applyOrQueue = (values) => {
        if (disposed || requestId !== hintRequestRef.current || !values?.length) return;
        const next = values.slice(0, 3);
        if (hintHoverRef.current) pendingHintsRef.current = next;
        else {
          setPromptHints(next);
          setHintVersion((value) => value + 1);
        }
      };
      try {
        const result = await promptSuggestions({ mode, prompt: text, exclude: promptHints }, controller.signal);
        applyOrQueue(result?.suggestions);
      } catch {
        applyOrQueue(local);
      } finally { window.clearTimeout(responseTimer); }
    }, minimumWait);
    return () => {
      disposed = true;
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [mode, card, prompt, hintCycle]);
  const canCompose = prompt.trim().length > 1;
  function showGenerationFailure(failure, connection = false) {
    const stageName = {
      waiting: "等待队列", compiling: "全曲规划", text2midi: "旋律生成", skill_shaping: "古曲结构塑形",
      arrangement: "多乐器编配", rendering: "音色渲染", lyrics: "歌词生成", mixing: "人声混音",
    }[failure?.error_stage || failure?.stage] || "生成过程";
    modalCopy = {
      title: connection ? "暂时没有收到生成进度" : "这次创作没有完成",
      message: connection ? "页面连续无法连接创作服务。琴心卡与当前选择仍然保留，可以稍后重试。" : (failure?.error || "生成过程意外中止，琴心卡与选择已经保留。"),
      items: [`发生阶段：${stageName}`, `错误类型：${connection ? "服务连接异常" : (failure?.error_code || "GENERATION_FAILED")}`],
      hint: "关闭后可以检查配置并重新开始；已经填写的内容不会丢失。",
    };
    setModal(modalCopy);
  }
  function leaveSuggestions() {
    hintHoverRef.current = false;
    if (pendingHintsRef.current) {
      setPromptHints(pendingHintsRef.current);
      pendingHintsRef.current = null;
      setHintVersion((value) => value + 1);
    } else if (prompt.trim().length >= 4) setHintCycle((value) => value + 1);
  }
  function choosePromptHint(value) {
    setPrompt((current) => current.trim() ? `${current.trim()}，${value}` : value);
    window.requestAnimationFrame(() => {
      promptInputRef.current?.focus();
      const end = promptInputRef.current?.value.length || 0;
      promptInputRef.current?.setSelectionRange(end, end);
    });
  }
  async function handleLyricsToggle(next) {
    if (!next) {
      setLyrics(false);
      return;
    }
    try {
      const voices = await listVoices();
      if (!voices.length) {
        setLyrics(false);
        setVoiceRequired(true);
        return;
      }
      if (voice === "instrumental-guide") setVoice(voices[0].id);
      setLyrics(true);
    } catch {
      setLyrics(false);
      setVoiceRequired(true);
    }
  }
  async function understand() {
    setBusy(true);
    try {
      const r = await plan({
        session_id: sessionId,
        mode,
        prompt,
        answers: {},
        arrangement,
        lyrics,
      });
      setSessionId(r.session_id);
      setCard(r.card);
      setQuestions(r.questions || []);
      setDialogueMessages([
        { id: crypto.randomUUID(), role: "user", text: prompt.trim() },
        { id: crypto.randomUUID(), role: "assistant", text: r.reply || r.questions?.[0]?.text || "我听见了。" },
      ]);
      setSafety(r.blocked_reason === "safety_crisis" ? r.safety_message : null);
      setStep("refine");
    } finally {
      setBusy(false);
    }
  }
  function currentPayload() {
    return {
      session_id: sessionId,
      card,
      arrangement,
      ensemble_style: ensembleStyle,
      lead_instrument: leadInstrument,
      preferred_instruments: preferredInstruments.split(/[、,，]/).map((x) => x.trim()).filter(Boolean),
      excluded_instruments: excludedInstruments.split(/[、,，]/).map((x) => x.trim()).filter(Boolean),
      lyrics,
      voice,
      vocal_balance: vocalBalance,
      duration_seconds: duration,
      approved_lyrics: lyricDraft,
    };
  }
  async function prepareLyrics() {
    if (!caps?.gpu?.available) {
      modalCopy = {};
      setModal({});
      return;
    }
    setBusy(true);
    setLyricPreparing(true);
    const shownAt = performance.now();
    try {
      // Let React commit the waiting bubble before starting model work. Even a
      // cached/fast response should feel acknowledged instead of visually stuck.
      await new Promise((resolve) => window.requestAnimationFrame(() => window.requestAnimationFrame(resolve)));
      const draft = await draftLyrics(currentPayload());
      const remaining = Math.max(0, 1400 - (performance.now() - shownAt));
      if (remaining) await new Promise((resolve) => window.setTimeout(resolve, remaining));
      setLyricDraft(normalizeLyricDraft(draft));
    } catch (e) {
      alert(e.message);
    } finally {
      setBusy(false);
      setLyricPreparing(false);
    }
  }
  async function continueDialogue(value, finish = false) {
    const answer = value.trim();
    if ((!answer && !finish) || busy || dialogueRequestRef.current) return;
    dialogueRequestRef.current = true;
    const shown = finish ? "就从这些开始" : answer;
    setDialogueMessages((items) => [...items, { id: crypto.randomUUID(), role: "user", text: shown }]);
    setFollowupDraft("");
    setBusy(true);
    try {
      const r = await plan({ session_id: sessionId, mode, prompt: answer || shown, answers: {}, arrangement, lyrics, finish_dialogue: finish });
      setSessionId(r.session_id);
      setCard(r.card);
      setQuestions(r.questions || []);
      setDialogueMessages((items) => [...items, { id: crypto.randomUUID(), role: "assistant", text: r.reply || r.questions?.[0]?.text || "我明白了。" }]);
      setSafety(r.blocked_reason === "safety_crisis" ? r.safety_message : null);
    } finally {
      dialogueRequestRef.current = false;
      setBusy(false);
    }
  }
  function chooseDirection(x) {
    setFollowupDraft(x);
  }
  function beginFreshMode(nextMode) {
    setMode(nextMode);
    setPrompt("");
    setCard(null);
    setQuestions([]);
    setDialogueMessages([]);
    setSessionId(null);
    setStep("input");
    setSafety(null);
    setLyricDraft(null);
    setResult(null);
    setProgress(null);
    setPreferredInstruments("");
    setExcludedInstruments("");
    setLeadInstrument("");
    setLyrics(false);
  }
  async function compose() {
    if (!caps?.gpu?.available) {
      modalCopy = {};
      setModal({});
      return;
    }
    setBusy(true);
    try {
      const payload = currentPayload();
      const check = await preflight(payload);
      if (!check.ready) {
        const lyricCrowded = check.missing.some((item) => item.startsWith("歌词共"));
        modalCopy = {
          title: lyricCrowded ? "给歌词留一点呼吸" : "创作资源还没有备齐",
          message: lyricCrowded ? "当前歌词在所选时长里会过于拥挤。我没有将它强行塞进旋律，你可以精简字句，或延长作品时长。" : "你的琴心卡已经保存。补齐下列本地资源后即可开始：",
          items: check.missing,
          hint: lyricCrowded ? "修改后可直接再次开始创作，其他选择都会保留。" : undefined,
        };
        setModal(modalCopy);
        return;
      }
      const created = await generate(payload);
      activeComposeRef.current = true;
      setStep("creating");
      setProgress(created);
      let current = created;
      while (!["complete", "failed"].includes(current.status)) {
        await new Promise((r) => setTimeout(r, 1600));
        current = await readJobWithRetry(created.id);
        setProgress(current);
      }
      if (current.status === "failed") {
        showGenerationFailure(current);
        setStep("refine");
        return;
      }
      setResult(current);
      setStep("result");
    } catch (e) {
      setStep("refine");
      showGenerationFailure({ stage: progress?.stage || "preflight", error: e.message, error_code: "PREFLIGHT_OR_SERVICE" }, false);
    } finally {
      activeComposeRef.current = false;
      setBusy(false);
    }
  }
  if (setupState && !setupState.ready)
    return <SetupScreen value={setupState} error={setupError} onRefresh={refreshSetup} />;
  if (step === "result" && result)
    return (
      <main className="shell">
        <header>
          <Logo />
        </header>
        <Result
          result={result}
          onAgain={() => {
            setMode(null);
            setPrompt("");
            setCard(null);
            setQuestions([]);
            setDialogueMessages([]);
            setFollowupDraft("");
            setSessionId(null);
            setStep("input");
            setResult(null);
            setProgress(null);
            setSafety(null);
            setLyricDraft(null);
            setLeadInstrument("");
            setPreferredInstruments("");
            setExcludedInstruments("");
            setLyrics(false);
          }}
        />
      </main>
    );
  if (!mode)
    return (
      <main className="shell landing">
        <WaterField />
        <header>
          <Logo />
          <span className="whisper">以一段声音，安放此刻</span>
        </header>
        <section className="hero">
          <span className="eyebrow">古风五音与东方调心</span>
          <h1>
            此刻，你想让音乐
            <br />
            怎样来到身边？
          </h1>
          <p>不必懂乐理。写下一幅景，或说说此刻的心绪。</p>
          <div className="portals">
            <button onClick={() => beginFreshMode("xieyi")}>
              <Feather />
              <span>
                <b>写意</b>
                <small>描绘一个想听见的世界</small>
              </span>
              <ChevronRight />
            </button>
            <button onClick={() => beginFreshMode("tiaoxin")}>
              <Leaf />
              <span>
                <b>调心</b>
                <small>从此刻，慢慢走向另一种心境</small>
              </span>
              <ChevronRight />
            </button>
          </div>
        </section>
        <footer>一弦一息 · 让未成言的心绪，循声舒展</footer>
      </main>
    );
  return (
    <main className={`shell studio ${mode} ${card ? "dialogue-studio" : "opening-studio"}`}>
      <header>
        <Logo />
        <button
          className="back"
          onClick={() => {
            setMode(null);
            setPrompt("");
            setStep("input");
            setCard(null);
            setQuestions([]);
            setDialogueMessages([]);
            setSessionId(null);
            setSafety(null);
            setLyricDraft(null);
            setResult(null);
            setProgress(null);
          }}
        >
          <ArrowLeft />
          换一种入口
        </button>
      </header>
      <div className={`workspace ${card ? "dialogue-workspace" : "opening-workspace"}`}>
        <section className="conversation">
          <span className="eyebrow">
            {mode === "xieyi" ? "写意 · 以景入声" : "调心 · 以声观心"}
          </span>
          <h1>
            {mode === "xieyi" ? "描绘你想听见的景象" : "此刻，心里是什么天气？"}
          </h1>
          <p>
            {mode === "xieyi"
              ? "时令、光影、远近与流动，都可以成为声音。"
              : "可以只说“我很难过”。如果愿意，也可以告诉我希望慢慢走向哪里。"}
          </p>
          <div className={`prompt-wrap ${card ? "submitted" : ""}`}>
            <textarea
              ref={promptInputRef}
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={
                mode === "xieyi"
                  ? "例如：雨后的空山，云从松间散开，远处有鹤掠过……"
                  : "例如：我最近有些悲伤，反复想起一件事，希望音乐陪我慢慢安定……"
              }
            />
            <div className="suggestions" onMouseEnter={() => { hintHoverRef.current = true; }} onMouseLeave={leaveSuggestions}>
              {promptHints.map((x, index) => (
                <button key={`${hintVersion}-${x}`} style={{ animationDelay: `${index * 70}ms` }} onClick={() => choosePromptHint(x)}>
                  {x}
                </button>
              ))}
            </div>
            {!card && (
              <div className="first-choices">
                <span>这次将创作一段多乐器古风音乐，并以五音路径组织情绪走向</span>
                <label className="toggle compact">
                  <span><b>添加歌词与人声</b><small>之后会在对话中审阅歌词、选择声线</small></span>
                  <input type="checkbox" checked={lyrics} onChange={(e) => handleLyricsToggle(e.target.checked)} /><i />
                </label>
              </div>
            )}
            <button
              className="primary understand"
              disabled={!canCompose || busy}
              onClick={understand}
            >
              <Sparkles />
              {busy ? "正在听见……" : "听见并展开"}
            </button>
          </div>
          {card && !safety && (
            <div className="chat-thread">
              {(dialogueMessages.length ? dialogueMessages : [
                { id: "restored-user", role: "user", text: prompt },
                { id: "restored-assistant", role: "assistant", text: questions[0]?.text || "我明白了。接下来，把它慢慢交给声音。" },
              ]).map((message, index, items) => (
                <div className={`bubble dialogue-message ${message.role === "user" ? "user-bubble" : "qin-bubble"}`} style={{ animationDelay: `${index === 0 ? .2 : .72}s` }} key={message.id}>
                  <small>{message.role === "user" ? "你" : "琴境"}</small>
                  {message.role === "assistant" ? <FlowingReply delay={index ? 420 : 560}>{message.text}</FlowingReply> : <p>{message.text}</p>}
                  {message.role === "assistant" && index === items.length - 1 && questions.length > 0 && (
                    <div className="dialogue-response">
                      <div className="bubble-actions">{(questions[0].options?.length ? questions[0].options : directions).map((x) => <button type="button" className={followupDraft === x ? "selected" : ""} key={x} onClick={() => chooseDirection(x)} disabled={busy}>{x}</button>)}</div>
                      <div className="followup-entry"><input value={followupDraft} onChange={(event) => setFollowupDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.nativeEvent.isComposing) continueDialogue(followupDraft); }} placeholder="选择后可修改，也可以用自己的话说……" /><button type="button" onClick={() => continueDialogue(followupDraft)} disabled={!followupDraft.trim() || busy}><Check />确认回答</button></div>
                      <button type="button" className="finish-dialogue" onClick={() => continueDialogue("", true)} disabled={busy}>就从这些开始</button>
                    </div>
                  )}
                </div>
              ))}
              {busy && questions.length > 0 && (
                <div className="bubble dialogue-message qin-bubble dialogue-waiting" role="status">
                  <small>琴境</small>
                  <span className="listening-dots" aria-label="正在理解"><i /><i /><i /></span>
                </div>
              )}
              {questions.length === 0 && arrangement === "ensemble" && (
                <div className="bubble qin-bubble"><small>琴境</small><FlowingReply delay={1100}>我会根据五音路径安排多乐器合奏。你有特别想听，或不想听见的乐器吗？留空就由我结合此刻的状态与意象来选。</FlowingReply>
                  <InstrumentChooser groups={soundCatalog.instrument_groups || []} preferred={preferredInstruments} excluded={excludedInstruments} lead={leadInstrument} onPreferred={setPreferredInstruments} onExcluded={setExcludedInstruments} onLead={setLeadInstrument} />
                  <label className="field"><span>编配气质</span><select value={ensembleStyle} onChange={(e) => setEnsembleStyle(e.target.value)}>{soundCatalog.ensemble_styles.map((style) => <option key={style.id} value={style.id}>{style.name}</option>)}</select><small>只影响候选权重，不会锁死一套乐器。</small></label>
                </div>
              )}
              {questions.length === 0 && lyrics && (
                <div className="bubble qin-bubble"><small>琴境</small><FlowingReply delay={1500}>我会先根据曲式写出歌词，给你逐句审阅；你确认后，才会生成逐字对齐的歌唱 MIDI。</FlowingReply><label className="field"><span>人声</span><select value={voice} onChange={(e) => setVoice(e.target.value)}>{soundCatalog.voices.filter((item) => item.id !== "instrumental-guide").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="field"><span>人声与器乐</span><select value={vocalBalance} onChange={(e) => setVocalBalance(e.target.value)}><option value="natural">自然融合</option><option value="forward">人声靠前</option><option value="instrumental">器乐为主</option></select><small>系统仍会根据实际响度自动平衡。</small></label></div>
              )}
              {questions.length === 0 && lyrics && lyricPreparing && <LyricsBrewing />}
              {questions.length === 0 && lyrics && lyricDraft && (
                <div className="bubble qin-bubble lyric-review">
                  <small>琴境 · 歌词初稿</small>
                  <input className="lyric-title" value={lyricDraft.title || ""} onChange={(e) => setLyricDraft({ ...lyricDraft, title: e.target.value })} />
                  {(lyricDraft.lines || []).map((line, index) => (
                    <input key={index} value={line} onChange={(e) => { const lines = [...lyricDraft.lines]; lines[index] = e.target.value; setLyricDraft({ ...lyricDraft, lines }); }} />
                  ))}
                  <p className="hint">可直接修改。确认后，将以这一版的字数和句法生成歌唱旋律。</p>
                </div>
              )}
              {questions.length === 0 && (!lyrics || !lyricPreparing) && (
                <div className="bubble qin-bubble final-bubble"><small>琴境</small><FlowingReply delay={1900}>我已经记下这些选择。作品时长可以再定一下，然后我们进入创作。</FlowingReply><div className="duration-picker"><div className="duration-heading"><span>作品时长</span><b>{formatChosenDuration(duration)}</b></div><input type="range" min="30" max="360" step="5" value={duration} onChange={(e) => setDuration(Number(e.target.value))} aria-label="作品时长" /><div className="duration-presets">{[[45,"片刻"],[90,"一境"],[180,"一章"],[300,"一曲"]].map(([value,label])=><button type="button" className={duration===value?"active":""} key={value} onClick={()=>setDuration(value)}>{label}<small>{formatChosenDuration(value)}</small></button>)}</div><p>可在 30 秒至 6 分钟之间调整；生成时会预留少量余裕，再裁去开头静音。</p></div><button className="compose" onClick={lyrics && !lyricDraft ? prepareLyrics : compose} disabled={busy}><Play fill="currentColor" />{lyricPreparing ? "正在酝酿歌词…" : lyrics && !lyricDraft ? "先生成歌词供我审阅" : lyricDraft ? "确认歌词并开始创作" : "开始创作"}</button></div>
              )}
            </div>
          )}
          {safety && (
            <div className="safety">
              <b>先让现实中的人陪到你</b>
              <p>{safety}</p>
              <small>琴境不是医疗或危机干预服务。</small>
            </div>
          )}
          {false && questions.length > 0 && (
            <div className="question">
              <span>不必回答，但你的选择会让琴声更贴近你</span>
              <h3>{questions[0].text}</h3>
              <div>
                {directions.map((x) => (
                  <button key={x} onClick={() => chooseDirection(x)}>
                    {x}
                  </button>
                ))}
              </div>
              <button className="skip" onClick={() => setQuestions([])}>
                沿用温和默认方向
              </button>
            </div>
          )}
        </section>
        <aside>
          <Card card={card} onEdit={() => {
            setCard(null);
            setQuestions([]);
            setDialogueMessages([]);
            setSessionId(null);
            setLyricDraft(null);
            setLyricPreparing(false);
            setProgress(null);
            setResult(null);
            setSafety(null);
            setStep("input");
          }} />
          {false && card && !safety && (
            <section className="settings">
              <h3>声音形态</h3>
              <div className="seg">
                <button
                  className={arrangement === "ensemble" ? "active" : ""}
                  onClick={() => setArrangement("ensemble")}
                >
                  古风合奏
                </button>
              </div>
              {arrangement === "ensemble" && (
                <label className="field">
                  <span>合奏编制</span>
                  <select
                    value={ensembleStyle}
                    onChange={(e) => setEnsembleStyle(e.target.value)}
                  >
                    {soundCatalog.ensemble_styles.map((style) => (
                      <option key={style.id} value={style.id}>
                        {style.name} · {style.instruments.join("、")}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <label className="field">
                <span>作品长度</span>
                <select
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                >
                  <option value={60}>一息 · 约 1 分钟</option>
                  <option value={90}>一境 · 约 90 秒</option>
                  <option value={180}>一章 · 约 3 分钟</option>
                  <option value={300}>一曲 · 约 5 分钟</option>
                </select>
              </label>
              <label className="toggle">
                <span>
                  <b>加入歌词与人声</b>
                  <small>作为合奏之外的独立维度</small>
                </span>
                <input
                  type="checkbox"
                  checked={lyrics}
                  onChange={(e) => handleLyricsToggle(e.target.checked)}
                />
                <i />
              </label>
              {lyrics && (
                <select
                  value={voice}
                  onChange={(e) => setVoice(e.target.value)}
                >
                  {soundCatalog.voices.filter((item) => item.id !== "instrumental-guide").map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              )}
              <button className="compose" onClick={compose} disabled={busy}>
                <Play fill="currentColor" />
                {busy ? "准备中……" : "进入创作"}
              </button>
              <div className="cap">
                <span className={caps?.gpu?.available ? "dot online" : "dot"} />
                {caps?.gpu?.available
                  ? `${caps.gpu.name} · 可以生成`
                  : "CPU 体验模式 · 构思会被保存"}
              </div>
            </section>
          )}
        </aside>
      </div>
      {step === "creating" && (
        <CreationProgress progress={progress} />
      )}
      {modal && <Modal onClose={() => setModal(false)} />}
      {voiceRequired && <VoiceRequiredModal onClose={() => setVoiceRequired(false)} />}
    </main>
  );
}
