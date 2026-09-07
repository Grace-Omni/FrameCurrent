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
const DIRECTOR_SCENE_ALLOWANCE_USD = 0.04;

const state = {
  durationSeconds: 30,
  serverStatus: "checking",
  activeGeneration: null,
  healthChecking: false,
  initialized: false,
  durationValid: true,
  durationMode: "fixed",
  activeChannelId: "hand_drawn_fantasy",
  channelSessions: {},
  channelDrafts: {},
  pendingRequestIds: {},
  reconcilingStarts: {},
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
  showcase: { active: false, epoch: 0 },
  preview: {
    enabled: false,
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
    "number": "CH 01",
    "name": "日系手绘奇幻",
    "revision": "windmeadow-v1",
    "subject": "一位七八岁的小女孩，栗棕齐下巴短发、系陶红丝带的草帽、淡奶油黄短袖及膝夏裙、鼠尾草绿腰带、象牙白短袜和棕色便鞋；自然儿童身材约五头身，全身可见，占画面高度约四分之一，脸型、服装与身高始终一致；一只圆脸橘白宠物猫在她侧后方相伴，橘色虎斑背耳、白色口鼻胸腹和四爪、微弯橘尾，肩高约到孩子小腿，猫与孩子保持清楚间距",
    "scene": "晴朗夏日上午的一片连绵青绿花草地，白色雏菊与少量淡粉野花、远处小巧红瓦奶油白农舍和蓝天中的奶油白积云；草地上有一条平缓、开阔的低草小径，近处细腻、中景清晰、远山柔和，纯手绘水彩背景",
    "action": "治愈唯美的日系手绘动画；孩子与宠物的目标、发现和情绪随机演进，出现明显的新事件与反转，保持温暖基调，不指定事件顺序或结局",
    "camera": "儿童视线略高的中远景平行跟拍，女孩通常全身可见、约占画面高度四分之一，脚下留出草地；镜头随追逐、减速、跪下与互动平缓调整，地平线水平，不突然推近、不环绕、不升空",
    "avoid": "不要湖泊、河流、积水、倒影、小船或船篷；不要成人身形、巨人比例、大头娃娃、多人、多余肢体、换脸换装、脚底悬浮或滑步；不要文字Logo、3D塑料质感、写实真人、黄褐滤镜、狂奔跳跃、快速运镜或突然换景；不要巨型宠物、猫的花色变化、宠物复制、猫钻到孩子脚下或肢体交叠",
    "hint": "日系手绘与夏日奇幻。小女孩和橘白猫的故事，由 AI 此刻展开。"
  },
  cinematic_scifi: {
    number: "CH 02",
    name: "科幻史诗电影",
    revision: "time-crystal-canyon-v1",
    subject: "一位独行的成年时间勘探者，深炭灰兜帽长斗篷、黑色旅行靴和顶端发出微弱青光的细长手杖始终一致；人物从背后可辨认，比例自然，不出现第二位主角",
    scene: "一条潮湿的黑色岩石峡谷，原位矗立着多根透明时间晶体：翠绿春林、明亮夏空、橙红秋林和冰雪寒冬分别封存在不同晶体中；峭壁、路径、晶体位置与风暴天空保持连续",
    action: "电影级科幻冒险；探索未知规则、改变认知与目标，随机产生具有因果关系的重大事件和反转，不预设危机类型与结局",
    camera: "电影级中远景后方跟拍，以湿润路径为轴缓慢推进；随着事件升级逐步抬升或侧移揭示晶体尺度，但保持人物方向、地形关系和镜头轴线连续",
    avoid: "不要飞船、城市、枪战或额外主角；不要晶体、手杖或人物复制变形；不要随机换峡谷、瞬移季节、无因爆炸、硬切、快速甩镜、文字Logo、字幕、界面或水印",
    hint: "电影级科幻世界，未知的规则与惊人的发现，正在生成。",
  },
  studio_variety: {
    number: "CH 03",
    name: "高能棚内综艺",
    revision: "mechanical-moon-stage-v1",
    subject: "一位成年女歌手，深色齐肩卷发、白色羽饰高级定制长礼服、银色高跟鞋和黑银手持麦克风始终一致；保持同一张脸、自然人体和完整礼服轮廓",
    scene: "黑红主色的巨型电视演播厅，镜面舞台中央是一轮从中部裂开的银蓝机械月亮，顶部白色聚光、两侧红光机械结构、薄雾与地面反射保持统一；所有屏幕无可读文字",
    action: "高能电视综艺；表演、挑战与现场互动随机演进，出现明显的目标转折和情绪高潮，不指定机关、事故或表演顺序",
    camera: "稳定电视直播摇臂从中远景缓慢靠近并适度抬升，关键反转时才改变景别；始终保持歌手居中可辨、机械月亮空间关系清楚，不使用快速剪辑",
    avoid: "不要第二位主持人或伴舞抢镜，不要突然换脸换装、麦克风复制、肢体畸变或礼服消失；不要可读文字、字幕、台标Logo、界面、水印、硬切、频闪和无因烟花",
    hint: "高能舞台与临场惊喜，每一次开播都是全新的节目。",
  },
  travel_aerial: {
    number: "CH 04",
    name: "旅行电影航拍",
    revision: "volcanic-ridge-storm-v1",
    subject: "一位独行成年徒步者，芥末黄色防水连帽外套、黑色长裤、深色登山靴和黑色双肩包始终一致；人物背向镜头、体型比例自然，始终只有一名徒步者",
    scene: "真实感火山岛海岸的狭窄绿色火山口山脊，左侧深蓝大海与黑色礁岸、右侧翡翠火山湖，前方黑色风暴云、雨幕和远处破云日光保持同一地理关系",
    action: "沉浸式旅行纪实；基于真实地形随机发现新的路径、自然现象与有意义的选择，画面与旅程明显推进，不预设天气事件或目的地",
    camera: "稳定无人机在人物后上方沿同一山脊轴线跟随；随着风暴逼近逐渐降低并靠近，脱险后再抬升揭示全景，地平线和左右海湖关系始终稳定",
    avoid: "不要列车、汽车、城市、额外游客或虚构巨兽；不要山脊、海岸和火山湖换位，不要人物复制换衣、飞行悬浮、危险跳跃、天气瞬间跳变、硬切、快速旋转、文字Logo、字幕、界面或水印",
    hint: "电影感航拍，沿未知的旅程，遇见下一处风景。",
  },
  costume_drama: {
    number: "CH 05",
    name: "AI古装短剧",
    revision: "frontier-beacon-v1",
    subject: "一位成年女将，墨黑高马尾、深色札甲、绯红窄袖内袍、残破深红披风和一柄黑鞘长剑始终一致；保持同一张脸、盔甲结构和自然成人比例",
    scene: "落日沙暴下的古代边关城墙，女将站在粗粝垛口，深红残破披风向左飞扬；前方同一座山岭堡垒的烽火塔已经燃起，黑烟、残旗、城墙路线和荒漠群山保持连续",
    action: "有强烈戏剧张力的古装故事；人物目标、线索与局势随机演进，出现有因果关系的重大揭示与反转，不预设阴谋或结局",
    camera: "史诗古装中远景从女将侧后方跟拍，沿城墙轴线稳定推进；危机时适度靠近手、箭书与表情，高潮再抬升揭示烽火链，保持堡垒方位和人物动线连续",
    avoid: "不要宫殿屋脊、现代物品、现有影视人物、多人混战或仙侠法术；不要女将换脸换装、披风剑鞘复制、穿墙飞行、堡垒瞬移、无因爆炸、硬切、快速旋转、文字Logo、字幕、界面或水印",
    hint: "古装世界里的风云变幻，下一刻的故事尚未写下。",
  },
  custom_channel: {
    number: "CH ＋",
    name: "自定义频道",
    subject: "一个外形、材质和颜色始终一致的主角或主体",
    scene: "一个空间关系清晰、光线与材质统一的原创世界",
    action: "根据频道设定随机演进新事件，改变主角的目标、处境或认知，保持人物和因果连续",
    camera: "低机位缓慢跟随主体向前",
    avoid: "不要文字Logo、不要突然换景、不要主体复制变形、不要碰撞穿模",
    hint: "定义你的世界和视觉风格，让 AI 即兴演绎。",
  },
};

function presetFieldValues(field) {
  return Object.values(presetProfiles).map((profile) => profile[field]);
}

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
  const { timeoutMs = 20000, ...fetchOptions } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      cache: "no-store",
      signal: controller.signal,
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.error || data.message || `请求失败 (${response.status})`);
      error.status = response.status;
      throw error;
    }
    return data;
  } finally {
    window.clearTimeout(timer);
  }
}

async function checkHealth() {
  if (state.healthChecking) return;
  state.healthChecking = true;
  $("#retryConnection").disabled = true;
  try {
    const health = await request("/api/health", { timeoutMs: 4000 });
    if (!health.ok || health.app_id !== "framecurrent") throw new Error("本机服务不匹配");
    state.serverStatus = "online";
    state.activeGeneration = presetProfiles[health.active_session?.preset] ? health.active_session : null;
    if (state.activeGeneration) rememberSession(state.activeGeneration.preset, state.activeGeneration.session_id);
    $("#healthDot").classList.add("ok");
    $("#healthText").textContent = "本机服务已连接";
    if (state.initialized && !state.starting && !state.restoring
        && state.activeGeneration?.preset === state.activeChannelId
        && state.sessionId !== state.activeGeneration.session_id) {
      await loadChannelSession(state.activeChannelId);
    }
  } catch (_) {
    state.serverStatus = "offline";
    $("#healthDot").classList.remove("ok");
    $("#healthText").textContent = "本机服务未连接";
  } finally {
    state.healthChecking = false;
    $("#retryConnection").disabled = false;
    $("#connectionNotice").hidden = state.serverStatus !== "offline";
    updateStartEligibility();
  }
}

function estimatedCost() {
  if (state.durationMode === "unlimited") return 0;
  if (!state.durationValid) return 0;
  const rate = $("#resolution").value === "768P" ? 0.08 : 0.05;
  const count = buildSchedule(state.durationSeconds, Number($("#clipDuration").value || 10)).length;
  return state.durationSeconds * rate + count * DIRECTOR_SCENE_ALLOWANCE_USD;
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
    if (!state.sessionId) {
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
  const otherActive = state.activeGeneration && state.activeGeneration.preset !== state.activeChannelId;
  let reason = "";
  if (state.serverStatus !== "online") reason = state.serverStatus === "offline" ? "请先重新启动本机服务，然后点击上方“重新连接”。" : "正在连接本机服务…";
  else if (otherActive) reason = "另一个频道正在生成，请先返回该频道查看或停止续写。";
  else if (state.busy || (state.activeGeneration && !unresolvedSession)) reason = "这个频道正在生成，已完成的片段会自动保存。";
  else if (state.starting || state.paymentDialogOpen) reason = "正在确认或启动，请勿重复提交。";
  else if (state.restoring || unresolvedSession) reason = "正在找回这个频道的节目；无法恢复时可点击当前频道重试。";
  else if (state.reconcilingStarts[state.activeChannelId]) reason = "正在核对上一次开播结果，请稍候。";
  else if (state.imagePreparing) reason = "正在准备参考图，请稍候。";
  else if (!durationReady) reason = "请填写10秒到30分钟之间的成片时长。";
  else if (!hasSubject || !hasScene) reason = "请在节目设置中补全固定主体与固定世界。";
  else if (!state.keyVerified) reason = "下一步：输入并验证你的 fal API Key。";
  $("#startButton").disabled = Boolean(reason);
  $("#startHelp").textContent = reason || "准备好了。点击开播后，仍需核对并确认本次费用。";
  $("#activeNotice").hidden = !otherActive;
  if (otherActive) $("#activeNoticeText").textContent = `${presetProfiles[state.activeGeneration.preset].name}仍在生成。换台不会停止任务，已提交画面可能计费。`;
  document.querySelectorAll("[data-preset]").forEach((card) => card.classList.toggle("broadcasting", card.dataset.preset === state.activeGeneration?.preset));
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
    && (state.sessionId === state.channelSessions[preset] || !state.channelSessions[preset])
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
    : "频道风格已就绪，AI 将即兴生成节目。";
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
  $("#liveBadge span").textContent = `AI VIDEO · ${profile.number}`;
  $("#presetHint").textContent = profile.hint;
  [
    ["#subjectLock", "subject", "subjectEdited", "subjectLock"],
    ["#sceneSetting", "scene", "sceneEdited", "sceneSetting"],
    ["#concept", "action", "actionEdited", "concept"],
    ["#cameraMotion", "camera", "cameraEdited", "cameraMotion"],
    ["#avoidContent", "avoid", "avoidEdited", "avoidContent"],
  ].forEach(([selector, field, editedFlag, draftField]) => {
    const element = $(selector);
    const draftMatches = !profile.revision || draft?.presetRevision === profile.revision;
    element.value = (draftMatches && draft?.[draftField]) || profile[field];
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
    presetRevision: presetProfiles[state.activeChannelId]?.revision || "",
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
      timeoutMs: 90000,
      body: JSON.stringify({ api_key: apiKey }),
    });
    if ($("#apiKey").value.trim() !== apiKey) {
      state.verifiedKey = "";
      setKeyStatus("密钥已改变，请验证当前输入的密钥", "error");
      return;
    }
    if (result.valid === false || result.ok === false) throw new Error(result.message || "密钥验证失败");
    state.keyVerified = true;
    state.verifiedKey = apiKey;
    const balanceText = result.balance && result.balance.current_balance !== null
      ? ` · 可用余额 ${money(result.balance.current_balance)}`
      : ` · ${result.balance_note || "请确认所属工作区有可用余额"}`;
    setKeyStatus(`账户连接已验证${balanceText}；实际生成权限以提交结果为准`, "ok");
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
  if (session.status === "preparing") return "正在检查本地媒体工具，尚未提交付费生成";
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
  return "下一幕正在即兴构思";
}

function friendlyError(message, fallback = "创作暂时中断，请稍后重试。") {
  const value = String(message || "").toLowerCase();
  if (value.includes("剧情")) {
    if (["格式", "字段", "标记", "无效内容"].some((word) => value.includes(word))) return "AI 剧情返回格式未通过校验，请刷新页面后重新开播。";
    if (["重复", "相似", "变化不足", "未构思出"].some((word) => value.includes(word))) return "AI 暂未构思出符合要求的新剧情，请重新开播。";
    return "AI 剧情续写暂未完成，请刷新页面后重新开播。";
  }
  if (value.includes("本地环境")) return "本地环境未就绪。请运行 doctor.command 检查工具与目录权限；此检查失败时不会提交付费生成。";
  if (value.includes("本地视频处理") || value.includes("视频下载未通过")) return "视频处理或下载检查未通过。可下载下方已保存片段；请先运行 doctor.command，不要反复付费开播。";
  if (value.includes("已有一个生成任务")) return "另一个频道正在生成，请返回该频道查看或停止续写。";
  if (value.includes("余额") || value.includes("balance")) return "fal账户余额不足，或这把Key所属的工作区尚未充值。";
  if (value.includes("budget") || value.includes("预算")) return "本地预计费用上限不符合要求，请调整后重试。";
  if (value.includes("api key") || value.includes("unauthorized") || value.includes("401") || value.includes("密钥")) return "API Key无效或没有可用权限，请检查后重试。";
  if (value.includes("safety") || value.includes("内容安全")) return "这段描述未通过内容安全检查，请调整画面描述。";
  if (value.includes("network") || value.includes("timeout") || value.includes("abort") || value.includes("fetch") || value.includes("连接")) return "连接暂时中断或请求超时。请确认本机启动终端仍在运行，再重新连接；开播结果未知时不要更换设备重复提交。";
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

function renderSavedClips(session) {
  const clips = session.clips || [];
  const container = $("#savedClipLinks");
  const signature = `${session.session_id || ""}:${clips.map((clip) => clip.url).join("|")}`;
  $("#savedClips").hidden = !clips.length;
  if (container.dataset.signature === signature) return;
  container.dataset.signature = signature;
  container.replaceChildren();
  $("#savedClipsSummary").textContent = `已保存片段 · ${clips.length}幕 · 可单独下载`;
  clips.forEach((clip, index) => {
    // Only link to this session's same-origin media, never arbitrary URLs.
    const prefix = `/media/${encodeURIComponent(session.session_id)}/`;
    if (typeof clip.url !== "string" || !clip.url.startsWith(prefix) || clip.url.includes("..")) return;
    const link = document.createElement("a");
    link.href = clip.url;
    link.download = `FrameCurrent-${session.session_id}-${index + 1}.mp4`;
    link.textContent = `第${index + 1}幕 · ${formatDuration(clip.duration)} ↓`;
    container.append(link);
  });
}

function updateMonitor(session) {
  state.latestSession = session;
  if (!terminalStatuses.has(session.status)) state.activeGeneration = { session_id: session.session_id, preset: session.config?.preset || state.activeChannelId };
  else if (state.activeGeneration?.session_id === session.session_id) state.activeGeneration = null;
  renderSavedClips(session);
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
  if (session.error && session.status === "failed") {
    errorBox.textContent += clips.length
      ? ` 已保存 ${clips.length} 幕，可在下方下载。`
      : Number(session.submitted_seconds || 0) === 0
        ? " 本次尚未提交视频生成。"
        : " 已提交的视频尚未保存，请先检查 fal 任务结果。";
  }
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

function updatePreviewButton() {
  const button = $("#previewButton");
  const playing = state.showcase.active || state.preview.enabled;
  const hasClips = Boolean(state.latestSession?.clips?.length);
  const running = state.starting || (state.latestSession && !terminalStatuses.has(state.latestSession.status));
  const hasExample = state.activeChannelId === "hand_drawn_fantasy" && !running;
  button.disabled = !playing && !hasClips && !hasExample;
  button.textContent = playing ? "关闭预览" : hasClips ? "预览已生成视频" : hasExample ? "预览示例" : "暂无可预览视频";
  button.setAttribute("aria-pressed", String(playing));
  $("#previewHint").textContent = playing
    ? (running ? "仅关闭播放，不停止生成" : "关闭后回到黑屏，视频仍然保留")
    : "仅播放已有视频，不启动生成";
}

function stopShowcase() {
  state.showcase.epoch += 1;
  state.showcase.active = false;
  const video = $("#presetShowcase");
  video.pause();
  video.classList.remove("visible");
  video.removeAttribute("src");
  video.load();
}

async function togglePreview() {
  if (state.showcase.active || state.preview.enabled) {
    resetPreview(state.preview.sessionId);
    return;
  }
  if (state.latestSession?.clips?.length) {
    if (state.preview.sessionId !== state.latestSession.session_id) resetPreview(state.latestSession.session_id);
    state.preview.clips = state.latestSession.clips;
    state.preview.enabled = true;
    updatePreviewButton();
    await startPreview();
    return;
  }
  if ($("#previewButton").disabled) return;
  const video = $("#presetShowcase");
  const epoch = ++state.showcase.epoch;
  state.showcase.active = true;
  updatePreviewButton();
  video.src = video.dataset.src;
  try {
    await video.play();
    if (state.showcase.epoch !== epoch) return;
    video.classList.add("visible");
    $("#stagePlaceholder").classList.add("hidden");
    $("#liveStage").classList.add("screen-active");
  } catch (_) {
    if (state.showcase.epoch !== epoch) return;
    resetPreview(state.preview.sessionId);
    toast("示例暂时无法播放，请点击预览重试");
  }
}

function resetPreview(sessionId = null, enabled = false) {
  stopShowcase();
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
    enabled,
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
  $("#stagePlaceholder h3").textContent = "";
  $("#stagePlaceholder p").textContent = "";
  $("#liveStage").classList.remove("screen-active");
  $("#previewCaption").hidden = true;
  $("#bufferNotice").hidden = true;
  $("#previewElapsed").textContent = "00:00";
  updatePreviewButton();
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
  if (!state.preview.enabled || state.preview.started || state.preview.clips.length < 1 || state.preview.syncing) return;
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
    $("#liveStage").classList.add("screen-active");
    $("#previewCaption").hidden = false;
    $("#bufferNotice").hidden = true;
    updatePreviewClock();
  } catch (_) {
    if (state.preview.epoch !== epoch) return;
    resetPreview(state.preview.sessionId);
    toast("视频暂时无法播放，请点击预览重试");
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
  updatePreviewButton();
  if (!state.preview.enabled) return;
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

async function reconcilePendingStart(channelId, sessionId) {
  const pending = state.pendingRequestIds[channelId];
  const requestId = typeof pending === "string" ? pending : pending?.id;
  if (!requestId) return;
  if (state.reconcilingStarts[channelId]) return;
  state.reconcilingStarts[channelId] = true;
  updateStartEligibility();
  try {
    const result = await request("/api/session/recover", {
      method: "POST", body: JSON.stringify({ client_request_id: requestId }),
    });
    // A different tab may have started another task; never clear an unproven ID.
    if (result.session_id === sessionId && state.pendingRequestIds[channelId] === pending) clearPendingStart(channelId);
  } catch (_) { /* Keep unknown requests for safe idempotent recovery. */ }
  finally {
    delete state.reconcilingStarts[channelId];
    updateStartEligibility();
  }
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
  $("#stagePlaceholder h3").textContent = "";
  $("#stagePlaceholder p").textContent = "";
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
  renderSavedClips({ clips: [] });
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
    const requiredRevision = presetProfiles[channelId]?.revision || "";
    const actualRevision = session.config?.preset_revision || "";
    if (requiredRevision && actualRevision !== requiredRevision) {
      delete state.channelSessions[channelId];
      persistSessionMap();
      resetMonitorForChannel();
      toast("旧版频道节目已退出；可点击预览查看当前示例");
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
    reconcilePendingStart(channelId, session.session_id);
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
  const minimumBudget = Number((clipDuration * rate + DIRECTOR_SCENE_ALLOWANCE_USD).toFixed(2));
  const fixedBudget = Number(estimatedCost().toFixed(2));
  const floorBudgetCents = (value) => Math.floor(Number(value) * 100 + 1e-9) / 100;

  $("#paidDialogMode").textContent = unlimited ? "参考生成费率" : "本次预计费用";
  $("#paidDialogCost").textContent = unlimited ? `${money(rate * 60 + 60 / clipDuration * DIRECTOR_SCENE_ALLOWANCE_USD)} / 分钟` : money(fixedBudget);
  $("#paidDialogDetail").textContent = unlimited
    ? `${$("#selectedChannelName").textContent} · ${state.aspectRatio} · ${resolution} · 含视频及 AI 剧情续写预留，持续至停止或达到下方上限`
    : `${$("#selectedChannelName").textContent} · 成片${formatDuration(state.durationSeconds)} · ${state.aspectRatio} · ${resolution} · 含视频及 AI 剧情续写预留，实际以 fal 账单为准`;
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
  if (state.busy || state.starting || state.restoring || state.imagePreparing || unresolvedSession || state.reconcilingStarts[state.activeChannelId] || state.serverStatus !== "online" || state.activeGeneration) return;
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
    preset_revision: presetProfiles[channelId]?.revision || "",
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
    state.latestSession = null;
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
    // Only a newly requested broadcast opts into automatic playback. Restored
    // history and idempotent recovery remain black until an explicit preview.
    resetPreview(sessionId, !result.idempotent_replay);
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
    updatePreviewButton();
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
$("#previewButton").addEventListener("click", togglePreview);
$("#presetShowcase").addEventListener("ended", () => {
  if (state.showcase.active) resetPreview(state.preview.sessionId);
});

state.channelDrafts = recalledChannelDrafts();
state.channelSessions = recalledSessions();
state.pendingRequestIds = recalledPendingStarts();
selectChannel("hand_drawn_fantasy", false);
applyDurationMode("fixed");
applyAspectRatio("16:9", false);
updateDuration();
updateStartEligibility();
async function initializeSession() {
  await checkHealth();
  if (state.activeGeneration) selectChannel(state.activeGeneration.preset, false);
  await loadChannelSession(state.activeChannelId);
  state.initialized = true;
}
$("#retryConnection").addEventListener("click", async () => {
  await checkHealth();
  if (!state.busy && !state.restoring) await loadChannelSession(state.activeChannelId);
});
$("#returnActiveChannel").addEventListener("click", () => {
  if (state.activeGeneration) selectChannel(state.activeGeneration.preset);
});
$("#openGuideButton").addEventListener("click", () => {
  $("#usageGuide").open = true;
  $("#usageGuide summary").focus();
  $("#usageGuide").scrollIntoView({ behavior: "smooth", block: "start" });
});
const initialization = initializeSession();
window.setInterval(checkHealth, 15000);
