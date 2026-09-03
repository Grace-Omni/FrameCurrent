const $ = (selector) => document.querySelector(selector);
const SESSION_STORAGE_KEY = "h3-max-channel-sessions-v2";
const LEGACY_SESSION_STORAGE_KEY = "h3-max-public-session";
const CHANNEL_DRAFTS_STORAGE_KEY = "h3-max-channel-drafts-v2";
const CUSTOM_CHANNEL_STORAGE_KEY = "h3-max-custom-channel-v1";
const PENDING_STARTS_STORAGE_KEY = "h3-max-pending-starts-v1";
const terminalStatuses = new Set(["complete", "failed", "stopped", "interrupted", "invalid"]);
const MIN_DURATION_SECONDS = 10;
const MAX_DURATION_SECONDS = 1800;
const MAX_LOCAL_ESTIMATED_BUDGET_USD = 150;
const MAX_CLIP_MARKERS = 60;

const state = {
  durationSeconds: 300,
  durationValid: true,
  durationMode: "fixed",
  activeChannelId: "hand_drawn_fantasy",
  channelSessions: {},
  channelDrafts: {},
  pendingRequestIds: {},
  restoring: false,
  restoreEpoch: 0,
  aspectRatio: "16:9",
  startImage: null,
  sourceImage: null,
  sourceImageName: "",
  sourceImageSize: 0,
  imagePreparing: false,
  imageRequestEpoch: 0,
  channelImages: {},
  subjectEdited: false,
  sceneEdited: false,
  actionEdited: false,
  cameraEdited: false,
  avoidEdited: false,
  sessionId: null,
  latestSession: null,
  pollTimer: null,
  busy: false,
  starting: false,
  paymentDialogOpen: false,
  keyVerified: false,
  verifiedKey: "",
  preview: {
    sessionId: null,
    clips: [],
    activeSlot: 0,
    activeClipIndex: -1,
    started: false,
    switching: false,
    waiting: false,
    syncing: false,
    tickHandle: null,
    epoch: 0,
  },
};

const presetProfiles = {
  hand_drawn_fantasy: {
    number: "CH 01",
    name: "日系手绘奇幻",
    subject: "一架红色复古单翼滑翔机，驾驶舱内的成年短发女飞行员始终穿芥末黄斗篷、背红色邮差包并戴圆形护目镜",
    scene: "漂浮在云海之上的手绘天空群岛，巨型风车、绿色草坡、瀑布和金色黄昏始终统一",
    action: "滑翔机沿天空岛外侧的开阔航线稳定前飞，既有风车始终从左侧安全距离后退，远处天空鲸只缓慢变大",
    camera: "电影感侧后方跟拍，低空平稳飞行，缓慢拉远揭示天空岛",
    avoid: "不要写实真人质感、不要现有动画角色、不要文字Logo、不要突然变成3D塑料材质",
    hint: "原创日系手绘动画质感；天空岛、强风与云海形成鲜明层次，建议16:9。",
  },
  cinematic_scifi: {
    number: "CH 02",
    name: "科幻史诗电影",
    subject: "一艘黑色三角深空侦察舰，银白骨架、三枚红色引擎和细长机翼始终一致",
    scene: "日蚀中的气态巨行星与环形轨道遗迹，黑色金属、冷青体积光、红色引擎辉光和漂浮星尘保持统一",
    action: "侦察舰沿环形巨构的开阔中轴稳定飞行，既有结构向两侧后退，远处中央核心只缓慢变大",
    camera: "超宽银幕低机位跟拍，镜头缓慢抬升揭示轨道巨构尺度",
    avoid: "不要卡通化、不要文字Logo或界面UI、不要飞船复制变形、不要爆炸遮挡主体或镜头翻滚",
    hint: "日蚀、轨道巨构与体积光强调大银幕尺度，16:9和768P效果更突出。",
  },
  studio_variety: {
    number: "CH 03",
    name: "高能棚内综艺",
    subject: "一位成年女主持人，利落短发、钴蓝色亮片西装和橙色手持麦克风始终一致",
    scene: "大型环形LED综艺舞台，青蓝、洋红和琥珀灯阵、镜面地板、抽象动态图形与观众灯海保持统一",
    action: "主持人沿清晰的舞台弧线缓慢走向中心，镜头保持安全距离，灯阵只在既有舞台结构内逐渐增强",
    camera: "稳定的广播摇臂机位，围绕舞台中心平滑半环绕并轻微推近",
    avoid: "不要可读文字、字幕、台标或Logo，不要第二位主持人抢镜、快速切镜、突然换装或肢体畸变",
    hint: "单主持人加大型舞台机关，保留综艺高能感同时降低多人连续生成漂移，建议16:9。",
  },
  travel_aerial: {
    number: "CH 04",
    name: "旅行电影航拍",
    subject: "一列红白相间的三节观景列车，黑色全景车窗和流线型车头始终一致",
    scene: "黄金时刻的高山海岸铁路，雪峰、翡翠湖、瀑布、松林山脊和海崖由同一条路线连接",
    action: "观景列车始终沿可见的悬崖铁路向前，无人机稳定平行跟随并缓慢升高，远处海湾逐渐展开",
    camera: "稳定无人机贴近主体前进并缓慢升高，始终保持地平线水平",
    avoid: "不要城市高楼、文字Logo、天气或时间突变、道路断裂、列车复制变形、快速旋转或地理跳切",
    hint: "用列车锁定连续路线，航拍逐渐升高展开雪山、湖湾与海岸，16:9最开阔。",
  },
  costume_drama: {
    number: "CH 05",
    name: "AI古装短剧",
    subject: "一位成年女侠，乌黑高马尾、月白窄袖劲装、深红披风和青铜剑鞘始终一致",
    scene: "月色下的东方古代宫城屋脊与回廊，青瓦、朱墙、灯笼暖光和薄雾保持统一",
    action: "女侠沿开阔屋脊稳定前行，既有宫墙从两侧后退，远处主殿只缓慢靠近",
    camera: "电影感中远景侧后方跟拍，稳定平移，保持屋脊方向清楚",
    avoid: "不要现代建筑服饰、不要现有影视角色、不要文字Logo、不要多人混战、不要飞檐穿模或快速旋转",
    hint: "月下宫城、红白服饰与屋脊追踪形成强烈古装短剧感；少角色和单路线更利于连续生成。",
  },
  custom_channel: {
    number: "CH ＋",
    name: "自定义频道",
    subject: "一个外形、材质和颜色始终一致的主角或主体",
    scene: "一个空间关系清晰、光线与材质统一的原创世界",
    action: "主体沿一条无遮挡的路线持续运动，远处目标缓慢靠近",
    camera: "低机位缓慢跟随主体向前",
    avoid: "不要文字Logo、不要突然换景、不要主体复制变形、不要碰撞穿模",
    hint: "为频道命名，再锁定一个主角、一个世界和一条持续动作路线。",
  },
};

function presetFieldValues(field) {
  return Object.values(presetProfiles).map((profile) => profile[field]);
}

const sceneBeats = [
  "沿着同一条路径继续向前，展开更深一层空间",
  "从前景细节旁经过，主体保持原来的速度",
  "光线在同一场景中柔和变化",
  "绕过一处环境结构，世界继续自然延伸",
  "靠近一处精致材质，再回到原来的前进方向",
  "前方打开更宽阔的景深与空间",
  "在不换场的前提下加入更梦幻的光影",
  "穿过属于当前世界的一道小小边界",
  "镜头轻微侧移，呈现温柔的空间层次",
  "远处的视觉惊喜逐渐靠近",
];

const previewVideos = [$("#previewA"), $("#previewB")];

const toast = (message) => {
  const node = $("#toast");
  node.textContent = message;
  node.classList.add("show");
  window.clearTimeout(toast.timer);
  toast.timer = window.setTimeout(() => node.classList.remove("show"), 2800);
};

const money = (value) => `$${Number(value || 0).toFixed(2)}`;

function formatDuration(seconds, empty = "00:00") {
  if (!Number.isFinite(Number(seconds))) return empty;
  const value = Math.max(0, Math.round(Number(seconds)));
  const hours = Math.floor(value / 3600);
  const minutes = Math.floor((value % 3600) / 60);
  const remainder = value % 60;
  if (hours) return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}

async function request(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    cache: "no-store",
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(data.error || data.message || `请求失败 (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return data;
}

async function checkHealth() {
  try {
    const health = await request("/api/health");
    $("#healthDot").classList.toggle("ok", Boolean(health.ok));
    $("#healthText").textContent = health.ok ? "AI 服务在线" : "AI 服务暂不可用";
  } catch (_) {
    $("#healthDot").classList.remove("ok");
    $("#healthText").textContent = "AI 服务未连接";
  }
}

function estimatedCost() {
  if (state.durationMode === "unlimited") return 0;
  if (!state.durationValid) return 0;
  const rate = $("#resolution").value === "768P" ? 0.08 : 0.05;
  return state.durationSeconds * rate;
}

function buildSchedule(durationSeconds, preferredSeconds) {
  const minCount = Math.ceil(durationSeconds / 15);
  const maxCount = Math.floor(durationSeconds / 5);
  if (minCount > maxCount) return [];
  let bestCount = minCount;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let count = minCount; count <= maxCount; count += 1) {
    const distance = Math.abs(durationSeconds / count - preferredSeconds);
    if (distance < bestDistance) {
      bestDistance = distance;
      bestCount = count;
    }
  }
  const base = Math.floor(durationSeconds / bestCount);
  const extra = durationSeconds % bestCount;
  return Array.from({ length: bestCount }, (_, index) => base + (index < extra ? 1 : 0));
}

function plannedClipCount() {
  if (!state.durationValid) return 0;
  return buildSchedule(state.durationSeconds, Number($("#clipDuration").value || 10)).length;
}

function durationFromInputs() {
  const rawMinutes = $("#durationMinutes").value.trim();
  const rawSeconds = $("#durationSeconds").value.trim();
  const minutes = Number(rawMinutes);
  const seconds = Number(rawSeconds);
  const fieldsValid = rawMinutes !== "" && rawSeconds !== ""
    && Number.isInteger(minutes) && Number.isInteger(seconds)
    && minutes >= 0 && minutes <= 30 && seconds >= 0 && seconds <= 59;
  const total = fieldsValid ? minutes * 60 + seconds : 0;
  return { total, valid: fieldsValid && total >= MIN_DURATION_SECONDS && total <= MAX_DURATION_SECONDS };
}

function setDurationInputs(totalSeconds) {
  const bounded = Math.max(MIN_DURATION_SECONDS, Math.min(MAX_DURATION_SECONDS, Math.round(totalSeconds)));
  $("#durationMinutes").value = String(Math.floor(bounded / 60));
  $("#durationSeconds").value = String(bounded % 60);
  updateDuration();
}

function updateDuration() {
  const { total, valid } = durationFromInputs();
  state.durationSeconds = total;
  state.durationValid = valid;
  const helper = $("#durationHelp");
  helper.classList.toggle("error", !valid);
  if (valid) {
    const clips = plannedClipCount();
    helper.textContent = `${formatDuration(total)} · 预计拆分为${clips}幕连续生成`;
    if (!state.sessionId || !state.busy) {
      renderClipGrid(clips, 0, "");
      $("#generatedTime").textContent = `00:00 / ${formatDuration(total)}`;
    }
  } else {
    helper.textContent = "请输入10秒到30分钟之间的有效时长";
  }
  document.querySelectorAll("[data-duration]").forEach((button) => {
    button.classList.toggle("active", valid && Number(button.dataset.duration) === total);
  });
  updateCost();
  updateBriefSummary();
}

function applyDurationMode(mode) {
  state.durationMode = mode === "unlimited" ? "unlimited" : "fixed";
  document.querySelectorAll('input[name="durationMode"]').forEach((input) => {
    input.checked = input.value === state.durationMode;
    input.closest("label").classList.toggle("selected", input.checked);
  });
  $("#fixedDurationControls").hidden = state.durationMode === "unlimited";
  $("#unlimitedDurationNote").hidden = state.durationMode !== "unlimited";
  updateCost();
  updateStartEligibility();
  if (!state.sessionId && !state.busy) {
    $("#progressFill").style.width = "0%";
    $(".progress-track").classList.remove("indeterminate");
    $("#progressPercent").textContent = state.durationMode === "unlimited" ? "LIVE" : "0%";
    $("#generatedTime").textContent = state.durationMode === "unlimited" ? "00:00 · 持续播出" : `00:00 / ${formatDuration(state.durationSeconds)}`;
    $("#etaTime").textContent = state.durationMode === "unlimited" ? "手动停播" : "—";
    if (state.durationMode === "unlimited") renderUnlimitedClipGrid(0, "");
    else renderClipGrid(plannedClipCount(), 0, "");
  }
}

function updateCost() {
  updateStartEligibility();
}

function updateStartEligibility() {
  const hasSubject = Boolean($("#subjectLock").value.trim());
  const hasScene = Boolean($("#sceneSetting").value.trim());
  const durationReady = state.durationMode === "unlimited" || state.durationValid;
  const unresolvedSession = Boolean(
    state.channelSessions[state.activeChannelId]
    && state.sessionId !== state.channelSessions[state.activeChannelId]
  );
  $("#startButton").disabled = state.busy || state.starting || state.paymentDialogOpen || state.restoring || state.imagePreparing || unresolvedSession || !durationReady || !hasSubject || !hasScene || !state.keyVerified;
  document.querySelectorAll('input[name="aspectRatio"]').forEach((input) => {
    input.disabled = state.imagePreparing;
  });
}

function compactText(value, maxLength) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  return clean.length > maxLength ? `${clean.slice(0, maxLength)}…` : clean;
}

function updateBriefSummary() {
  const subject = $("#subjectLock").value.trim() || "尚未填写主体";
  const scene = $("#sceneSetting").value.trim() || "尚未填写场景";
  const camera = $("#cameraMotion").selectedOptions[0]?.textContent || "缓慢跟随";
  const ratio = state.aspectRatio === "16:9" ? "横屏16:9" : "竖屏9:16";
  $("#briefSummary").textContent = `${compactText(subject, 34)} · ${compactText(scene, 28)} · ${camera} · ${ratio}`;
}

function creatorConcept() {
  const scene = $("#sceneSetting").value.trim();
  const action = $("#concept").value.trim();
  const camera = $("#cameraMotion").value;
  const avoid = $("#avoidContent").value.trim();
  const customStyle = state.activeChannelId === "custom_channel" ? $("#customChannelStyle").value.trim() : "";
  return [
    customStyle ? `Visual style: ${customStyle}` : "",
    `Scene setting: ${scene}`,
    action ? `Story action: ${action}` : "Story action: the subject continues naturally through the same world",
    `Camera direction: ${camera}`,
    avoid ? `Creator exclusions: ${avoid}` : "",
  ].filter(Boolean).join(". ");
}

async function cropReferenceImage(dataUrl, aspectRatio) {
  const image = new Image();
  await new Promise((resolve, reject) => {
    image.onload = resolve;
    image.onerror = () => reject(new Error("参考图无法读取"));
    image.src = dataUrl;
  });
  if (image.naturalWidth < 360 || image.naturalHeight < 360) {
    throw new Error("参考图分辨率过低，建议至少360像素宽高");
  }
  const portrait = aspectRatio === "9:16";
  const outputWidth = portrait ? 768 : 1344;
  const outputHeight = portrait ? 1344 : 768;
  const targetRatio = outputWidth / outputHeight;
  const sourceRatio = image.naturalWidth / image.naturalHeight;
  let sx = 0;
  let sy = 0;
  let sourceWidth = image.naturalWidth;
  let sourceHeight = image.naturalHeight;
  if (sourceRatio > targetRatio) {
    sourceWidth = image.naturalHeight * targetRatio;
    sx = (image.naturalWidth - sourceWidth) / 2;
  } else {
    sourceHeight = image.naturalWidth / targetRatio;
    sy = (image.naturalHeight - sourceHeight) / 2;
  }
  const canvas = document.createElement("canvas");
  canvas.width = outputWidth;
  canvas.height = outputHeight;
  const context = canvas.getContext("2d", { alpha: false });
  context.fillStyle = "#111512";
  context.fillRect(0, 0, outputWidth, outputHeight);
  context.drawImage(image, sx, sy, sourceWidth, sourceHeight, 0, 0, outputWidth, outputHeight);
  return canvas.toDataURL("image/jpeg", 0.92);
}

async function refreshReferenceImage(
  showMessage = false,
  channelId = state.activeChannelId,
  imageEpoch = state.imageRequestEpoch,
) {
  if (channelId !== state.activeChannelId || imageEpoch !== state.imageRequestEpoch) return;
  const preview = $("#imagePreview");
  if (!state.sourceImage) {
    state.startImage = null;
    preview.removeAttribute("src");
    preview.style.display = "none";
    $("#removeImage").hidden = true;
    const format = state.aspectRatio === "16:9" ? "横屏16:9" : "竖屏9:16";
    $("#uploadText").textContent = `可上传任意横竖图片，系统会按${format}生成预览`;
    return;
  }
  const sourceImage = state.sourceImage;
  const aspectRatio = state.aspectRatio;
  const sourceImageName = state.sourceImageName;
  const preparedImage = await cropReferenceImage(sourceImage, aspectRatio);
  if (channelId !== state.activeChannelId || imageEpoch !== state.imageRequestEpoch) return;
  state.startImage = preparedImage;
  preview.src = state.startImage;
  preview.classList.toggle("landscape", aspectRatio === "16:9");
  preview.style.display = "block";
  $("#removeImage").hidden = false;
  const format = aspectRatio === "16:9" ? "横屏16:9" : "竖屏9:16";
  $("#uploadText").textContent = `${sourceImageName} · 已按${format}居中裁切`;
  if (showMessage) toast(`参考图已切换为${format}预览`);
}

function applyAspectRatio(aspectRatio, refreshImage = true) {
  const channelId = state.activeChannelId;
  const imageEpoch = state.imageRequestEpoch + 1;
  state.imageRequestEpoch = imageEpoch;
  state.aspectRatio = aspectRatio === "16:9" ? "16:9" : "9:16";
  document.querySelectorAll('input[name="aspectRatio"]').forEach((input) => {
    input.checked = input.value === state.aspectRatio;
    input.closest(".ratio-option").classList.toggle("selected", input.checked);
  });
  $("#liveStage").classList.toggle("landscape", state.aspectRatio === "16:9");
  updateBriefSummary();
  if (state.sourceImage) {
    state.imagePreparing = true;
    state.startImage = null;
    $("#uploadText").textContent = "正在按新画幅准备参考图…";
    updateStartEligibility();
  }
  const refreshTask = refreshImage
    ? refreshReferenceImage(Boolean(state.sourceImage), channelId, imageEpoch).catch((error) => toast(error.message))
    : refreshReferenceImage(false, channelId, imageEpoch).catch(() => {});
  refreshTask.finally(() => {
    if (state.activeChannelId === channelId && state.imageRequestEpoch === imageEpoch) {
      state.imagePreparing = false;
      saveActiveChannelImage();
      updateStartEligibility();
    }
  });
}

function selectChannel(preset, restoreSession = true) {
  const profile = presetProfiles[preset];
  if (!profile) return;
  if (state.starting) {
    toast("当前频道正在开播，请稍候再换台");
    return;
  }
  if (
    restoreSession
    && state.activeChannelId === preset
    && (state.sessionId || !state.channelSessions[preset])
  ) return;
  if (state.activeChannelId && state.activeChannelId !== preset) {
    saveActiveChannelDraft();
    saveActiveChannelImage();
  }
  state.activeChannelId = preset;
  $("#preset").value = preset;
  document.body.dataset.visualPreset = preset;
  $("#configForm").dataset.presetTheme = preset;
  document.querySelectorAll("[data-preset]").forEach((node) => {
    const selected = node.dataset.preset === preset;
    node.classList.toggle("selected", selected);
    node.setAttribute("aria-pressed", String(selected));
  });
  const isCustom = preset === "custom_channel";
  $("#customChannelFields").hidden = !isCustom;
  $("#customProgramSettings").hidden = !isCustom;
  $("#configForm").dataset.channelKind = isCustom ? "custom" : "preset";
  $("#controlModeCopy").textContent = isCustom
    ? "先定义节目内容，再确认生成参数。"
    : "节目内容已经预设，只需确认生成参数。";
  const draft = state.channelDrafts[preset] || (isCustom ? recalledCustomChannel() : null);
  if (draft) state.channelDrafts[preset] = draft;
  if (isCustom) {
    $("#customChannelName").value = draft?.customChannelName || $("#customChannelName").value || "我的AI频道";
    $("#customChannelStyle").value = draft?.customChannelStyle || $("#customChannelStyle").value || "电影级原创视觉，统一色彩与材质";
    const customCardTitle = document.querySelector('[data-preset="custom_channel"] .channel-copy b');
    if (customCardTitle) customCardTitle.textContent = $("#customChannelName").value.trim() || profile.name;
  }
  const displayName = isCustom ? ($("#customChannelName").value.trim() || profile.name) : profile.name;
  $("#selectedChannelName").textContent = displayName;
  $("#playerChannelName").textContent = `${profile.number} · ${displayName}`;
  $("#stationChannelLabel").textContent = `${profile.number} · ${displayName}`;
  $("#liveBadge span").textContent = `AI LIVE · ${profile.number}`;
  $("#presetHint").textContent = profile.hint;
  [
    ["#subjectLock", "subject", "subjectEdited", "subjectLock"],
    ["#sceneSetting", "scene", "sceneEdited", "sceneSetting"],
    ["#concept", "action", "actionEdited", "concept"],
    ["#cameraMotion", "camera", "cameraEdited", "cameraMotion"],
    ["#avoidContent", "avoid", "avoidEdited", "avoidContent"],
  ].forEach(([selector, field, editedFlag, draftField]) => {
    const element = $(selector);
    element.value = draft?.[draftField] || profile[field];
    state[editedFlag] = false;
  });
  loadActiveChannelImage(!draft?.aspectRatio);
  if (draft?.aspectRatio) applyAspectRatio(draft.aspectRatio, false);
  updateBriefSummary();
  updateStartEligibility();
  if (restoreSession) {
    resetMonitorForChannel();
    loadChannelSession(preset);
  }
}

function captureActiveChannelDraft() {
  return {
    customChannelName: $("#customChannelName").value.trim(),
    customChannelStyle: $("#customChannelStyle").value.trim(),
    subjectLock: $("#subjectLock").value.trim(),
    sceneSetting: $("#sceneSetting").value.trim(),
    concept: $("#concept").value.trim(),
    cameraMotion: $("#cameraMotion").value,
    avoidContent: $("#avoidContent").value.trim(),
    aspectRatio: state.aspectRatio,
  };
}

function saveActiveChannelDraft() {
  if (!state.activeChannelId) return;
  const draft = captureActiveChannelDraft();
  state.channelDrafts[state.activeChannelId] = draft;
  try { window.localStorage.setItem(CHANNEL_DRAFTS_STORAGE_KEY, JSON.stringify(state.channelDrafts)); } catch (_) { /* no-op */ }
  if (state.activeChannelId === "custom_channel") {
    try { window.localStorage.setItem(CUSTOM_CHANNEL_STORAGE_KEY, JSON.stringify(draft)); } catch (_) { /* no-op */ }
  }
}

function recalledChannelDrafts() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(CHANNEL_DRAFTS_STORAGE_KEY) || "null");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (_) {
    return {};
  }
}

function recalledCustomChannel() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(CUSTOM_CHANNEL_STORAGE_KEY) || "null");
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch (_) {
    return null;
  }
}

function saveActiveChannelImage() {
  if (!state.activeChannelId) return;
  state.channelImages[state.activeChannelId] = {
    startImage: state.startImage,
    sourceImage: state.sourceImage,
    sourceImageName: state.sourceImageName,
    sourceImageSize: state.sourceImageSize,
  };
}

function loadActiveChannelImage(refresh = true) {
  const imageEpoch = state.imageRequestEpoch + 1;
  state.imageRequestEpoch = imageEpoch;
  state.imagePreparing = false;
  const saved = state.channelImages[state.activeChannelId] || {};
  state.startImage = saved.startImage || null;
  state.sourceImage = saved.sourceImage || null;
  state.sourceImageName = saved.sourceImageName || "";
  state.sourceImageSize = Number(saved.sourceImageSize || 0);
  if (refresh) refreshReferenceImage(false, state.activeChannelId, imageEpoch).catch(() => {});
}

function setKeyStatus(message, kind = "") {
  const node = $("#keyStatus");
  node.textContent = message;
  node.className = `key-status ${kind}`.trim();
}

async function verifyApiKey() {
  const apiKey = $("#apiKey").value.trim();
  if (!apiKey) {
    setKeyStatus("请先输入fal API Key", "error");
    return;
  }
  const button = $("#verifyKeyButton");
  button.disabled = true;
  button.textContent = "正在连接";
  setKeyStatus("正在安全验证连接…");
  state.keyVerified = false;
  updateStartEligibility();
  try {
    const result = await request("/api/key/check", {
      method: "POST",
      body: JSON.stringify({ api_key: apiKey }),
    });
    if (result.valid === false || result.ok === false) throw new Error(result.message || "密钥验证失败");
    state.keyVerified = true;
    state.verifiedKey = apiKey;
    const balanceText = result.balance && result.balance.current_balance !== null
      ? ` · 可用余额 ${money(result.balance.current_balance)}`
      : ` · ${result.balance_note || "请确认所属工作区有可用余额"}`;
    setKeyStatus(`密钥已验证，H3 Max连接正常${balanceText}`, "ok");
    toast("连接成功，可以开始连续生成");
  } catch (error) {
    state.verifiedKey = "";
    setKeyStatus(friendlyError(error.message, "无法验证密钥，请检查后重试"), "error");
  } finally {
    button.disabled = false;
    button.textContent = "连接并验证";
    updateStartEligibility();
  }
}

function renderClipGrid(total = 20, ready = 0, status = "") {
  const grid = $("#clipGrid");
  const safeTotal = Math.max(1, Number(total) || 1);
  const markerCount = Math.min(safeTotal, MAX_CLIP_MARKERS);
  const readyMarkers = Math.floor(Math.min(ready, safeTotal) / safeTotal * markerCount);
  const activeMarker = Math.min(markerCount - 1, Math.floor(Math.min(ready, safeTotal - 1) / safeTotal * markerCount));
  if (grid.children.length !== markerCount) {
    grid.innerHTML = "";
    for (let index = 0; index < markerCount; index += 1) {
      const marker = document.createElement("i");
      const start = Math.floor(index / markerCount * safeTotal) + 1;
      const end = Math.floor((index + 1) / markerCount * safeTotal);
      marker.title = start === end ? `第${start}幕` : `第${start}–${end}幕`;
      grid.append(marker);
    }
  }
  [...grid.children].forEach((node, index) => {
    node.className = index < readyMarkers ? "ready" : (index === activeMarker && ["preparing", "generating"].includes(status) ? "current" : "");
  });
  $("#clipSummary").textContent = `${Math.min(ready, safeTotal)} / ${safeTotal}幕`;
  grid.setAttribute("aria-label", `共${safeTotal}幕，已完成${Math.min(ready, safeTotal)}幕`);
}

function renderUnlimitedClipGrid(ready = 0, status = "") {
  const visibleTotal = Math.max(12, Math.min(MAX_CLIP_MARKERS, ready + 4));
  renderClipGrid(visibleTotal, ready, status);
  $("#clipSummary").textContent = `${ready}幕 · 持续播出`;
  $("#clipGrid").setAttribute("aria-label", `不限时节目，已完成${ready}幕`);
}

const generationTimingSources = {
  gpu_core: { short: "核心", label: "GPU核心推理" },
  fal_processing: { short: "FAL", label: "fal运行器处理" },
  result_ready: { short: "就绪", label: "本机提交至结果可读取" },
};

function floorGenerationTenth(raw) {
  if (raw === null || raw === "" || typeof raw === "boolean") return null;
  const seconds = Number(raw);
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  return Math.floor(seconds * 10) / 10;
}

function clipGenerationTiming(clip = {}) {
  const source = String(clip.generation_time_source || "");
  const preferred = floorGenerationTenth(clip.generation_time_seconds);
  if (source && source !== "unavailable" && preferred !== null) {
    return { seconds: preferred, source };
  }
  const legacy = Number(clip.generation_seconds);
  if (Number.isFinite(legacy) && legacy > 0) {
    return { seconds: floorGenerationTenth(legacy), source: "result_ready" };
  }
  return null;
}

function formatGenerationSeconds(seconds) {
  if (!Number.isFinite(seconds) || seconds < 0) return null;
  if (seconds < 0.1) return "<0.1秒";
  if (seconds < 60) return `${seconds.toFixed(1)}秒`;
  const minutes = Math.floor(seconds / 60);
  const remainder = (seconds - minutes * 60).toFixed(1).padStart(4, "0");
  return `${minutes}分${remainder}秒`;
}

function renderClipTimings(session = {}) {
  const clips = Array.isArray(session.clips) ? session.clips : [];
  const rows = clips.map((clip, index) => ({
    number: Number.isFinite(Number(clip.number)) ? Number(clip.number) : index + 1,
    timing: clipGenerationTiming(clip),
  }));
  const signature = `${session.session_id || "empty"}|${session.status || "idle"}|${rows
    .map((row) => `${row.number}:${row.timing?.seconds ?? "-"}:${row.timing?.source || "-"}`)
    .join("|")}`;
  const strip = $("#clipTimingStrip");
  const latest = $("#clipTimingLatest");
  if (strip.dataset.signature === signature) return;
  const previousCount = Number(strip.dataset.clipCount || 0);
  strip.replaceChildren();

  if (!rows.length) {
    const empty = document.createElement("span");
    empty.className = "clip-timing-empty";
    const preparing = ["preparing", "generating"].includes(session.status);
    empty.textContent = preparing ? "第1幕生成中…" : "每一幕完成后都会在这里留下用时";
    strip.append(empty);
    latest.textContent = preparing ? "第1幕生成中" : "等待第一幕";
  } else {
    rows.forEach((row) => {
      const source = generationTimingSources[row.timing?.source] || { short: "—", label: "未记录计时来源" };
      const formatted = row.timing ? formatGenerationSeconds(row.timing.seconds) : null;
      const item = document.createElement("span");
      item.className = `clip-timing-chip${formatted ? "" : " missing"}`;
      item.setAttribute("role", "listitem");
      item.title = formatted ? `${source.label}：${formatted}` : "这一幕没有可用计时记录";
      item.setAttribute("aria-label", `第${row.number}幕，${item.title}`);

      const number = document.createElement("small");
      number.textContent = `S${String(row.number).padStart(2, "0")}`;
      const value = document.createElement("b");
      value.textContent = formatted || "未记录";
      const scope = document.createElement("em");
      scope.textContent = source.short;
      item.append(number, value, scope);
      strip.append(item);
    });

    const last = rows.at(-1);
    const formatted = last.timing ? formatGenerationSeconds(last.timing.seconds) : null;
    const source = generationTimingSources[last.timing?.source];
    latest.textContent = formatted
      ? `第${last.number}幕 · ${formatted} · ${source?.short || "计时"}`
      : `第${last.number}幕 · 未记录`;

    if (rows.length > previousCount) {
      strip.lastElementChild?.classList.add("just-ready");
      requestAnimationFrame(() => { strip.scrollLeft = strip.scrollWidth; });
    }
  }

  strip.dataset.signature = signature;
  strip.dataset.clipCount = String(rows.length);
}

function publicStatus(status) {
  if (status === "complete") return ["done", "作品已完成"];
  if (status === "finalizing") return ["working", "正在合成"];
  if (["failed", "interrupted", "invalid"].includes(status)) return ["failed", "创作已中断"];
  if (status === "stopped") return ["idle", "已停止续写"];
  if (["preparing", "generating"].includes(status)) return ["working", "AI创作中"];
  return ["idle", "准备就绪"];
}

function publicProgressMessage(session) {
  const clips = session.clips || [];
  const total = session.config?.total_clips || 20;
  const unlimited = session.config?.duration_mode === "unlimited";
  if (session.status === "complete") return session.ready_to_download ? "作品已完成，请先播放检查动作逻辑" : "画面已完成，正在合成完整视频";
  if (session.status === "finalizing") return "全部画面已生成，正在合成完整视频";
  if (session.status === "stopped") return `已保存${clips.length}幕画面`;
  if (["failed", "interrupted", "invalid"].includes(session.status)) return "已完成的画面仍然保留";
  if (session.status === "preparing") return "正在准备第一幕";
  return unlimited ? `AI频道正在续写第${clips.length + 1}幕` : `AI正在续写第${Math.min(clips.length + 1, total)}幕`;
}

function estimateRemaining(session) {
  if (session.status === "complete") return 0;
  if (session.config?.duration_mode === "unlimited") return null;
  if (Number.isFinite(Number(session.eta_seconds))) return Math.max(0, Number(session.eta_seconds));
  const clips = session.clips || [];
  const total = session.config?.total_clips || 20;
  const recent = clips
    .map((clip) => Number(clip.generation_seconds))
    .filter((value) => Number.isFinite(value) && value > 0)
    .slice(-5);
  if (!recent.length) return null;
  const average = recent.reduce((sum, value) => sum + value, 0) / recent.length;
  return Math.max(0, total - clips.length) * average;
}

function nextSceneFor(session) {
  if (session.status === "complete") return "接缝已完成；动作与空间逻辑仍需播放确认";
  if (session.next_chapter) return session.next_chapter;
  if (session.next_scene) return session.next_scene;
  if (session.next_beat) return session.next_beat;
  const index = (session.clips || []).length % sceneBeats.length;
  return sceneBeats[index];
}

function friendlyError(message, fallback = "创作暂时中断，请稍后重试。已完成的内容仍然保留。") {
  const value = String(message || "").toLowerCase();
  if (value.includes("余额") || value.includes("balance")) return "fal账户余额不足，或这把Key所属的工作区尚未充值。";
  if (value.includes("budget") || value.includes("预算")) return "本地预计费用上限不符合要求，请调整后重试。";
  if (value.includes("api key") || value.includes("unauthorized") || value.includes("401") || value.includes("密钥")) return "API Key无效或没有可用权限，请检查后重试。";
  if (value.includes("safety") || value.includes("安全")) return "这段描述未通过内容安全检查，请调整画面描述。";
  if (value.includes("network") || value.includes("timeout") || value.includes("连接")) return "连接暂时不稳定，请稍后重试。";
  return fallback;
}

function finalDownloadUrl(session) {
  if (typeof session.download_url === "string") return session.download_url;
  if (typeof session.final_video_url === "string") return session.final_video_url;
  if (typeof session.final_url === "string") return session.final_url;
  if (session.final_video && typeof session.final_video.url === "string") return session.final_video.url;
  return `/download/${encodeURIComponent(session.session_id)}/video.mp4`;
}

function updateCompletionActions(session) {
  const complete = session.status === "complete";
  const ready = complete && session.ready_to_download !== false && session.finalizing !== true;
  const download = $("#downloadButton");
  const player = $("#playerButton");
  if (ready) {
    const url = finalDownloadUrl(session);
    download.href = url;
    const actualSeconds = session.config?.duration_mode === "unlimited"
      ? Number(session.generated_seconds || 0)
      : Number(session.target_seconds || session.config?.duration_seconds || state.durationSeconds);
    const durationLabel = formatDuration(actualSeconds).replaceAll(":", "-");
    const ratioLabel = (session.config?.aspect_ratio || state.aspectRatio).replace(":", "x");
    download.download = `FrameCurrent-连续影像-${durationLabel}-${ratioLabel}.mp4`;
    download.classList.remove("disabled");
    download.setAttribute("aria-disabled", "false");
    player.href = `/player.html?session=${encodeURIComponent(session.session_id)}`;
    player.classList.remove("disabled");
    player.setAttribute("aria-disabled", "false");
  } else {
    download.href = "#";
    player.href = "#";
    download.classList.add("disabled");
    player.classList.add("disabled");
    download.setAttribute("aria-disabled", "true");
    player.setAttribute("aria-disabled", "true");
  }
  if (complete && !ready) $("#progressMessage").textContent = "画面已完成，正在合成完整视频";
}

function updateMonitor(session) {
  state.latestSession = session;
  const clips = session.clips || [];
  const config = session.config || {};
  const unlimited = config.duration_mode === "unlimited";
  const target = unlimited ? null : Number(session.target_seconds || config.duration_seconds || state.durationSeconds || 300);
  if (config.aspect_ratio && config.aspect_ratio !== state.aspectRatio) applyAspectRatio(config.aspect_ratio, false);
  const generated = Number(session.generated_seconds || clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0));
  const percent = unlimited ? null : Math.min(100, Math.round((generated / target) * 100));
  const playableSeconds = clips.reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
  const totalClips = unlimited ? null : Number(config.total_clips || Math.ceil(target / Number(config.clip_duration || 10)));
  const maxBudgetValue = Number(config.max_budget_usd ?? session.max_budget_usd ?? 0);
  const maxBudget = Number.isFinite(maxBudgetValue) && maxBudgetValue > 0 ? maxBudgetValue : 0;
  const eta = estimateRemaining(session);

  $(".progress-track").classList.toggle("indeterminate", unlimited && ["preparing", "generating"].includes(session.status));
  $("#progressFill").style.width = unlimited ? "34%" : `${percent}%`;
  $("#progressPercent").textContent = unlimited ? "LIVE" : `${percent}%`;
  $("#progressMessage").textContent = publicProgressMessage(session);
  $("#generatedTime").textContent = unlimited ? `${formatDuration(generated)} · 持续播出` : `${formatDuration(generated)} / ${formatDuration(target)}`;
  $("#playableTime").textContent = formatDuration(playableSeconds);
  $("#etaTime").textContent = unlimited ? "手动停播" : (eta === null ? "计算中" : formatDuration(eta));
  $("#spentCost").textContent = maxBudget > 0
    ? `${money(session.spent_estimate_usd)} / ${money(maxBudget)}`
    : money(session.spent_estimate_usd);
  $("#nextScene").textContent = nextSceneFor(session);
  if (unlimited) renderUnlimitedClipGrid(clips.length, session.status);
  else renderClipGrid(totalClips, clips.length, session.status);
  renderClipTimings(session);

  const [className, label] = publicStatus(session.status);
  $("#monitorState").className = `monitor-state ${className}`;
  $("#monitorState").textContent = label;
  $("#liveBadge").classList.toggle("active", ["preparing", "generating"].includes(session.status));

  const errorBox = $("#monitorError");
  errorBox.hidden = !session.error;
  errorBox.textContent = session.error ? friendlyError(session.error) : "";
  $("#stopButton").disabled = !["preparing", "generating"].includes(session.status);
  syncChannelBadge(session);
  updateCompletionActions(session);
  syncPreview(session);

  if (terminalStatuses.has(session.status)) {
    state.busy = false;
    window.clearTimeout(state.pollTimer);
    updateStartEligibility();
    if (session.status === "complete") toast(`${formatDuration(unlimited ? generated : target)}作品已完成，请先播放检查动作逻辑`);
  } else {
    state.busy = true;
    updateStartEligibility();
  }
}

function resetPreview(sessionId = null) {
  const epoch = Number(state.preview?.epoch || 0) + 1;
  cancelAnimationFrame(state.preview.tickHandle);
  previewVideos.forEach((video) => {
    video.pause();
    video.removeAttribute("src");
    video.removeAttribute("data-clip-index");
    video.classList.remove("visible");
    video.load();
  });
  state.preview = {
    sessionId,
    clips: [],
    activeSlot: 0,
    activeClipIndex: -1,
    started: false,
    switching: false,
    waiting: false,
    syncing: false,
    tickHandle: null,
    epoch,
  };
  $("#stagePlaceholder").classList.remove("hidden");
  $("#previewCaption").hidden = true;
  $("#bufferNotice").hidden = true;
  $("#previewElapsed").textContent = "00:00";
}

function clipUrl(index) {
  return state.preview.clips[index]?.url || "";
}

function loadPreviewSlot(slot, clipIndex) {
  const video = previewVideos[slot];
  const url = clipUrl(clipIndex);
  if (!url) return Promise.reject(new Error("画面尚未就绪"));
  if (Number(video.dataset.clipIndex) === clipIndex && video.readyState >= 2) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const onReady = () => { cleanup(); resolve(); };
    const onError = () => { cleanup(); reject(new Error("预览画面暂时无法读取")); };
    const cleanup = () => {
      video.removeEventListener("loadeddata", onReady);
      video.removeEventListener("error", onError);
    };
    video.pause();
    video.classList.remove("visible");
    video.src = url;
    video.dataset.clipIndex = String(clipIndex);
    video.currentTime = 0;
    video.addEventListener("loadeddata", onReady, { once: true });
    video.addEventListener("error", onError, { once: true });
    video.load();
  });
}

async function startPreview() {
  if (state.preview.started || state.preview.clips.length < 1 || state.preview.syncing) return;
  const epoch = state.preview.epoch;
  state.preview.syncing = true;
  try {
    await loadPreviewSlot(0, 0);
    if (state.preview.epoch !== epoch) return;
    if (state.preview.clips.length > 1) await loadPreviewSlot(1, 1);
    if (state.preview.epoch !== epoch) return;
    state.preview.activeSlot = 0;
    state.preview.activeClipIndex = 0;
    const first = previewVideos[0];
    first.classList.add("visible");
    await first.play();
    if (state.preview.epoch !== epoch) {
      first.pause();
      first.classList.remove("visible");
      return;
    }
    state.preview.started = true;
    state.preview.waiting = false;
    $("#stagePlaceholder").classList.add("hidden");
    $("#previewCaption").hidden = false;
    $("#bufferNotice").hidden = true;
    updatePreviewClock();
  } catch (_) {
    if (state.preview.epoch !== epoch) return;
    $("#stagePlaceholder h3").textContent = "画面正在缓冲";
    $("#stagePlaceholder p").textContent = "AI完成下一幕后会自动继续。";
  } finally {
    if (state.preview.epoch === epoch) state.preview.syncing = false;
  }
}

async function advancePreview() {
  if (!state.preview.started || state.preview.switching) return;
  const epoch = state.preview.epoch;
  const nextIndex = state.preview.activeClipIndex + 1;
  if (nextIndex >= state.preview.clips.length) {
    state.preview.waiting = true;
    const complete = state.latestSession?.status === "complete";
    $("#bufferNotice").textContent = complete ? "实时预览已到作品结尾，可播放完整视频" : "AI正在准备下一幕，画面会从这里继续";
    $("#bufferNotice").hidden = false;
    return;
  }

  state.preview.switching = true;
  try {
    const oldSlot = state.preview.activeSlot;
    const nextSlot = 1 - oldSlot;
    await loadPreviewSlot(nextSlot, nextIndex);
    const oldVideo = previewVideos[oldSlot];
    const nextVideo = previewVideos[nextSlot];
    nextVideo.currentTime = 0;
    await nextVideo.play();
    if (state.preview.epoch !== epoch) {
      nextVideo.pause();
      nextVideo.classList.remove("visible");
      return;
    }
    nextVideo.classList.add("visible");
    oldVideo.classList.remove("visible");
    oldVideo.pause();
    state.preview.activeSlot = nextSlot;
    state.preview.activeClipIndex = nextIndex;
    state.preview.waiting = false;
    $("#bufferNotice").hidden = true;

    const preloadIndex = nextIndex + 1;
    if (preloadIndex < state.preview.clips.length) loadPreviewSlot(oldSlot, preloadIndex).catch(() => {});
  } catch (_) {
    if (state.preview.epoch !== epoch) return;
    state.preview.waiting = true;
    $("#bufferNotice").textContent = "AI正在准备下一幕，画面会从这里继续";
    $("#bufferNotice").hidden = false;
  } finally {
    if (state.preview.epoch === epoch) state.preview.switching = false;
  }
}

async function syncPreview(session) {
  if (state.preview.sessionId !== session.session_id) resetPreview(session.session_id);
  state.preview.clips = session.clips || [];
  const minimumBuffer = ["finalizing", "complete", "stopped"].includes(session.status) ? 1 : 2;
  if (!state.preview.started && state.preview.clips.length >= minimumBuffer) {
    await startPreview();
    return;
  }
  if (state.preview.started && state.preview.waiting && state.preview.activeClipIndex + 1 < state.preview.clips.length) {
    await advancePreview();
  }
}

function updatePreviewClock() {
  if (!state.preview.started) return;
  const current = previewVideos[state.preview.activeSlot];
  const completed = state.preview.clips
    .slice(0, state.preview.activeClipIndex)
    .reduce((sum, clip) => sum + Number(clip.duration || 0), 0);
  const elapsed = completed + Number(current.currentTime || 0);
  $("#previewElapsed").textContent = formatDuration(elapsed);
  $("#previewClip").textContent = `第${state.preview.activeClipIndex + 1}幕`;
  state.preview.tickHandle = requestAnimationFrame(updatePreviewClock);
}

previewVideos.forEach((video) => {
  video.addEventListener("timeupdate", () => {
    if (video !== previewVideos[state.preview.activeSlot] || state.preview.switching || !state.preview.started) return;
    if (video.duration && video.currentTime >= video.duration - 0.06) advancePreview();
  });
  video.addEventListener("ended", () => {
    if (video === previewVideos[state.preview.activeSlot]) advancePreview();
  });
});

function rememberSession(channelId, sessionId) {
  state.channelSessions[channelId] = sessionId;
  persistSessionMap();
}

function persistSessionMap() {
  try {
    window.localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(state.channelSessions));
  } catch (_) {
    // The running page still keeps the session in memory when storage is unavailable.
  }
}

function recalledSessions() {
  try {
    const raw = window.localStorage.getItem(SESSION_STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) return parsed;
    const legacy = window.localStorage.getItem(LEGACY_SESSION_STORAGE_KEY);
    return legacy ? { hand_drawn_fantasy: legacy } : {};
  } catch (_) {
    return {};
  }
}

function recalledPendingStarts() {
  try {
    const parsed = JSON.parse(window.localStorage.getItem(PENDING_STARTS_STORAGE_KEY) || "null");
    return parsed && typeof parsed === "object" && !Array.isArray(parsed) ? parsed : {};
  } catch (_) {
    return {};
  }
}

function persistPendingStarts() {
  try { window.localStorage.setItem(PENDING_STARTS_STORAGE_KEY, JSON.stringify(state.pendingRequestIds)); } catch (_) { /* no-op */ }
}

function createRequestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  const bytes = new Uint8Array(16);
  if (globalThis.crypto?.getRandomValues) globalThis.crypto.getRandomValues(bytes);
  else for (let index = 0; index < bytes.length; index += 1) bytes[index] = Math.floor(Math.random() * 256);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = [...bytes].map((value) => value.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

function payloadFingerprint(payload) {
  const safePayload = { ...payload };
  delete safePayload.api_key;
  delete safePayload.client_request_id;
  const source = JSON.stringify(safePayload);
  let first = 0x811c9dc5;
  let second = 0x9e3779b1;
  for (let index = 0; index < source.length; index += 1) {
    const code = source.charCodeAt(index);
    first = Math.imul(first ^ code, 0x01000193);
    second = Math.imul(second ^ code, 0x85ebca6b);
  }
  return `${(first >>> 0).toString(16).padStart(8, "0")}${(second >>> 0).toString(16).padStart(8, "0")}:${source.length}`;
}

function pendingStartEntry(channelId, fingerprint) {
  const saved = state.pendingRequestIds[channelId];
  let entry;
  const existing = Boolean(saved);
  const legacy = typeof saved === "string";
  if (legacy) entry = { id: saved, fingerprint: "" };
  else if (saved?.id) entry = saved;
  else entry = { id: createRequestId(), fingerprint };
  const mismatch = Boolean(existing && (!entry.fingerprint || entry.fingerprint !== fingerprint));
  if (!existing && !entry.fingerprint) entry.fingerprint = fingerprint;
  state.pendingRequestIds[channelId] = entry;
  persistPendingStarts();
  return { id: entry.id, mismatch, existing };
}

function clearPendingStart(channelId) {
  delete state.pendingRequestIds[channelId];
  persistPendingStarts();
}

function resetMonitorForChannel() {
  window.clearTimeout(state.pollTimer);
  state.sessionId = null;
  state.latestSession = null;
  state.busy = false;
  resetPreview();
  $("#monitorState").className = "monitor-state idle";
  $("#monitorState").textContent = "准备就绪";
  $("#liveBadge").classList.remove("active");
  $("#stagePlaceholder h3").textContent = "频道尚未开播";
  $("#stagePlaceholder p").textContent = state.activeChannelId === "custom_channel"
    ? "完成节目设置与开播设置后按“开播这个频道”。"
    : "完成开播设置后按“开播这个频道”。";
  $("#progressFill").style.width = "0%";
  $(".progress-track").classList.remove("indeterminate");
  $("#progressPercent").textContent = state.durationMode === "unlimited" ? "LIVE" : "0%";
  $("#progressMessage").textContent = "等待频道开播";
  $("#generatedTime").textContent = state.durationMode === "unlimited" ? "00:00 · 持续播出" : `00:00 / ${formatDuration(state.durationSeconds)}`;
  $("#playableTime").textContent = "00:00";
  $("#etaTime").textContent = state.durationMode === "unlimited" ? "手动停播" : "—";
  $("#spentCost").textContent = "$0.00";
  if (state.durationMode === "unlimited") renderUnlimitedClipGrid(0, "");
  else renderClipGrid(plannedClipCount(), 0, "");
  renderClipTimings({ clips: [], status: "idle" });
  updateCompletionActions({ status: "idle" });
  $("#stopButton").disabled = true;
  $("#monitorError").hidden = true;
  updateStartEligibility();
}

function syncChannelBadge(session) {
  const channelId = session?.config?.preset || state.activeChannelId;
  const card = document.querySelector(`[data-preset="${channelId}"]`);
  if (!card) return;
  card.classList.toggle("broadcasting", ["preparing", "generating", "finalizing"].includes(session?.status));
}

async function loadChannelSession(channelId) {
  const restoreEpoch = state.restoreEpoch + 1;
  state.restoreEpoch = restoreEpoch;
  const savedSessionId = state.channelSessions[channelId];
  if (!savedSessionId) {
    state.restoring = false;
    if (state.activeChannelId === channelId) resetMonitorForChannel();
    return;
  }
  state.restoring = true;
  if (state.activeChannelId === channelId) {
    $("#monitorState").className = "monitor-state working";
    $("#monitorState").textContent = "正在调台";
    $("#progressMessage").textContent = "正在恢复这个频道的节目";
    updateStartEligibility();
  }
  try {
    const session = await request(`/api/session/${encodeURIComponent(savedSessionId)}`);
    if (state.restoreEpoch !== restoreEpoch || state.activeChannelId !== channelId || state.channelSessions[channelId] !== savedSessionId) return;
    const actualChannelId = session.config?.preset;
    if (!presetProfiles[actualChannelId] || actualChannelId !== channelId) {
      delete state.channelSessions[channelId];
      if (presetProfiles[actualChannelId] && !state.channelSessions[actualChannelId]) {
        state.channelSessions[actualChannelId] = savedSessionId;
      }
      persistSessionMap();
      resetMonitorForChannel();
      toast(presetProfiles[actualChannelId]
        ? `历史节目已归回“${presetProfiles[actualChannelId].name}”频道`
        : "这条历史节目不属于当前可用频道，已停止恢复");
      return;
    }
    if (!state.channelDrafts[channelId]) {
      const config = session.config || {};
      $("#subjectLock").value = config.subject_lock || $("#subjectLock").value;
      $("#sceneSetting").value = config.scene_setting || $("#sceneSetting").value;
      $("#concept").value = config.story_action || $("#concept").value;
      $("#cameraMotion").value = config.camera_direction || $("#cameraMotion").value;
      $("#avoidContent").value = config.avoid_content || $("#avoidContent").value;
      if (channelId === "custom_channel") {
        $("#customChannelName").value = config.custom_channel_name || config.preset_name || $("#customChannelName").value;
        $("#customChannelStyle").value = config.custom_channel_style || $("#customChannelStyle").value;
      }
      saveActiveChannelDraft();
      updateBriefSummary();
    }
    const durationMode = session.config?.duration_mode === "unlimited" ? "unlimited" : "fixed";
    applyDurationMode(durationMode);
    const restoredDuration = Number(session.target_seconds || session.config?.duration_seconds);
    if (durationMode === "fixed" && (!Number.isInteger(restoredDuration) || restoredDuration < MIN_DURATION_SECONDS || restoredDuration > MAX_DURATION_SECONDS)) {
      throw new Error("作品时长不匹配");
    }
    if (durationMode === "fixed") {
      state.durationSeconds = restoredDuration;
      state.durationValid = true;
      $("#durationMinutes").value = String(Math.floor(restoredDuration / 60));
      $("#durationSeconds").value = String(restoredDuration % 60);
      updateDuration();
    }
    applyAspectRatio(session.config?.aspect_ratio || "16:9", false);
    state.sessionId = session.session_id;
    updateMonitor(session);
    if (!terminalStatuses.has(session.status)) pollSession();
  } catch (error) {
    if (state.restoreEpoch !== restoreEpoch) return;
    if (error.status === 404) {
      delete state.channelSessions[channelId];
      persistSessionMap();
    }
    if (state.activeChannelId === channelId) {
      resetMonitorForChannel();
      if (error.status !== 404) {
        $("#monitorError").hidden = false;
        $("#monitorError").textContent = "暂时无法恢复这个频道，任务记录仍已保留。服务恢复后重新选择该频道即可继续查看。";
      }
    }
  } finally {
    if (state.restoreEpoch === restoreEpoch && state.activeChannelId === channelId) {
      state.restoring = false;
      updateStartEligibility();
    }
  }
}

async function restoreCurrentSession() {
  state.channelSessions = recalledSessions();
  await loadChannelSession(state.activeChannelId);
}

async function pollSession() {
  if (!state.sessionId) return;
  const sessionId = state.sessionId;
  const channelId = state.activeChannelId;
  try {
    const session = await request(`/api/session/${encodeURIComponent(sessionId)}`);
    if (state.sessionId !== sessionId || state.activeChannelId !== channelId) return;
    updateMonitor(session);
    if (!terminalStatuses.has(session.status)) {
      state.pollTimer = window.setTimeout(pollSession, 700);
    }
  } catch (error) {
    if (state.sessionId !== sessionId || state.activeChannelId !== channelId) return;
    $("#monitorError").hidden = false;
    $("#monitorError").textContent = friendlyError(error.message, "暂时无法更新创作进度，正在自动重连。已完成的内容不会丢失。");
    if (state.sessionId === sessionId && state.activeChannelId === channelId) state.pollTimer = window.setTimeout(pollSession, 1800);
  }
}

function requestPaidStartConfirmation() {
  const dialog = $("#paidDialog");
  const budgetField = $("#paidDialogBudgetField");
  const budgetInput = $("#confirmMaxBudget");
  const confirmButton = $("#confirmPaidStart");
  const closeButtons = [$("#cancelPaidDialog"), $("#backPaidDialog")];
  const rate = $("#resolution").value === "768P" ? 0.08 : 0.05;
  const resolution = $("#resolution").value;
  const clipDuration = Number($("#clipDuration").value || 10);
  const unlimited = state.durationMode === "unlimited";
  const minimumBudget = Number((clipDuration * rate).toFixed(2));
  const fixedBudget = Number(estimatedCost().toFixed(2));
  const floorBudgetCents = (value) => Math.floor(Number(value) * 100 + 1e-9) / 100;

  $("#paidDialogMode").textContent = unlimited ? "参考生成费率" : "本次预计费用";
  $("#paidDialogCost").textContent = unlimited ? `${money(rate * 60)} / 分钟` : money(fixedBudget);
  $("#paidDialogDetail").textContent = unlimited
    ? `${resolution} · 持续至手动停止或达到下方上限`
    : `${formatDuration(state.durationSeconds)} · ${resolution} · ${money(rate)}/秒`;
  budgetField.hidden = !unlimited;
  budgetInput.min = minimumBudget.toFixed(2);
  budgetInput.max = MAX_LOCAL_ESTIMATED_BUDGET_USD.toFixed(2);
  budgetInput.value = unlimited ? "" : fixedBudget.toFixed(2);
  $("#paidDialogBudgetHelp").textContent = `可填 ${money(minimumBudget)}–${money(MAX_LOCAL_ESTIMATED_BUDGET_USD)}；达到上限后停止提交新画面。这不是 fal 最终账单保证。`;

  const syncConfirmButton = () => {
    const budget = unlimited ? floorBudgetCents(budgetInput.value) : fixedBudget;
    const valid = Number.isFinite(budget)
      && budget > 0
      && budget <= MAX_LOCAL_ESTIMATED_BUDGET_USD
      && (!unlimited || budget >= minimumBudget);
    budgetInput.setCustomValidity(!unlimited || valid ? "" : `请输入 ${money(minimumBudget)}–${money(MAX_LOCAL_ESTIMATED_BUDGET_USD)} 之间的本地预计费用上限`);
    confirmButton.disabled = !valid;
    confirmButton.textContent = valid
      ? `确认并开播 · ${unlimited ? `本地上限 ${money(budget)}` : money(budget)}`
      : "请输入有效预算";
  };
  syncConfirmButton();

  if (typeof dialog.showModal !== "function") {
    let approvedBudget = fixedBudget;
    if (unlimited) {
      const rawBudget = window.prompt(`请输入本次不限时节目的本地预计费用上限（USD，最高 ${money(MAX_LOCAL_ESTIMATED_BUDGET_USD)}）`, "");
      if (rawBudget === null) return Promise.resolve(null);
      approvedBudget = floorBudgetCents(rawBudget);
      if (!Number.isFinite(approvedBudget) || approvedBudget < minimumBudget || approvedBudget > MAX_LOCAL_ESTIMATED_BUDGET_USD) {
        toast(`本地预计费用上限需在 ${money(minimumBudget)}–${money(MAX_LOCAL_ESTIMATED_BUDGET_USD)} 之间`);
        return Promise.resolve(null);
      }
    }
    const approved = window.confirm(`确认后将向 fal 提交付费生成，本次${unlimited ? "本地预计费用上限" : "预计费用"} ${money(approvedBudget)}。该数值不是 fal 最终账单保证。是否开播？`);
    return Promise.resolve(approved ? approvedBudget : null);
  }

  return new Promise((resolve) => {
    let approvedBudget = null;
    const closeDialog = () => dialog.close("cancelled");
    const confirmStart = () => {
      const budget = unlimited ? floorBudgetCents(budgetInput.value) : fixedBudget;
      if (
        !Number.isFinite(budget)
        || budget <= 0
        || budget > MAX_LOCAL_ESTIMATED_BUDGET_USD
        || (unlimited && budget < minimumBudget)
      ) {
        budgetInput.reportValidity();
        return;
      }
      approvedBudget = budget;
      dialog.close("confirmed");
    };
    const preventSubmit = (event) => {
      event.preventDefault();
      confirmStart();
    };
    const closeFromBackdrop = (event) => {
      if (event.target === dialog) closeDialog();
    };
    const finish = () => {
      budgetInput.removeEventListener("input", syncConfirmButton);
      confirmButton.removeEventListener("click", confirmStart);
      dialog.querySelector("form").removeEventListener("submit", preventSubmit);
      dialog.removeEventListener("click", closeFromBackdrop);
      closeButtons.forEach((button) => button.removeEventListener("click", closeDialog));
      resolve(dialog.returnValue === "confirmed" ? approvedBudget : null);
    };

    budgetInput.addEventListener("input", syncConfirmButton);
    confirmButton.addEventListener("click", confirmStart);
    dialog.querySelector("form").addEventListener("submit", preventSubmit);
    dialog.addEventListener("click", closeFromBackdrop);
    closeButtons.forEach((button) => button.addEventListener("click", closeDialog));
    dialog.addEventListener("close", finish, { once: true });
    dialog.returnValue = "";
    dialog.showModal();
    (unlimited ? budgetInput : confirmButton).focus();
  });
}

async function startSession(event) {
  event.preventDefault();
  const unresolvedSession = Boolean(
    state.channelSessions[state.activeChannelId]
    && state.sessionId !== state.channelSessions[state.activeChannelId]
  );
  if (state.busy || state.starting || state.restoring || state.imagePreparing || unresolvedSession) return;
  if (state.durationMode === "fixed" && !state.durationValid) {
    toast("请先设置10秒到30分钟之间的创作时长");
    return;
  }
  if (!$("#subjectLock").value.trim()) {
    toast("请先告诉AI画面的主角或主体是什么");
    $("#subjectLock").focus();
    return;
  }
  if (!$("#sceneSetting").value.trim()) {
    toast("请先告诉AI这个世界发生在哪里");
    $("#sceneSetting").focus();
    return;
  }
  const apiKey = $("#apiKey").value.trim();
  if (!state.keyVerified || apiKey !== state.verifiedKey) {
    setKeyStatus("请重新连接并验证当前密钥", "error");
    updateStartEligibility();
    return;
  }

  state.starting = true;
  state.paymentDialogOpen = true;
  updateStartEligibility();
  let approvedBudget = null;
  try {
    approvedBudget = await requestPaidStartConfirmation();
  } catch (_) {
    toast("费用确认窗口暂时无法打开，请刷新页面后重试");
  }
  state.paymentDialogOpen = false;
  if (approvedBudget === null) {
    state.starting = false;
    updateStartEligibility();
    return;
  }

  const clipDuration = Number($("#clipDuration").value);
  const channelId = state.activeChannelId;
  const payload = {
    duration_mode: state.durationMode,
    duration_seconds: state.durationMode === "fixed" ? state.durationSeconds : null,
    clip_duration: clipDuration,
    resolution: $("#resolution").value,
    aspect_ratio: state.aspectRatio,
    preset: $("#preset").value,
    custom_channel_name: state.activeChannelId === "custom_channel" ? $("#customChannelName").value.trim() : "",
    custom_channel_style: state.activeChannelId === "custom_channel" ? $("#customChannelStyle").value.trim() : "",
    concept: creatorConcept(),
    subject_lock: $("#subjectLock").value.trim(),
    scene_setting: $("#sceneSetting").value.trim(),
    story_action: $("#concept").value.trim(),
    camera_direction: $("#cameraMotion").value,
    avoid_content: $("#avoidContent").value.trim(),
    start_image: channelId === "custom_channel" ? state.startImage : null,
    max_budget_usd: approvedBudget,
    api_key: apiKey,
    paid_confirmed: true,
  };
  const pendingStart = pendingStartEntry(channelId, payloadFingerprint(payload));
  payload.client_request_id = pendingStart.id;

  try {
    state.busy = true;
    updateStartEligibility();
    resetPreview();
    $("#monitorState").className = "monitor-state working";
    $("#monitorState").textContent = "AI创作中";
    $("#progressMessage").textContent = "正在准备第一幕";
    $("#liveBadge").classList.add("active");
    $("#stagePlaceholder h3").textContent = "AI正在创作第一幕";
    $("#stagePlaceholder p").textContent = "准备好两幕缓冲后自动开始连续预览。";
    if (state.durationMode === "unlimited") renderUnlimitedClipGrid(0, "preparing");
    else renderClipGrid(buildSchedule(state.durationSeconds, clipDuration).length, 0, "preparing");
    renderClipTimings({ session_id: "pending", clips: [], status: "preparing" });
    const result = await request("/api/session/start", { method: "POST", body: JSON.stringify(payload) });
    const sessionId = result.session.session_id;
    const recoveredEarlierSettings = Boolean(result.idempotent_replay && pendingStart.mismatch);
    clearPendingStart(channelId);
    rememberSession(channelId, sessionId);
    $("#apiKey").value = "";
    state.verifiedKey = "";
    state.keyVerified = false;
    setKeyStatus("任务已启动，密钥已从页面清除", "ok");
    if (state.activeChannelId !== channelId) return;
    state.sessionId = sessionId;
    resetPreview(sessionId);
    updateMonitor(result.session);
    if (recoveredEarlierSettings) {
      $("#monitorError").hidden = false;
      $("#monitorError").textContent = "已找回上一次结果未确认的开播任务；你刚修改的设置没有再次提交，也没有产生第二个任务。";
      toast("已安全找回上一次开播任务，本次修改未重复提交");
    }
    pollSession();
    $("#monitorPanel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    if (!pendingStart.existing && Number(error.status) >= 400 && Number(error.status) < 500 && Number(error.status) !== 409) clearPendingStart(channelId);
    if (state.activeChannelId === channelId) {
      state.busy = false;
      $("#monitorState").className = "monitor-state failed";
      $("#monitorState").textContent = "无法开始";
      $("#liveBadge").classList.remove("active");
      $("#monitorError").hidden = false;
      $("#monitorError").textContent = friendlyError(error.message, "暂时无法开始连续生成，请稍后重试。");
    }
    const uncertain = !error.status || Number(error.status) >= 500;
    toast(uncertain ? "开播结果暂时未知；再次点击会安全查询同一次任务，不会重复创建" : friendlyError(error.message, "暂时无法开始，请稍后重试"));
  } finally {
    state.starting = false;
    updateStartEligibility();
  }
}

async function stopSession() {
  if (!state.sessionId) return;
  if (!window.confirm("停止后不会再提交新画面。已经提交的一幕仍可能完成并计费，是否停止续写？")) return;
  const sessionId = state.sessionId;
  const channelId = state.activeChannelId;
  try {
    $("#stopButton").disabled = true;
    const result = await request(`/api/session/${encodeURIComponent(sessionId)}/stop`, { method: "POST", body: "{}" });
    if (state.sessionId === sessionId && state.activeChannelId === channelId) updateMonitor(result.session);
  } catch (error) {
    toast(friendlyError(error.message, "暂时无法停止，请稍后重试"));
    if (state.sessionId === sessionId && state.activeChannelId === channelId) $("#stopButton").disabled = false;
  }
}

function readImage(file) {
  if (!file) return;
  const channelId = state.activeChannelId;
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) {
    toast("请选择JPG、PNG或WebP图片");
    return;
  }
  if (file.size > 12 * 1024 * 1024) {
    toast("参考图请控制在12MB以内");
    return;
  }
  const imageEpoch = state.imageRequestEpoch + 1;
  state.imageRequestEpoch = imageEpoch;
  state.imagePreparing = true;
  state.startImage = null;
  state.sourceImage = null;
  state.sourceImageName = "";
  state.sourceImageSize = 0;
  $("#imagePreview").removeAttribute("src");
  $("#imagePreview").style.display = "none";
  $("#removeImage").hidden = true;
  $("#uploadText").textContent = `正在读取 ${file.name}…`;
  saveActiveChannelImage();
  updateStartEligibility();
  const reader = new FileReader();
  reader.onload = async () => {
    if (state.activeChannelId !== channelId || state.imageRequestEpoch !== imageEpoch) return;
    state.sourceImage = reader.result;
    state.sourceImageName = file.name;
    state.sourceImageSize = file.size;
    try {
      await refreshReferenceImage(false, channelId, imageEpoch);
      if (state.activeChannelId !== channelId || state.imageRequestEpoch !== imageEpoch) return;
      saveActiveChannelImage();
      toast("参考图已准备好");
    } catch (error) {
      if (state.activeChannelId === channelId && state.imageRequestEpoch === imageEpoch) {
        removeReferenceImage();
        toast(error.message || "参考图无法读取");
      }
    } finally {
      if (state.activeChannelId === channelId && state.imageRequestEpoch === imageEpoch) {
        state.imagePreparing = false;
        updateStartEligibility();
      }
    }
  };
  reader.onerror = () => {
    if (state.activeChannelId !== channelId || state.imageRequestEpoch !== imageEpoch) return;
    removeReferenceImage();
    toast("参考图无法读取");
  };
  reader.readAsDataURL(file);
}

function removeReferenceImage() {
  state.imageRequestEpoch += 1;
  state.imagePreparing = false;
  state.startImage = null;
  state.sourceImage = null;
  state.sourceImageName = "";
  state.sourceImageSize = 0;
  $("#startImage").value = "";
  refreshReferenceImage(false).catch(() => {});
  saveActiveChannelImage();
  updateStartEligibility();
}

document.querySelectorAll("[data-duration]").forEach((button) => {
  button.addEventListener("click", () => setDurationInputs(Number(button.dataset.duration)));
});
$("#durationMinutes").addEventListener("input", updateDuration);
$("#durationSeconds").addEventListener("input", updateDuration);
document.querySelectorAll('input[name="aspectRatio"]').forEach((input) => {
  input.addEventListener("change", () => {
    applyAspectRatio(input.value);
    saveActiveChannelDraft();
  });
});
document.querySelectorAll('input[name="durationMode"]').forEach((input) => {
  input.addEventListener("change", () => applyDurationMode(input.value));
});
document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => selectChannel(button.dataset.preset));
});
$("#customChannelName").addEventListener("input", () => {
  if (state.activeChannelId !== "custom_channel") return;
  const name = $("#customChannelName").value.trim() || "自定义频道";
  const cardTitle = document.querySelector('[data-preset="custom_channel"] .channel-copy b');
  if (cardTitle) cardTitle.textContent = name;
  $("#selectedChannelName").textContent = name;
  $("#playerChannelName").textContent = `CH ＋ · ${name}`;
  $("#stationChannelLabel").textContent = `CH ＋ · ${name}`;
  saveActiveChannelDraft();
});
$("#customChannelStyle").addEventListener("input", saveActiveChannelDraft);
$("#subjectLock").addEventListener("input", () => {
  state.subjectEdited = true;
  updateBriefSummary();
  updateStartEligibility();
  if (state.activeChannelId === "custom_channel") saveActiveChannelDraft();
});
$("#sceneSetting").addEventListener("input", () => {
  state.sceneEdited = true;
  updateBriefSummary();
  updateStartEligibility();
  if (state.activeChannelId === "custom_channel") saveActiveChannelDraft();
});
$("#concept").addEventListener("input", () => {
  state.actionEdited = true;
  if (state.activeChannelId === "custom_channel") saveActiveChannelDraft();
});
$("#cameraMotion").addEventListener("change", () => {
  state.cameraEdited = true;
  updateBriefSummary();
  if (state.activeChannelId === "custom_channel") saveActiveChannelDraft();
});
$("#avoidContent").addEventListener("input", () => {
  state.avoidEdited = true;
  if (state.activeChannelId === "custom_channel") saveActiveChannelDraft();
});
$("#clipDuration").addEventListener("change", () => {
  if (state.durationMode === "unlimited") {
    updateCost();
    if (!state.sessionId) renderUnlimitedClipGrid(0, "");
  } else {
    updateDuration();
  }
});
$("#resolution").addEventListener("change", updateCost);
$("#startImage").addEventListener("change", (event) => readImage(event.target.files[0]));
$("#removeImage").addEventListener("click", () => {
  removeReferenceImage();
  toast("参考图已移除");
});
$("#apiKey").addEventListener("input", () => {
  if ($("#apiKey").value.trim() === state.verifiedKey && state.verifiedKey) return;
  state.keyVerified = false;
  setKeyStatus("密钥有变化，请重新连接并验证");
  updateStartEligibility();
});
$("#verifyKeyButton").addEventListener("click", verifyApiKey);
$("#configForm").addEventListener("submit", startSession);
$("#stopButton").addEventListener("click", stopSession);

checkHealth();
state.channelDrafts = recalledChannelDrafts();
state.pendingRequestIds = recalledPendingStarts();
selectChannel("hand_drawn_fantasy", false);
applyDurationMode("fixed");
applyAspectRatio("16:9", false);
updateDuration();
updateStartEligibility();
restoreCurrentSession();
