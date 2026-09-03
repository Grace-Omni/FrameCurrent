const params = new URLSearchParams(location.search);
const sessionId = params.get("session");
const movie = document.querySelector("#movie");
const cover = document.querySelector("#cover");
const coverTitle = document.querySelector("#coverTitle");
const coverCopy = document.querySelector("#coverCopy");
const loadingTrack = document.querySelector("#loadingTrack");
const loadText = document.querySelector("#loadText");
const controls = document.querySelector("#controls");
const playButton = document.querySelector("#playButton");
const timeline = document.querySelector("#timeline");
const timeText = document.querySelector("#timeText");
const downloadButton = document.querySelector("#downloadButton");
const fatal = document.querySelector("#fatal");
let session;
let seeking = false;

function fail(message) {
  fatal.style.display = "grid";
  fatal.textContent = message;
  cover.classList.add("hidden");
}

function formatTime(seconds) {
  const value = Math.max(0, Math.floor(Number(seconds) || 0));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const remainder = value % 60;
  if (hours) return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

function finalVideoUrl(data) {
  if (typeof data.final_video_url === "string") return data.final_video_url;
  if (typeof data.final_url === "string") return data.final_url;
  if (data.final_video && typeof data.final_video.url === "string") return data.final_video.url;
  return `/download/${encodeURIComponent(data.session_id)}/video.mp4`;
}

function finalDownloadUrl(data) {
  if (typeof data.download_url === "string") return data.download_url;
  return finalVideoUrl(data);
}

async function getSession() {
  if (!sessionId) throw new Error("作品链接不完整，请返回创作台重新打开。");
  const response = await fetch(`/api/session/${encodeURIComponent(sessionId)}`, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || "找不到这件作品。");
  if (data.status !== "complete") throw new Error("作品还在生成中，请返回创作台查看实时进度。");
  if (data.ready_to_download === false || data.finalizing === true) throw new Error("完整视频仍在合成，请稍后再打开。");
  return data;
}

function prepareMovie(data) {
  return new Promise((resolve, reject) => {
    const url = finalVideoUrl(data);
    const onReady = () => { cleanup(); resolve(url); };
    const onError = () => { cleanup(); reject(new Error("完整视频暂时无法读取，请返回创作台后重试。")); };
    const cleanup = () => {
      movie.removeEventListener("loadedmetadata", onReady);
      movie.removeEventListener("error", onError);
    };
    movie.addEventListener("loadedmetadata", onReady, { once: true });
    movie.addEventListener("error", onError, { once: true });
    movie.src = url;
    movie.load();
  });
}

async function begin() {
  try {
    await movie.play();
    cover.classList.add("hidden");
    controls.classList.add("visible");
  } catch (_) {
    coverCopy.textContent = "浏览器阻止了自动播放，请再次点击。";
  }
}

function togglePlayback() {
  if (movie.paused) movie.play(); else movie.pause();
}

function updateProgress() {
  if (!movie.duration) return;
  if (!seeking) timeline.value = String(Math.round((movie.currentTime / movie.duration) * 1000));
  timeText.textContent = `${formatTime(movie.currentTime)} / ${formatTime(movie.duration)}`;
  playButton.textContent = movie.paused ? "播放" : "暂停";
}

cover.addEventListener("click", begin);
playButton.addEventListener("click", togglePlayback);
movie.addEventListener("click", togglePlayback);
movie.addEventListener("timeupdate", updateProgress);
movie.addEventListener("play", () => {
  cover.classList.add("hidden");
  controls.classList.add("visible");
  updateProgress();
});
movie.addEventListener("pause", updateProgress);
movie.addEventListener("ended", () => {
  coverTitle.textContent = "完整视频播放完毕";
  coverCopy.textContent = "点击可从头重新播放，或直接下载MP4。";
  loadText.textContent = "REPLAY";
  cover.classList.remove("hidden");
  movie.currentTime = 0;
  updateProgress();
});

timeline.addEventListener("input", () => {
  seeking = true;
  if (movie.duration) timeText.textContent = `${formatTime((Number(timeline.value) / 1000) * movie.duration)} / ${formatTime(movie.duration)}`;
});
timeline.addEventListener("change", () => {
  if (movie.duration) movie.currentTime = (Number(timeline.value) / 1000) * movie.duration;
  seeking = false;
  updateProgress();
});

document.querySelector("#fullButton").addEventListener("click", async () => {
  if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
  else await document.exitFullscreen();
});

document.addEventListener("keydown", async (event) => {
  if (event.code === "Space") {
    event.preventDefault();
    togglePlayback();
  }
  if (event.key.toLowerCase() === "f") {
    if (!document.fullscreenElement) await document.documentElement.requestFullscreen();
    else await document.exitFullscreen();
  }
});

(async () => {
  try {
    session = await getSession();
    await prepareMovie(session);
    const durationSeconds = Number(session.generated_seconds || session.final_validation?.duration || session.config?.duration_seconds || movie.duration || 0);
    const durationLabel = formatTime(durationSeconds);
    const filenameDuration = durationLabel.replaceAll(":", "-");
    const channelName = String(session.config?.custom_channel_name || session.config?.preset_name || "AI频道节目")
      .replace(/[\\/:*?"<>|]/g, "-")
      .slice(0, 40);
    downloadButton.href = finalDownloadUrl(session);
    downloadButton.download = `FrameCurrent-连续影像-${channelName}-${filenameDuration}.mp4`;
    coverTitle.textContent = `${channelName} · 完整节目`;
    coverCopy.textContent = `点击播放 ${durationLabel} 连续影像。`;
    loadingTrack.hidden = true;
    loadText.textContent = "READY · CLICK TO PLAY";
    controls.classList.add("visible");
    updateProgress();
  } catch (error) {
    fail(error.message);
  }
})();
