#!/usr/bin/env python3
"""FrameCurrent flexible-duration continuous-video creator for H3 Max.

The local server deliberately uses only Python's standard library so it runs
on a stock Mac. A fal API key is held in process memory only and is cleared
when a generation session ends.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import mimetypes
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


APP_ROOT = Path(__file__).resolve().parent
WEB_ROOT = APP_ROOT / "web"
SCRIPT_ROOT = APP_ROOT / "scripts"
RUNTIME_ROOT = APP_ROOT / "runtime"
SESSION_ROOT = RUNTIME_ROOT / "sessions"
BIN_ROOT = RUNTIME_ROOT / "bin"
APP_VERSION = "1.6.2"
APP_ID = "framecurrent"
# Identifies this checkout without exposing its absolute path to the browser.
INSTANCE_ID = hashlib.sha256(str(APP_ROOT).encode("utf-8")).hexdigest()[:24]
SHUTTING_DOWN = threading.Event()

MIN_DURATION_SECONDS = 10
MAX_DURATION_SECONDS = 30 * 60
DURATION_MODES = {"fixed", "unlimited"}
CLIENT_REQUEST_ID_PATTERN = re.compile(
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
)
CLIP_DURATIONS = {5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15}
RESOLUTION_RATES_USD = {"480P": 0.05, "768P": 0.08}
MAX_LOCAL_ESTIMATED_BUDGET_USD = 150.0
ASPECT_RATIOS = {
    "9:16": {"label": "竖屏", "width": 9, "height": 16},
    "16:9": {"label": "横屏", "width": 16, "height": 9},
}
ASPECT_RATIO_TOLERANCE = 0.015
MAX_JSON_BYTES = 18 * 1024 * 1024
MAX_API_JSON_BYTES = 4 * 1024 * 1024
MAX_VIDEO_BYTES = 512 * 1024 * 1024
QUEUE_GET_MAX_ATTEMPTS = 4
QUEUE_GET_BACKOFF_SECONDS = (0.5, 1.0, 2.0)
MAX_RETRY_AFTER_SECONDS = 10.0
INTERNAL_QA = os.environ.get("H3_INTERNAL_QA") == "1"
ALLOWED_QUEUE_HOSTS = {"queue.fal.run"}
ALLOWED_MEDIA_ROOTS = {"fal.media"}
LOCAL_REQUEST_HOSTS = {"127.0.0.1", "localhost"}
REDIRECT_STATUS_CODES = {301, 302, 303, 307, 308}
H3_FALLBACK_FRAME_RATE = 24.0
H3_MAX_GENERATION_EXTRA_FRAMES = 5.0
H3_GENERATION_UNDERRUN_SECONDS = 0.01
FINAL_DURATION_TOLERANCE_SECONDS = 0.012
MAX_MEDIA_INFO_CHARS = 64 * 1024
BOUNDARY_SIMILARITY_MIN = 0.96


PRESETS: Dict[str, Dict[str, Any]] = {
    "hand_drawn_fantasy": {
        "name": "日系手绘奇幻动画",
        "subject": "一架红色复古单翼滑翔机，驾驶舱内的成年短发女飞行员始终穿芥末黄斗篷、背红色邮差包并戴圆形护目镜",
        "base": (
            "An original Japanese hand-drawn fantasy animation with painterly cel shading, expressive wind, "
            "luminous cloud layers, jewel-like colors, dramatic scale and richly illustrated backgrounds. "
            "The design must be original and must not copy any existing artist, studio, franchise or character. "
            "Use a single fluid aerial journey, clean silhouettes, strong foreground parallax and a warm orchestral "
            "adventure atmosphere while preserving one coherent illustrated world."
        ),
        "beats": [
            "A vast floating island casts a moving shadow across the flight path while the aircraft keeps course.",
            "Enormous windmill blades turn through the foreground and create bold layered parallax.",
            "A colossal cloud whale gradually emerges in the distance and begins gliding parallel to the aircraft.",
            "The aircraft passes through a luminous cloud arch without changing direction or resetting the scene.",
            "Mist from an island waterfall crosses the path, then clears to reveal the same connected sky route.",
            "A higher tier of floating islands opens ahead as golden light spreads through the cloud sea.",
        ],
    },
    "cinematic_scifi": {
        "name": "电影级科幻史诗",
        "subject": "一艘黑色三角深空侦察舰，银白骨架、三枚红色引擎和细长机翼始终一致",
        "base": (
            "A high-budget hard-science-fiction feature film shot with vast orbital megastructures, a gas giant "
            "during eclipse, cold cyan rim light, red engine glow, volumetric dust and physically believable scale. "
            "Use anamorphic lens character, deep blacks, precise metallic detail and a monumental reveal. The ship "
            "moves along one readable flight path with no teleporting, no shape change and no chaotic battle montage."
        ),
        "beats": [
            "The craft passes beneath a colossal structural arch as the gas giant slowly fills more of the background.",
            "Rows of amber maintenance lights ignite sequentially along the same corridor ahead.",
            "A sparse field of metallic debris catches the eclipse rim light while remaining clear of the flight path.",
            "The craft crosses a translucent energy veil that ripples around it without altering the surrounding structure.",
            "A distant star moves out from eclipse and gradually carves a brilliant rim around the craft and megastructure.",
            "The corridor opens into the vast central ring core, revealed through scale and parallax rather than a cut.",
        ],
    },
    "studio_variety": {
        "name": "高能棚内综艺",
        "subject": "一位成年女主持人，利落短发、钴蓝色亮片西装和橙色手持麦克风始终一致",
        "base": (
            "A premium prime-time studio variety show with a spectacular curved LED stage, saturated cyan, magenta "
            "and amber light blocks, glossy reflections, moving beams, audience silhouettes and confident broadcast "
            "production design. Keep all LED graphics abstract and free of readable text or logos. Use one smooth "
            "broadcast-crane move, energetic lighting cues, clean staging and a consistent host identity."
        ),
        "beats": [
            "A cyan light chase travels from the stage perimeter toward the host while the camera keeps its smooth arc.",
            "Magenta beams sweep across the same stage geometry and reflect in the floor behind the host.",
            "The seated audience creates one synchronized wave of handheld lights without entering the foreground.",
            "A circular stage mechanism rotates slowly beneath the host while her position and scale remain stable.",
            "A controlled confetti burst fires from one fixed stage unit and clears without obscuring the host.",
            "All light arrays converge into a high-energy final tableau while the uninterrupted crane move continues.",
        ],
    },
    "travel_aerial": {
        "name": "旅行电影航拍",
        "subject": "一列红白相间的三节观景列车，黑色全景车窗和流线型车头始终一致",
        "base": (
            "A breathtaking premium travel-film aerial over one continuous alpine coastal valley at sunrise: "
            "snow peaks, a turquoise lake, waterfalls, pine ridges and sea cliffs connected by the same railway. "
            "Use a stabilized cinematic drone flight with crisp atmospheric depth, golden side light, grand scale "
            "and a gradual high reveal. Preserve geography, weather, train design, direction and a level horizon."
        ),
        "beats": [
            "The train follows a broad cliffside curve while the coastline produces deep foreground-to-horizon parallax.",
            "The train passes through a short rock tunnel and returns to the same connected coastline and weather.",
            "A tall waterfall appears beside the railway and its mist drifts briefly across the drone's path.",
            "The drone gains altitude gradually and reveals the next bay physically connected to the current headland.",
            "Golden sunlight breaks across the turquoise water while the train maintains speed and direction.",
            "The nearest cliff recedes to reveal a sweeping railway bridge and the continuous coast beyond it.",
        ],
    },
    "costume_drama": {
        "name": "AI古装短剧",
        "subject": "一位成年女侠，墨黑高马尾、绯红窄袖劲装、银色护腕和一柄黑鞘长剑始终一致",
        "base": (
            "An original premium Chinese costume-drama television serial with cinematic production design, "
            "layered palace and riverside architecture, wind-driven fabric, dramatic practical light, elegant "
            "martial-arts blocking and emotionally readable close-to-medium staging. Preserve the same adult heroine, "
            "costume, weapon, geography and screen direction in one coherent unfolding scene. Do not copy any existing "
            "film, television series, performer, franchise or character."
        ),
        "beats": [
            "The heroine advances beneath one continuous covered walkway while distant lantern light grows gradually brighter.",
            "A gust carries fallen leaves across the same courtyard as she keeps the established pace and direction.",
            "She notices a distant silhouette reflected in the river, without introducing a cut or changing location.",
            "The camera eases sideways to reveal the connected moon gate while every architectural landmark stays in place.",
            "She reaches the riverside steps and draws one controlled breath; her costume and sword remain unchanged.",
            "Dawn light spreads along the same palace roofline as the uninterrupted journey continues toward the next chapter.",
        ],
    },
    "custom_channel": {
        "name": "自定义频道",
        "subject": "用户在频道设定中指定的唯一主角或主体，其外观、材质、比例和关键识别特征始终一致",
        "base": (
            "An original premium AI television channel with a strong, deliberate visual identity and one coherent "
            "world. Treat the creator's channel description as the binding art direction. Preserve subject identity, "
            "geography, lighting logic, camera language and motion continuity instead of resetting the program each segment."
        ),
        "beats": [
            "Establish the creator-defined program with one clear subject, readable environment and a path that can continue.",
            "Continue the same physical action and reveal one connected layer of the creator-defined world.",
            "Let a controlled lighting or environmental change deepen the program without changing its identity.",
            "Use gentle parallax to reveal more of the same location while preserving every established spatial relationship.",
            "Advance toward one visible destination without replaying an earlier event or adding a new main subject.",
            "Reach a stable visual beat that remains open for the next uninterrupted chapter.",
        ],
    },
}

LEGACY_PRESET_ALIASES = {
    "miniature_odyssey": "hand_drawn_fantasy",
    "future_walk": "cinematic_scifi",
    "ink_landscape": "studio_variety",
    "mechanical_loop": "travel_aerial",
}


BEATS = [
    "The path advances gently and reveals a slightly wider layer of the same world.",
    "The camera passes one foreground detail while the subject continues at exactly the same pace.",
    "A soft change in light travels across the existing scene without changing location abruptly.",
    "The subject curves naturally around one environmental feature; motion remains slow and readable.",
    "The camera draws a little closer to tactile details, then resumes the same forward path.",
    "A deeper vista opens ahead while all palette, weather and material rules remain unchanged.",
    "The environment becomes subtly more magical through particles and light, not through a scene cut.",
    "The subject crosses a small threshold that physically belongs to the current location.",
    "The camera eases sideways for gentle parallax, then returns behind the subject.",
    "A calm visual payoff appears in the distance and grows gradually as the journey continues.",
]

# These beats deliberately avoid naming a new landmark. A continuation request
# only receives one still frame, so asking it to introduce a specific foreground
# object can cause that object to be teleported into the subject's path.
CONTINUATION_BEATS = [
    "Let every landmark already visible keep its current side and depth order while it recedes naturally; keep the route ahead unobstructed.",
    "Continue the same readable path and speed; a compatible distant detail may become slightly clearer but must remain in the background.",
    "Allow only a gradual lighting change across the existing world; do not add, repeat or relocate a major structure.",
    "Use a very gentle camera ease to reveal more of the physically connected route while keeping the subject's path clear.",
    "Let the existing distant destination grow gradually through forward motion, without a cut, reset or sudden scale jump.",
    "Continue through open space with the same horizon and screen direction; previously passed landmarks must remain behind.",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def positive_finite_seconds(value: Any) -> Optional[float]:
    """Return a provider timing only when it is a usable positive number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    seconds = float(value)
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    return seconds


def floor_timing_tenth(value: Any) -> Optional[float]:
    """Truncate a positive duration to tenths without rounding it upward."""
    seconds = positive_finite_seconds(value)
    if seconds is None:
        return None
    return math.floor(seconds * 10) / 10


def build_generation_timing(
    status: Dict[str, Any],
    result: Dict[str, Any],
    result_ready_seconds: Any,
) -> Dict[str, Any]:
    """Select the narrowest provider-reported generation timing available.

    H3 Max may expose ``timings.inference`` for GPU DiT denoising. When that
    narrower metric is unavailable, fal's completed queue status can expose
    runner processing time. The local request-to-result clock is a final,
    always-observable fallback. These scopes are selected deliberately rather
    than taking a mathematical minimum between unlike measurements.
    """
    result_data = (
        result.get("data") if isinstance(result.get("data"), dict) else {}
    )
    core_candidates = []
    for container in (result, result_data):
        timings = container.get("timings") if isinstance(container, dict) else None
        if isinstance(timings, dict):
            core_candidates.append(timings.get("inference"))
    core_seconds = next(
        (
            value
            for value in map(positive_finite_seconds, core_candidates)
            if value is not None
        ),
        None,
    )

    status_data = (
        status.get("data") if isinstance(status.get("data"), dict) else {}
    )
    processing_candidates = []
    for container in (status, status_data):
        metrics = container.get("metrics") if isinstance(container, dict) else None
        if isinstance(metrics, dict):
            processing_candidates.append(metrics.get("inference_time"))
    processing_seconds = next(
        (
            value
            for value in map(positive_finite_seconds, processing_candidates)
            if value is not None
        ),
        None,
    )
    fallback_seconds = positive_finite_seconds(result_ready_seconds)

    if core_seconds is not None:
        selected_seconds, source = core_seconds, "gpu_core"
    elif processing_seconds is not None:
        selected_seconds, source = processing_seconds, "fal_processing"
    else:
        selected_seconds, source = fallback_seconds, "result_ready"

    return {
        "seconds": floor_timing_tenth(selected_seconds),
        "source": source if selected_seconds is not None else "unavailable",
    }


def normalize_client_request_id(value: Any) -> str:
    """Validate and normalize the mandatory idempotency key for paid starts."""
    if not isinstance(value, str):
        raise ValueError("client_request_id 必须是 UUID 格式字符串")
    if len(value) != 36 or not CLIENT_REQUEST_ID_PATTERN.fullmatch(value):
        raise ValueError("client_request_id 必须是 UUID 格式字符串")
    return value.lower()


def client_request_hash(client_request_id: str) -> str:
    """Create a disk-safe lookup token without retaining the raw request ID."""
    return hashlib.sha256(
        f"h3-max-session-start:{client_request_id}".encode("ascii")
    ).hexdigest()


def estimate_cost_usd(duration_seconds: int, resolution: str) -> float:
    return round(duration_seconds * RESOLUTION_RATES_USD[resolution], 2)


def budget_allows_segment(
    config: Dict[str, Any],
    submitted_seconds: int,
    segment_duration: int,
) -> bool:
    """Return whether one more clip stays inside the local estimated-cost cap."""
    projected = estimate_cost_usd(
        submitted_seconds + segment_duration,
        config["resolution"],
    )
    return projected <= config["max_budget_usd"] + 0.001


def build_clip_schedule(duration_seconds: int, preferred_seconds: int) -> List[int]:
    """Return legal 5..15 second clips whose sum is exactly the target."""
    if isinstance(duration_seconds, bool) or not isinstance(duration_seconds, int):
        raise ValueError("目标时长必须是整数秒")
    if isinstance(preferred_seconds, bool) or preferred_seconds not in CLIP_DURATIONS:
        raise ValueError("单段时长必须在5至15秒之间")
    minimum_count = math.ceil(duration_seconds / max(CLIP_DURATIONS))
    maximum_count = duration_seconds // min(CLIP_DURATIONS)
    if minimum_count < 1 or minimum_count > maximum_count:
        raise ValueError("无法用5至15秒片段精确组成目标时长")
    count = min(
        range(minimum_count, maximum_count + 1),
        key=lambda value: (abs(duration_seconds / value - preferred_seconds), value),
    )
    base, extra = divmod(duration_seconds, count)
    schedule = [base + (1 if index < extra else 0) for index in range(count)]
    if not schedule or any(length not in CLIP_DURATIONS for length in schedule):
        raise ValueError("无法用5至15秒片段精确组成目标时长")
    return schedule


def format_duration_label(duration_seconds: int) -> str:
    minutes, seconds = divmod(duration_seconds, 60)
    if minutes and seconds:
        return f"{minutes}分{seconds}秒"
    if minutes:
        return f"{minutes}分钟"
    return f"{seconds}秒"


def validate_aspect_dimensions(width: int, height: int, aspect_ratio: str) -> None:
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("画面比例必须是9:16或16:9")
    definition = ASPECT_RATIOS[aspect_ratio]
    expected_portrait = aspect_ratio == "9:16"
    orientation_matches = (height > width) if expected_portrait else (width > height)
    short_to_long = (
        min(width, height) / max(width, height)
        if width > 0 and height > 0
        else 0
    )
    if (
        not orientation_matches
        or abs(short_to_long - 9 / 16) > ASPECT_RATIO_TOLERANCE
    ):
        raise RuntimeError(
            f"媒体验证失败：需要 {aspect_ratio} {definition['label']}，实际为 {width}×{height}"
        )


def is_within(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(root.resolve())]) == str(root.resolve())
    except ValueError:
        return False


def build_prompt(config: Dict[str, Any], clip_index: int, has_start_frame: bool) -> str:
    preset = PRESETS[config["preset"]]
    duration_mode = config.get("duration_mode", "fixed")
    total = config.get("total_clips")
    concept = config.get("concept", "").strip()
    subject = config.get("subject_lock", "").strip() or preset["subject"]
    scene = config.get("scene_setting", "").strip()
    story_action = config.get("story_action", "").strip()
    camera = config.get("camera_direction", "").strip()
    exclusions = config.get("avoid_content", "").strip()
    custom_channel_style = config.get("custom_channel_style", "").strip()
    is_continuation = clip_index > 0
    preset_beats = preset.get("beats") or BEATS
    if is_continuation:
        beat = CONTINUATION_BEATS[(clip_index - 1) % len(CONTINUATION_BEATS)]
    else:
        beat = preset_beats[0]
    aspect_ratio = config.get("aspect_ratio", "9:16")
    orientation = "portrait" if aspect_ratio == "9:16" else "landscape"
    if is_continuation:
        intro = (
            "Picture 1 is the exact first frame of this continuation, not a new scene to reinterpret. "
            "Continue directly from it with no cut, no reset, no jump in camera position, and no change of lens, "
            "time of day, weather or art direction. During 00:00-00:04, continue only the motion implied by Picture 1: "
            "preserve every visible object's screen side, depth order, relative scale and orientation; keep the camera "
            "moving in the established direction with a level horizon. Do not introduce a new event during these first "
            "four seconds. After 00:04, any change must emerge gradually in the distant background. "
        )
    elif has_start_frame:
        intro = (
            "Picture 1 is the exact first frame of this new shot. Animate directly from it while preserving its subject, "
            "composition, environment and art direction, and establish a clear physical path that can continue later. "
        )
    else:
        intro = (
            f"Begin a single unbroken {orientation} shot and establish a physical path "
            "that can continue beyond this clip. "
        )
    if scene or story_action or camera or exclusions:
        custom_parts = []
        if scene:
            custom_parts.append(f"WORLD LOCK: {scene}.")
        if camera:
            custom_parts.append(f"CAMERA LOCK: {camera}.")
        if exclusions:
            custom_parts.append(f"CREATOR EXCLUSIONS: {exclusions}.")
        if story_action and not is_continuation:
            custom_parts.append(
                f"FIRST-SEGMENT ACTION ONLY: {story_action}. Do not rush to complete the whole journey."
            )
        elif is_continuation:
            custom_parts.append(
                "Do not restart or replay any earlier story event; continue only the state visible in Picture 1."
            )
        custom = " ".join(custom_parts) + " "
    else:
        custom = f"Creator's concept: {concept}. " if concept and not is_continuation else ""
    if custom_channel_style:
        custom = f"CUSTOM CHANNEL STYLE LOCK: {custom_channel_style}. {custom}"
    segment_label = (
        f"Segment {clip_index + 1} in an ongoing channel"
        if duration_mode == "unlimited"
        else f"Segment {clip_index + 1} of {total}"
    )
    return (
        f"{intro}{preset['base']} {custom}IDENTITY LOCK: {subject}. "
        f"{segment_label}: {beat} "
        "CONTINUITY RULES: one continuous take; preserve the exact subject identity, costume/materials, scale, "
        "screen direction, camera height, lens character, color palette and ambient sound bed. Keep motion slow "
        "and causal. Maintain a collision-free path: never pass through solid geometry, never let a foreground "
        "structure cross or cover the main subject, never teleport a landmark from behind to ahead, and never use "
        "fog, clouds, glare or motion blur to conceal a position reset. Do not introduce a new main character. "
        "No hard cut, montage, flash frame, title, subtitle, logo, UI, watermark, distorted hands, sudden close-up "
        "or rapid camera whip. End in a stable, unobstructed pose while motion is still "
        f"continuing smoothly so the final frame can become the next shot's opening frame. Format: {orientation} {aspect_ratio}."
    )


def validate_start_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    duration_mode = str(payload.get("duration_mode", "fixed")).strip().lower()
    if duration_mode not in DURATION_MODES:
        raise ValueError("时长模式必须是 fixed 或 unlimited")

    duration_seconds: Optional[int]
    if duration_mode == "fixed":
        raw_duration = payload.get("duration_seconds", 300)
        if isinstance(raw_duration, bool):
            raise ValueError("创作时长必须是10至1800秒之间的整数")
        try:
            numeric_duration = float(raw_duration)
        except (TypeError, ValueError) as error:
            raise ValueError("创作时长必须是10至1800秒之间的整数") from error
        if not math.isfinite(numeric_duration) or not numeric_duration.is_integer():
            raise ValueError("创作时长必须是10至1800秒之间的整数")
        duration_seconds = int(numeric_duration)
        if not MIN_DURATION_SECONDS <= duration_seconds <= MAX_DURATION_SECONDS:
            raise ValueError("创作时长必须在10秒至30分钟之间")
    else:
        duration_seconds = None

    clip_duration = int(payload.get("clip_duration", 15))
    if clip_duration not in CLIP_DURATIONS:
        raise ValueError("单段时长必须在5至15秒之间")

    resolution = str(payload.get("resolution", "480P")).upper()
    if resolution not in RESOLUTION_RATES_USD:
        raise ValueError("分辨率必须是480P或768P")

    aspect_ratio = str(payload.get("aspect_ratio", "9:16")).strip()
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("画面比例必须是9:16或16:9")

    requested_preset = str(payload.get("preset", "hand_drawn_fantasy"))
    preset = LEGACY_PRESET_ALIASES.get(requested_preset, requested_preset)
    if preset not in PRESETS:
        raise ValueError("未知的画面方向")

    custom_channel_name = str(payload.get("custom_channel_name", "")).strip()[:40]
    custom_channel_style = str(payload.get("custom_channel_style", "")).strip()[:300]
    if preset == "custom_channel" and not custom_channel_name:
        custom_channel_name = "我的AI频道"

    if duration_mode == "fixed":
        qa_schedule = payload.get("qa_schedule") if INTERNAL_QA else None
        if qa_schedule is not None:
            if (
                not isinstance(qa_schedule, list)
                or not qa_schedule
                or any(not isinstance(value, int) or value not in CLIP_DURATIONS for value in qa_schedule)
                or sum(qa_schedule) != duration_seconds
            ):
                raise ValueError("内部验收片段计划无效")
            clip_schedule = list(qa_schedule)
        else:
            clip_schedule = build_clip_schedule(duration_seconds, clip_duration)
        total_clips: Optional[int] = len(clip_schedule)
        estimated: Optional[float] = estimate_cost_usd(duration_seconds, resolution)
    else:
        clip_schedule = []
        total_clips = None
        estimated = None

    if duration_mode == "unlimited" and "max_budget_usd" not in payload:
        raise ValueError("不限时长模式必须显式设置本地预计费用上限")
    budget_default = estimated if estimated is not None else float("nan")
    raw_max_budget = safe_float(payload.get("max_budget_usd"), budget_default)
    if not math.isfinite(raw_max_budget) or raw_max_budget < 0:
        raise ValueError("本地预计费用上限必须是有效的非负数字")
    if raw_max_budget > MAX_LOCAL_ESTIMATED_BUDGET_USD:
        raise ValueError(
            f"本地预计费用上限不能超过 ${MAX_LOCAL_ESTIMATED_BUDGET_USD:.2f}"
        )
    # Never round a caller's local cap upward. The configured reference rates
    # are cent-denominated, so extra fractional cents are conservatively discarded.
    max_budget = math.floor(raw_max_budget * 100 + 1e-9) / 100
    api_key = str(payload.get("api_key", "")).strip()
    paid_confirmed = payload.get("paid_confirmed") is True

    if not api_key:
        raise ValueError("请输入 fal API Key")
    validate_key_shape(api_key)
    if not paid_confirmed:
        raise ValueError("请确认本次生成会产生 API 费用")
    if estimated is not None and max_budget < estimated:
        raise ValueError(f"本地预计费用上限不足：按内置标准费率计算需要 ${estimated:.2f}")
    if duration_mode == "unlimited":
        first_segment_cost = estimate_cost_usd(clip_duration, resolution)
        if max_budget + 0.001 < first_segment_cost:
            raise ValueError(
                f"不限时长模式的预算至少需要覆盖一幕：${first_segment_cost:.2f}"
            )

    start_image = payload.get("start_image")
    if start_image:
        validate_start_image(str(start_image), aspect_ratio)

    config = {
        "duration_mode": duration_mode,
        "duration_seconds": duration_seconds,
        "duration_label": (
            format_duration_label(duration_seconds)
            if duration_seconds is not None
            else "不限时长"
        ),
        "clip_duration": clip_duration,
        "clip_schedule": clip_schedule,
        "total_clips": total_clips,
        "resolution": resolution,
        "aspect_ratio": aspect_ratio,
        "preset": preset,
        "preset_name": custom_channel_name if preset == "custom_channel" else PRESETS[preset]["name"],
        "concept": str(payload.get("concept", "")).strip()[:3000],
        "subject_lock": str(payload.get("subject_lock", "")).strip()[:800],
        "scene_setting": str(payload.get("scene_setting", "")).strip()[:1000],
        "story_action": str(payload.get("story_action", "")).strip()[:1000],
        "camera_direction": str(payload.get("camera_direction", "")).strip()[:500],
        "avoid_content": str(payload.get("avoid_content", "")).strip()[:500],
        "start_image": start_image,
        "estimated_cost_usd": estimated,
        "max_budget_usd": max_budget,
        "paid_confirmed": paid_confirmed,
        "api_key": api_key,
        "playback_mode": "live_buffer",
        "pricing_basis": "fal_standard_public_rate_guard",
    }
    if preset == "custom_channel":
        config["custom_channel_name"] = custom_channel_name
        config["custom_channel_style"] = custom_channel_style
    return config


def validate_start_image(data_url: str, aspect_ratio: str = "9:16") -> Tuple[int, int]:
    """Validate an in-memory reference image without retaining a copy."""
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("画面比例必须是9:16或16:9")
    matched = re.fullmatch(
        r"data:image/(jpeg|jpg|png|webp);base64,([A-Za-z0-9+/=\r\n]+)",
        data_url,
        flags=re.IGNORECASE,
    )
    if not matched:
        raise ValueError("参考图必须是 JPG、PNG 或 WebP 图片")
    try:
        raw = base64.b64decode(re.sub(r"\s+", "", matched.group(2)), validate=True)
    except Exception as error:
        raise ValueError("参考图数据损坏") from error
    if len(raw) < 1024 or len(raw) > 12 * 1024 * 1024:
        raise ValueError("参考图大小必须在 1KB 至 12MB 之间")

    suffix = ".jpg" if matched.group(1).lower() in {"jpeg", "jpg"} else f".{matched.group(1).lower()}"
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    temporary_path = ""
    try:
        with tempfile.NamedTemporaryFile(dir=RUNTIME_ROOT, suffix=suffix, delete=False) as temporary:
            temporary.write(raw)
            temporary_path = temporary.name
        completed = subprocess.run(
            ["/usr/bin/sips", "-g", "pixelWidth", "-g", "pixelHeight", temporary_path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if completed.returncode != 0:
            raise ValueError("参考图无法读取")
        width_match = re.search(r"pixelWidth:\s*(\d+)", completed.stdout)
        height_match = re.search(r"pixelHeight:\s*(\d+)", completed.stdout)
        if not width_match or not height_match:
            raise ValueError("无法识别参考图尺寸")
        width, height = int(width_match.group(1)), int(height_match.group(1))
        if min(width, height) < 360 or max(width, height) < 640:
            raise ValueError("参考图分辨率过低，短边至少360像素且长边至少640像素")
        expected = ASPECT_RATIOS[aspect_ratio]
        expected_portrait = aspect_ratio == "9:16"
        orientation_matches = (height > width) if expected_portrait else (width > height)
        short_to_long = min(width, height) / max(width, height)
        if (
            not orientation_matches
            or abs(short_to_long - 9 / 16) > ASPECT_RATIO_TOLERANCE
        ):
            raise ValueError(
                f"参考图需要接近 {aspect_ratio} {expected['label']}"
            )
        return width, height
    finally:
        if temporary_path:
            Path(temporary_path).unlink(missing_ok=True)


class FalAPIError(RuntimeError):
    """HTTP/network failure with enough structure for safe GET-only retries."""

    def __init__(
        self,
        message: str,
        *,
        status_code: Optional[int] = None,
        retry_after: Optional[float] = None,
        network_error: bool = False,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.retry_after = retry_after
        self.network_error = network_error

    @property
    def transient(self) -> bool:
        return self.network_error or self.status_code == 429 or (
            self.status_code is not None and 500 <= self.status_code <= 599
        )


class NoAutomaticRedirect(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from replaying requests or forwarding credentials."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def open_without_redirects(request: urllib.request.Request, timeout: int):
    """Open one trusted request without following any HTTP redirect."""

    opener = urllib.request.build_opener(NoAutomaticRedirect())
    return opener.open(request, timeout=timeout)


def request_json(
    url: str,
    method: str,
    api_key: str,
    payload: Optional[Dict[str, Any]] = None,
    timeout: int = 90,
    extra_headers: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Authorization": f"Key {api_key}", "Accept": "application/json"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    if extra_headers:
        headers.update(extra_headers)
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with open_without_redirects(request, timeout=timeout) as response:
            raw_bytes = response.read(MAX_API_JSON_BYTES + 1)
            if len(raw_bytes) > MAX_API_JSON_BYTES:
                raise RuntimeError("fal API 响应过大")
            raw = raw_bytes.decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as error:
        if error.code in REDIRECT_STATUS_CODES:
            error.close()
            detail = "重定向已被本机安全策略拒绝"
        else:
            detail = error.read().decode("utf-8", errors="replace")[:2000]
        retry_after: Optional[float] = None
        try:
            raw_retry_after = error.headers.get("Retry-After") if error.headers else None
            if raw_retry_after is not None:
                retry_after = min(
                    MAX_RETRY_AFTER_SECONDS,
                    max(0.0, float(raw_retry_after)),
                )
        except (TypeError, ValueError):
            retry_after = None
        raise FalAPIError(
            f"fal API HTTP {error.code}: {detail}",
            status_code=error.code,
            retry_after=retry_after,
        ) from error
    except urllib.error.URLError as error:
        raise FalAPIError(
            f"fal API 网络错误: {error.reason}",
            network_error=True,
        ) from error


def request_queue_json_with_retry(
    url: str,
    api_key: str,
    *,
    timeout: int,
    stop_event: threading.Event,
) -> Dict[str, Any]:
    """Retry only idempotent queue GETs; submission POST is never routed here."""

    for attempt in range(QUEUE_GET_MAX_ATTEMPTS):
        try:
            return request_json(url, "GET", api_key, timeout=timeout)
        except FalAPIError as error:
            last_attempt = attempt + 1 >= QUEUE_GET_MAX_ATTEMPTS
            if not error.transient or last_attempt:
                raise
            fallback = QUEUE_GET_BACKOFF_SECONDS[
                min(attempt, len(QUEUE_GET_BACKOFF_SECONDS) - 1)
            ]
            delay = error.retry_after if error.retry_after is not None else fallback
            if stop_event.wait(delay):
                raise RuntimeError("任务已由用户停止") from error
    raise AssertionError("queue GET retry loop exhausted unexpectedly")


def raise_for_fal_payload_error(payload: Dict[str, Any], phase: str) -> None:
    """Detect fal's documented error/error_type fields, including SDK wrappers."""

    candidates = [payload]
    if isinstance(payload.get("data"), dict):
        candidates.append(payload["data"])
    for candidate in candidates:
        error_value = candidate.get("error")
        error_type = candidate.get("error_type")
        if not error_value and not error_type:
            continue
        if isinstance(error_value, str):
            detail = error_value
        elif error_value:
            detail = json.dumps(error_value, ensure_ascii=False)
        else:
            detail = "未提供详细错误"
        type_label = f" ({error_type})" if error_type else ""
        raise RuntimeError(f"fal {phase}失败{type_label}: {detail[:1500]}")


def is_allowed_https_url(
    url: str,
    exact_hosts: Optional[set[str]] = None,
    root_hosts: Optional[set[str]] = None,
) -> bool:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError:
        return False
    if (
        parsed.scheme != "https"
        or not host
        or parsed.username
        or parsed.password
        or port not in {None, 443}
    ):
        return False
    if exact_hosts and host in exact_hosts:
        return True
    if root_hosts and any(host == root or host.endswith(f".{root}") for root in root_hosts):
        return True
    return False


def require_queue_url(value: Any, field_name: str) -> str:
    url = str(value or "")
    if not is_allowed_https_url(url, exact_hosts=ALLOWED_QUEUE_HOSTS):
        raise RuntimeError(f"fal 返回了不受信任的 {field_name}")
    return url


def fal_generate(
    endpoint: str,
    arguments: Dict[str, Any],
    api_key: str,
    stop_event: threading.Event,
    progress_callback,
) -> Tuple[Dict[str, Any], str, float, Dict[str, Any]]:
    if stop_event.is_set() or SHUTTING_DOWN.is_set():
        raise RuntimeError("任务已由用户停止")
    started = time.monotonic()
    submit_url = f"https://queue.fal.run/{endpoint}"
    # Raw REST queue submission takes model arguments directly. Never retry
    # this POST: a lost response could otherwise create a duplicate paid job.
    submitted = request_json(
        submit_url,
        "POST",
        api_key,
        arguments,
        timeout=120,
        extra_headers={"X-Fal-Store-IO": "0"},
    )
    request_id = str(submitted.get("request_id", ""))
    status_url = submitted.get("status_url")
    response_url = submitted.get("response_url")
    if not request_id or not status_url or not response_url:
        raise RuntimeError(f"fal 返回缺少队列地址: {json.dumps(submitted, ensure_ascii=False)[:1000]}")
    status_url = require_queue_url(status_url, "status_url")
    response_url = require_queue_url(response_url, "response_url")
    cancel_url = ""
    if submitted.get("cancel_url"):
        cancel_url = require_queue_url(submitted["cancel_url"], "cancel_url")
    progress_callback("SUBMITTED", request_id, cancel_url)

    while not stop_event.is_set():
        status = request_queue_json_with_retry(
            status_url,
            api_key,
            timeout=90,
            stop_event=stop_event,
        )
        state = str(status.get("status", "UNKNOWN"))
        progress_callback(state, request_id, cancel_url)
        if state == "COMPLETED":
            raise_for_fal_payload_error(status, "队列任务")
            result = request_queue_json_with_retry(
                response_url,
                api_key,
                timeout=120,
                stop_event=stop_event,
            )
            raise_for_fal_payload_error(result, "结果读取")
            result_ready_seconds = round(time.monotonic() - started, 3)
            generation_timing = build_generation_timing(
                status,
                result,
                result_ready_seconds,
            )
            return result, request_id, result_ready_seconds, generation_timing
        if state in {"FAILED", "CANCELLED"}:
            raise RuntimeError(f"fal 任务 {state}: {json.dumps(status, ensure_ascii=False)[:1500]}")
        stop_event.wait(0.9 if state == "IN_PROGRESS" else 1.4)
    raise RuntimeError("任务已由用户停止")


def download_file(url: str, destination: Path) -> None:
    if not is_allowed_https_url(url, root_hosts=ALLOWED_MEDIA_ROOTS):
        raise RuntimeError("fal 返回了不受信任的视频下载地址")
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": f"FrameCurrent/{APP_VERSION}"})
    try:
        with open_without_redirects(request, timeout=180) as response, partial.open("wb") as target:
            declared_size = int(response.headers.get("Content-Length", "0") or "0")
            if declared_size > MAX_VIDEO_BYTES:
                raise RuntimeError("视频文件超过 512MB 安全上限")
            total = 0
            while True:
                chunk = response.read(min(1024 * 1024, MAX_VIDEO_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_VIDEO_BYTES:
                    raise RuntimeError("视频文件超过 512MB 安全上限")
                target.write(chunk)
        if partial.stat().st_size < 1024:
            raise RuntimeError("下载的视频文件过小")
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def compile_swift_tool(name: str) -> Path:
    source = SCRIPT_ROOT / f"{name}.swift"
    binary = BIN_ROOT / name
    BIN_ROOT.mkdir(parents=True, exist_ok=True)
    if not binary.exists() or source.stat().st_mtime > binary.stat().st_mtime:
        completed = subprocess.run(
            ["/usr/bin/swiftc", "-O", str(source), "-o", str(binary)],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if completed.returncode != 0:
            raise RuntimeError(f"Swift媒体工具编译失败: {completed.stderr[-3000:]}")
    return binary


def prepare_media_tools() -> None:
    """Fail locally before the first billable request, including on direct launches."""
    if sys.platform != "darwin":
        raise RuntimeError("本地环境未就绪：当前版本仅支持 macOS")
    for tool in ("/usr/bin/sips", "/usr/bin/avmediainfo", "/usr/bin/swiftc"):
        if not os.access(tool, os.X_OK):
            raise RuntimeError("本地环境未就绪：请运行 doctor.command 检查 Apple 媒体工具")
    try:
        SESSION_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=SESSION_ROOT) as probe:
            probe.write(b"FrameCurrent write check")
        for command, marker in ((["/usr/bin/avmediainfo", "--help"], "avmediainfo"),
                                (["/usr/bin/sips", "--version"], "sips")):
            result = subprocess.run(command, capture_output=True, text=True, timeout=15)
            if marker not in (result.stdout + result.stderr).lower():
                raise RuntimeError("Apple 媒体工具无法正常运行")
        for name in ("extract_frame", "image_similarity", "merge_clips"):
            binary = compile_swift_tool(name)
            if not os.access(binary, os.X_OK):
                raise RuntimeError("编译后的媒体工具无法执行")
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            if result.returncode != 1 or f"usage: {name}" not in result.stderr:
                raise RuntimeError("编译后的媒体工具启动检查失败")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(
            "本地环境未就绪：媒体工具编译或作品目录写入失败；尚未提交付费生成。"
            "请运行 doctor.command，检查 Apple 命令行工具和文件夹权限。"
        ) from error


def extract_frame(video_path: Path, output_path: Path, position: str) -> Path:
    tool = compile_swift_tool("extract_frame")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [str(tool), str(video_path), str(output_path), position],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if completed.returncode != 0 or not output_path.exists():
        raise RuntimeError(f"视频帧提取失败: {completed.stderr[-2500:]}")
    return output_path


def compare_images(first: Path, second: Path) -> float:
    tool = compile_swift_tool("image_similarity")
    completed = subprocess.run(
        [str(tool), str(first), str(second)], capture_output=True, text=True, timeout=60
    )
    if completed.returncode != 0:
        raise RuntimeError(f"衔接评分失败: {completed.stderr[-2000:]}")
    return round(float(completed.stdout.strip()), 4)


def media_info(video_path: Path) -> str:
    # Do not use avmediainfo's --brief mode here. AVFoundation exports can
    # legitimately retain more than one AAC format description on a single
    # merged audio track; brief mode then replaces the codec name with only
    # "N format descriptions available". The full report identifies every
    # description as MPEG-4 AAC, allowing validate_media to enforce the codec
    # requirement without rejecting a valid production merge.
    completed = subprocess.run(
        ["/usr/bin/avmediainfo", str(video_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if completed.returncode != 0 or not completed.stdout.strip():
        raise RuntimeError(f"avmediainfo 验证失败: {completed.stderr[-1500:]}")
    return completed.stdout.strip()[:MAX_MEDIA_INFO_CHARS]


def media_track_formats(receipt: str, media_kinds: Tuple[str, ...]) -> Tuple[bool, List[str]]:
    """Return format descriptions belonging only to the requested track types."""
    headers = list(re.finditer(r"(?m)^Track \d+:\s+([^\s,']+)", receipt))
    has_track = False
    formats: List[str] = []
    for index, header in enumerate(headers):
        if header.group(1) not in media_kinds:
            continue
        has_track = True
        block_end = headers[index + 1].start() if index + 1 < len(headers) else len(receipt)
        block = receipt[header.start():block_end]
        formats.extend(
            match.group(1).strip()
            for match in re.finditer(r"Format:\s*([^,\r\n]+)", block)
        )
    return has_track, formats


def validate_media(
    video_path: Path,
    expected_duration: Optional[float] = None,
    *,
    allow_generation_rounding: bool = False,
    require_audio: bool = False,
    aspect_ratio: str = "9:16",
) -> Dict[str, Any]:
    if aspect_ratio not in ASPECT_RATIOS:
        raise ValueError("画面比例必须是9:16或16:9")
    receipt = media_info(video_path)
    duration_match = re.search(r"Duration:\s*([0-9.]+) seconds", receipt)
    dimension_match = re.search(r"Dimensions:\s*(\d+) x (\d+)", receipt)
    frame_rate_match = re.search(r"([0-9.]+) fps", receipt)
    video_present, video_formats = media_track_formats(receipt, ("Video",))
    # Apple's avmediainfo labels an audio track as "Sound", not "Audio".
    has_audio, audio_formats = media_track_formats(receipt, ("Audio", "Sound"))
    has_video = video_present
    if not has_video or not duration_match or not dimension_match:
        raise RuntimeError("媒体验证失败：缺少可识别的视频轨、时长或尺寸")
    duration = float(duration_match.group(1))
    width, height = int(dimension_match.group(1)), int(dimension_match.group(2))
    frame_rate = float(frame_rate_match.group(1)) if frame_rate_match else H3_FALLBACK_FRAME_RATE
    if not math.isfinite(frame_rate) or frame_rate <= 0:
        frame_rate = H3_FALLBACK_FRAME_RATE
    if not video_formats or any(not value.startswith("H.264") for value in video_formats):
        raise RuntimeError("媒体验证失败：视频编码不是 H.264")
    if require_audio and not has_audio:
        raise RuntimeError("媒体验证失败：H3 Max 视频缺少原生音轨")
    if has_audio and (
        not audio_formats
        or any(not value.startswith("MPEG-4 AAC") for value in audio_formats)
    ):
        raise RuntimeError("媒体验证失败：音频编码不是 AAC")

    duration_delta = 0.0
    normalization_seconds = 0.0
    if expected_duration is not None:
        duration_delta = duration - expected_duration
        if allow_generation_rounding:
            # H3 Max can return a few complete frames beyond the requested
            # integer duration (observed: 5.167s at 24fps, i.e. four frames).
            # Accept at most five extra frames, but never accept a materially
            # short clip because the merger cannot safely invent missing video.
            max_overrun = H3_MAX_GENERATION_EXTRA_FRAMES / frame_rate + 0.006
            valid_duration = (
                duration_delta >= -H3_GENERATION_UNDERRUN_SECONDS
                and duration_delta <= max_overrun
            )
            normalization_seconds = max(0.0, duration_delta)
        else:
            # A final composition must stay effectively exact; the Swift
            # merger already targets an integer CMTime timeline.
            valid_duration = abs(duration_delta) <= FINAL_DURATION_TOLERANCE_SECONDS
        if not valid_duration:
            raise RuntimeError(
                f"媒体验证失败：实际时长 {duration:.3f} 秒，预期约 {expected_duration:.3f} 秒"
            )
    validate_aspect_dimensions(width, height, aspect_ratio)
    return {
        "duration": round(duration, 3),
        "target_duration": round(expected_duration, 3) if expected_duration is not None else None,
        "duration_delta": round(duration_delta, 3),
        "normalization_seconds": round(normalization_seconds, 3),
        "width": width,
        "height": height,
        "aspect_ratio": aspect_ratio,
        "frame_rate": round(frame_rate, 3),
        "has_audio": has_audio,
        "audio_codec": "AAC" if has_audio else None,
        "video_codec": "H.264",
        "validation": "PASS",
    }


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_session_clips(session: "SessionState") -> Tuple[Path, Dict[str, Any]]:
    duration_mode = session.config.get("duration_mode", "fixed")
    clips = list(session.clips)
    expected_duration = sum(int(clip["duration"]) for clip in clips)
    if not clips:
        raise RuntimeError("成片合并前检查失败：没有已完成片段")
    if expected_duration != session.generated_seconds:
        raise RuntimeError("成片合并前检查失败：已完成时长与片段记录不一致")
    if duration_mode == "fixed" and len(clips) != session.config["total_clips"]:
        raise RuntimeError("成片合并前检查失败：片段数量不完整")
    if duration_mode == "fixed" and expected_duration != session.config["duration_seconds"]:
        raise RuntimeError("成片合并前检查失败：固定时长片段不完整")

    aspect_slug = session.config.get("aspect_ratio", "9:16").replace(":", "x")
    output_name = f"h3-max-{expected_duration}s-{aspect_slug}.mp4"
    output_path = session.directory / output_name
    inputs = [session.directory / clip["filename"] for clip in clips]
    if any(not path.is_file() for path in inputs):
        raise RuntimeError("成片合并前检查失败：片段文件不完整")
    tool = compile_swift_tool("merge_clips")
    completed = subprocess.run(
        [str(tool), str(output_path), *map(str, inputs)],
        capture_output=True,
        text=True,
        timeout=max(600, expected_duration * 8),
    )
    if completed.returncode != 0 or not output_path.is_file():
        raise RuntimeError(f"完整视频合并失败: {completed.stderr[-3000:]}")
    validation = validate_media(
        output_path,
        expected_duration=expected_duration,
        require_audio=True,
        aspect_ratio=session.config.get("aspect_ratio", "9:16"),
    )
    validation["size_bytes"] = output_path.stat().st_size
    validation["sha256"] = file_sha256(output_path)
    return output_path, validation


def data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/jpeg;base64,{encoded}"


def public_error_message(error: str) -> str:
    if not error:
        return ""
    lowered = error.lower()
    if "本地环境" in error:
        return "本地环境未就绪：请运行 doctor.command 检查媒体工具和目录权限；本次未提交付费生成"
    if "512mb" in lowered or "下载的视频文件过小" in error:
        return "视频下载未通过文件检查；已提交的生成可能计费，请先检查服务商结果，不要反复开播"
    if "swift" in lowered or any(word in error for word in ("合并", "媒体", "视频文件不存在", "片段文件不完整")):
        return "本地视频处理或校验失败；可先下载已保存片段，再运行 doctor.command 检查环境"
    if "exhausted balance" in lowered or "insufficient balance" in lowered or "余额" in error:
        return "fal 账户余额不足，任务没有被受理；请充值后重试"
    if "budget" in lowered or "预算" in lowered:
        return "本地预计费用上限不足，软件已停止提交新的画面"
    if "401" in lowered or "403" in lowered or "api key" in lowered or "密钥" in lowered:
        return "fal 密钥无效、权限不足或账户不可用"
    if "safety" in lowered or "内容安全" in lowered:
        return "本幕没有通过内容安全检查，请调整画面描述"
    if "网络" in error or "timeout" in lowered or "timed out" in lowered:
        return "生成服务连接暂时不稳定，请稍后重试"
    return "本幕生成失败；详细信息只保留在本机运行日志中"


@dataclass
class SessionState:
    session_id: str
    config: Dict[str, Any]
    api_key: str = field(repr=False)
    client_request_hash: str = field(default="", repr=False)
    created_at: str = field(default_factory=utc_now)
    status: str = "preparing"
    message: str = "正在准备"
    clips: List[Dict[str, Any]] = field(default_factory=list)
    generated_seconds: int = 0
    submitted_seconds: int = 0
    spent_estimate_usd: float = 0.0
    active_request_id: str = field(default="", repr=False)
    active_cancel_url: str = field(default="", repr=False)
    cancel_attempted_request_id: str = field(default="", repr=False)
    active_queue_state: str = ""
    error: str = ""
    completion_reason: str = ""
    completed_at: str = ""
    final_filename: str = ""
    final_validation: Dict[str, Any] = field(default_factory=dict)
    stop_event: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    @property
    def directory(self) -> Path:
        return SESSION_ROOT / self.session_id

    def public(self) -> Dict[str, Any]:
        with self.lock:
            config_keys = {
                "duration_mode",
                "duration_seconds",
                "duration_label",
                "clip_duration",
                "clip_schedule",
                "total_clips",
                "resolution",
                "aspect_ratio",
                "preset",
                "preset_name",
                "custom_channel_name",
                "estimated_cost_usd",
                "max_budget_usd",
                "playback_mode",
            }
            config = {key: self.config[key] for key in config_keys if key in self.config}
            public_clips = [
                {
                    "index": clip["index"],
                    "number": clip["number"],
                    "url": clip["url"],
                    "duration": clip["duration"],
                    "generation_seconds": clip.get("generation_seconds"),
                    "generation_time_seconds": clip.get("generation_time_seconds"),
                    "generation_time_source": clip.get("generation_time_source", ""),
                    "first_frame_url": clip.get("first_frame_url"),
                    "last_frame_url": clip.get("last_frame_url"),
                    "join_similarity": clip.get("join_similarity"),
                    "continuity_check": clip.get("continuity_check", "not_checked"),
                    "semantic_check": clip.get("semantic_check", "manual_review_required"),
                    "media": {
                        key: clip.get("media", {}).get(key)
                        for key in {
                            "duration",
                            "width",
                            "height",
                            "aspect_ratio",
                            "has_audio",
                            "video_codec",
                            "validation",
                        }
                        if key in clip.get("media", {})
                    },
                    "ready_at": clip.get("ready_at", ""),
                }
                for clip in self.clips
            ]
            generation_times = [
                float(clip["generation_seconds"])
                for clip in self.clips
                if safe_float(clip.get("generation_seconds"), 0) > 0
            ]
            duration_mode = self.config.get("duration_mode", "fixed")
            if duration_mode == "fixed":
                total_clips = int(self.config.get("total_clips") or 0)
                remaining_clips: Optional[int] = max(0, total_clips - len(self.clips))
                eta_seconds = (
                    int(round(sum(generation_times) / len(generation_times) * remaining_clips))
                    if generation_times and self.status in {"preparing", "generating"}
                    else (0 if self.status in {"finalizing", "complete"} else None)
                )
            else:
                remaining_clips = None
                eta_seconds = None
            final_ready = (
                self.status == "complete"
                and bool(self.final_filename)
                and (self.directory / self.final_filename).is_file()
            )
            final_validation = {
                key: self.final_validation[key]
                for key in {
                    "duration",
                    "width",
                    "height",
                    "aspect_ratio",
                    "has_audio",
                    "video_codec",
                    "validation",
                    "size_bytes",
                    "sha256",
                }
                if key in self.final_validation
            }
            return {
                "session_id": self.session_id,
                "created_at": self.created_at,
                "completed_at": self.completed_at,
                "status": self.status,
                "message": self.message,
                "completion_reason": self.completion_reason,
                "clips": public_clips,
                "generated_seconds": self.generated_seconds,
                "submitted_seconds": self.submitted_seconds,
                "target_seconds": (
                    self.config.get("duration_seconds") if duration_mode == "fixed" else None
                ),
                "spent_estimate_usd": round(self.spent_estimate_usd, 2),
                "max_budget_usd": self.config["max_budget_usd"],
                "active_queue_state": self.active_queue_state,
                "error": public_error_message(self.error),
                "config": config,
                "ready_to_preview": len(self.clips) >= 2 or (
                    len(self.clips) >= 1 and self.status in {"finalizing", "complete"}
                ),
                "buffer_seconds": self.generated_seconds,
                "eta_seconds": eta_seconds,
                "next_chapter": (
                    "节目已结束；请播放检查动作与空间逻辑"
                    if self.status == "complete"
                    else (
                        f"第 {len(self.clips) + 1} 幕将先保持当前运动，再逐步展开远景"
                        if duration_mode == "unlimited" or remaining_clips
                        else "所有画面已生成；请播放检查动作与空间逻辑"
                    )
                ),
                "finalizing": self.status == "finalizing",
                "ready_to_download": final_ready,
                "final_filename": self.final_filename if final_ready else "",
                "final_url": f"/media/{self.session_id}/{self.final_filename}" if final_ready else "",
                "download_url": f"/download/{self.session_id}/video.mp4" if final_ready else "",
                "final_validation": final_validation if final_ready else {},
            }

    def persist(self) -> None:
        # Stop requests, queue callbacks and the worker can persist concurrently.
        # Keep the public snapshot and atomic rename inside the same session lock
        # so they cannot contend for the shared manifest.json.tmp path.
        with self.lock:
            payload = self.public()
            if self.client_request_hash:
                payload["_client_request_hash"] = self.client_request_hash
            atomic_json(self.directory / "manifest.json", payload)


SESSIONS: Dict[str, SessionState] = {}
CLIENT_REQUEST_SESSIONS: Dict[str, str] = {}
SESSIONS_LOCK = threading.RLock()


def best_effort_cancel_fal_request(cancel_url: str, api_key: str) -> str:
    """Ask fal to cancel once, without turning a cancellation race into failure."""

    try:
        trusted_url = require_queue_url(cancel_url, "cancel_url")
        response = request_json(trusted_url, "PUT", api_key, timeout=15)
        return str(response.get("status") or "CANCELLATION_REQUESTED")
    except FalAPIError as error:
        detail = str(error).upper()
        already_completed = (
            "ALREADY_COMPLETED" in detail
            or "ALREADY COMPLETED" in detail
            or "REQUEST HAS COMPLETED" in detail
        )
        if error.status_code in {400, 409} and already_completed:
            return "ALREADY_COMPLETED"
        if error.status_code == 404 and "NOT_FOUND" in detail:
            return "NOT_FOUND"
        return "CANCEL_FAILED"
    except Exception:
        return "CANCEL_FAILED"


def cancel_active_fal_request(session: SessionState) -> str:
    """Atomically claim and cancel the active fal request at most once."""

    with session.lock:
        request_id = session.active_request_id
        cancel_url = session.active_cancel_url
        api_key = session.api_key
        if not request_id or not cancel_url or not api_key:
            return "NO_ACTIVE_REQUEST"
        if session.cancel_attempted_request_id == request_id:
            return "CANCEL_ALREADY_ATTEMPTED"
        session.cancel_attempted_request_id = request_id

    outcome = best_effort_cancel_fal_request(cancel_url, api_key)
    with session.lock:
        if outcome == "CANCELLATION_REQUESTED" and session.active_request_id == request_id:
            session.active_queue_state = outcome
    return outcome


def stop_generation_session(session: SessionState) -> str:
    claimed_request_id = ""
    claimed_cancel_url = ""
    claimed_api_key = ""
    immediate_outcome = ""
    with session.lock:
        session.stop_event.set()
        if session.status in {"preparing", "generating", "finalizing"}:
            session.message = (
                "正在停止；不会再提交新任务，随后将导出已完成画面"
                if session.config.get("duration_mode") == "unlimited" and session.clips
                else "正在停止；不会再提交新任务"
            )
        claimed_request_id = session.active_request_id
        claimed_cancel_url = session.active_cancel_url
        claimed_api_key = session.api_key
        if not claimed_request_id or not claimed_cancel_url or not claimed_api_key:
            immediate_outcome = "NO_ACTIVE_REQUEST"
        elif session.cancel_attempted_request_id == claimed_request_id:
            immediate_outcome = "CANCEL_ALREADY_ATTEMPTED"
        else:
            # Claim the cancellation while setting the stop event under the same
            # lock. The worker can now finalize completed clips without racing
            # away with the only copy of the active cancel URL.
            session.cancel_attempted_request_id = claimed_request_id
    session.persist()
    if immediate_outcome:
        outcome = immediate_outcome
    else:
        outcome = best_effort_cancel_fal_request(claimed_cancel_url, claimed_api_key)
        with session.lock:
            if (
                outcome == "CANCELLATION_REQUESTED"
                and session.active_request_id == claimed_request_id
            ):
                session.active_queue_state = outcome
    session.persist()
    return outcome


def validate_key_shape(api_key: str) -> None:
    # fal documents only the key_id:key_secret contract; its own examples are
    # opaque rather than UUID/hex-only, so do not reject valid future formats.
    if len(api_key) > 512 or not re.fullmatch(r"[A-Za-z0-9._-]+:[A-Za-z0-9._-]+", api_key):
        raise ValueError("fal API Key 格式无效")


def check_fal_key(api_key: str) -> Dict[str, Any]:
    validate_key_shape(api_key)
    query = urllib.parse.urlencode(
        [
            ("endpoint_id", "minimax/h3-max/text-to-video"),
            ("endpoint_id", "minimax/h3-max/image-to-video"),
        ]
    )
    try:
        pricing = request_json(
            f"https://api.fal.ai/v1/models/pricing?{query}",
            "GET",
            api_key,
            timeout=45,
        )
    except RuntimeError as error:
        if "HTTP 401" in str(error):
            raise ValueError("fal API Key 无效或已被撤销") from error
        if "HTTP 403" in str(error):
            raise ValueError("fal API Key 没有价格查询权限") from error
        raise
    balance: Optional[Dict[str, Any]] = None
    balance_note = (
        "价格接口鉴权通过；余额需要 fal 管理员权限才能读取，"
        "是否可生成仍以模型任务实际提交结果为准"
    )
    try:
        billing = request_json(
            "https://api.fal.ai/v1/account/billing?expand=credits",
            "GET",
            api_key,
            timeout=30,
        )
        credits = billing.get("credits")
        if isinstance(credits, dict):
            balance = {
                "current_balance": credits.get("current_balance"),
                "currency": credits.get("currency", "USD"),
            }
            balance_note = "余额已读取；是否可生成仍以模型任务实际提交结果为准"
    except RuntimeError as error:
        if "HTTP 403" not in str(error):
            # Pricing access does not prove balance, model access, queue
            # availability, or that a generation submission will be accepted.
            balance_note = (
                "价格接口鉴权通过；余额服务暂时不可用，"
                "是否可生成仍以模型任务实际提交结果为准"
            )
    return {
        "ok": True,
        "provider": "fal",
        "message": "fal 价格接口鉴权通过",
        "pricing_verified": bool(pricing),
        "generation_verified": False,
        "standard_output_rates_usd": RESOLUTION_RATES_USD,
        "balance": balance,
        "balance_note": balance_note,
    }


def mark_session_stopped(session: SessionState, completion_reason: str) -> None:
    with session.lock:
        session.status = "stopped"
        session.message = "已停止续写；已提交的一幕可能仍会产生费用"
        session.error = ""
        session.completion_reason = completion_reason
        session.active_request_id = ""
        session.active_cancel_url = ""
        session.cancel_attempted_request_id = ""
        session.completed_at = utc_now()
    session.persist()


def finalize_completed_session(session: SessionState, completion_reason: str) -> None:
    with session.lock:
        if not session.clips:
            raise RuntimeError("没有已完成片段可供合并")
        session.status = "finalizing"
        session.message = "正在整理已完成画面并导出节目"
        session.active_queue_state = "FINALIZING"
        session.active_request_id = ""
        session.active_cancel_url = ""
        session.cancel_attempted_request_id = ""
    session.persist()

    final_path, final_validation = merge_session_clips(session)
    messages = {
        "target_reached": "完整视频已保存，请先播放检查动作逻辑",
        "user_stopped": "已停止续写并保存已完成画面，请先播放检查动作逻辑",
        "budget_guard_reached": "下一幕将超出本地预计费用上限，已保存现有画面",
    }
    with session.lock:
        session.final_filename = final_path.name
        session.final_validation = final_validation
        session.status = "complete"
        session.message = messages.get(completion_reason, messages["target_reached"])
        session.completion_reason = completion_reason
        session.error = ""
        session.active_queue_state = "READY"
        session.completed_at = utc_now()
    session.persist()


def run_session(session: SessionState) -> None:
    previous_last: Optional[Path] = None
    with session.lock:
        previous_data_uri: Optional[str] = session.config.pop("start_image", None)
        duration_mode = session.config.get("duration_mode", "fixed")
    termination_reason = ""
    generation_error: Optional[Exception] = None

    try:
        session.directory.mkdir(parents=True, exist_ok=True)
        with session.lock:
            session.message = "正在检查本地媒体工具；尚未提交付费生成"
        session.persist()
        prepare_media_tools()
        with session.lock:
            session.status = "generating"
            session.message = "AI 正在写下第一幕"
        session.persist()

        index = 0
        while True:
            if duration_mode == "fixed":
                schedule = session.config["clip_schedule"]
                if index >= len(schedule):
                    termination_reason = "target_reached"
                    break

            if session.stop_event.is_set() or SHUTTING_DOWN.is_set():
                termination_reason = "user_stopped"
                break

            if duration_mode == "fixed":
                segment_duration = schedule[index]
            else:
                segment_duration = session.config["clip_duration"]
                with session.lock:
                    submitted_seconds = session.submitted_seconds
                if not budget_allows_segment(
                    session.config,
                    submitted_seconds,
                    segment_duration,
                ):
                    termination_reason = "budget_guard_reached"
                    break

            prompt = build_prompt(session.config, index, previous_data_uri is not None)
            clip_filename = f"clip-{index + 1:03d}.mp4"
            clip_path = session.directory / clip_filename
            first_frame = session.directory / f"clip-{index + 1:03d}-first.jpg"
            last_frame = session.directory / f"clip-{index + 1:03d}-last.jpg"

            with session.lock:
                projected_cost = estimate_cost_usd(
                    session.submitted_seconds + segment_duration,
                    session.config["resolution"],
                )
                if projected_cost > session.config["max_budget_usd"] + 0.001:
                    if duration_mode == "unlimited":
                        termination_reason = "budget_guard_reached"
                    else:
                        raise RuntimeError(
                            f"预算保护已阻止下一幕：预计将达到 ${projected_cost:.2f}，"
                            f"高于本次上限 ${session.config['max_budget_usd']:.2f}"
                        )
                else:
                    if duration_mode == "unlimited":
                        session.message = f"AI 正在续写第 {index + 1} 幕"
                    else:
                        session.message = (
                            f"AI 正在续写第 {index + 1}/{session.config['total_clips']} 幕"
                        )
                    session.active_queue_state = "PREPARING"
            if termination_reason:
                break
            session.persist()

            if session.stop_event.is_set():
                termination_reason = "user_stopped"
                break

            if previous_data_uri:
                endpoint = "minimax/h3-max/image-to-video"
                arguments: Dict[str, Any] = {
                    "prompt": prompt,
                    "duration": segment_duration,
                    "resolution": session.config["resolution"],
                    "prompt_expansion_mode": "balanced",
                    "enable_safety_checker": True,
                    "image_url": previous_data_uri,
                }
            else:
                endpoint = "minimax/h3-max/text-to-video"
                arguments = {
                    "prompt": prompt,
                    "duration": segment_duration,
                    "resolution": session.config["resolution"],
                    "prompt_expansion_mode": "balanced",
                    "enable_safety_checker": True,
                    "aspect_ratio": session.config["aspect_ratio"],
                }

            submission_counted = False

            def progress(
                state: str,
                active_request: str,
                active_cancel_url: str,
            ) -> None:
                nonlocal submission_counted
                with session.lock:
                    if active_request != session.active_request_id:
                        session.cancel_attempted_request_id = ""
                    if not submission_counted and state in {
                        "SUBMITTED",
                        "IN_QUEUE",
                        "IN_PROGRESS",
                        "COMPLETED",
                    }:
                        session.submitted_seconds += segment_duration
                        session.spent_estimate_usd = estimate_cost_usd(
                            session.submitted_seconds, session.config["resolution"]
                        )
                        submission_counted = True
                    session.active_queue_state = state
                    session.active_request_id = active_request
                    session.active_cancel_url = active_cancel_url
                if state == "SUBMITTED":
                    session.persist()
                    # Covers a stop click that arrived while the submission POST
                    # was still waiting and no cancel URL was available yet.
                    if session.stop_event.is_set():
                        cancel_active_fal_request(session)

            try:
                result, _request_id, generation_seconds, generation_timing = fal_generate(
                    endpoint,
                    arguments,
                    session.api_key,
                    session.stop_event,
                    progress,
                )
            finally:
                # A reference image may be several megabytes. Drop both the
                # argument and loop reference as soon as the provider call ends.
                arguments.pop("image_url", None)
                previous_data_uri = None
            video = result.get("video") or (result.get("data") or {}).get("video")
            if not isinstance(video, dict) or not video.get("url"):
                raise RuntimeError(f"fal 结果没有视频地址: {json.dumps(result, ensure_ascii=False)[:1200]}")
            download_file(str(video["url"]), clip_path)

            media_validation = validate_media(
                clip_path,
                expected_duration=segment_duration,
                allow_generation_rounding=True,
                require_audio=True,
                aspect_ratio=session.config["aspect_ratio"],
            )
            extract_frame(clip_path, first_frame, "first")
            extract_frame(clip_path, last_frame, "last")
            similarity = None
            if previous_last is not None:
                similarity = compare_images(previous_last, first_frame)
            previous_last = last_frame
            previous_data_uri = data_uri(last_frame)

            clip = {
                "index": index,
                "number": index + 1,
                "filename": clip_filename,
                "url": f"/media/{session.session_id}/{clip_filename}",
                "duration": segment_duration,
                "generation_seconds": generation_seconds,
                "generation_time_seconds": generation_timing.get("seconds"),
                "generation_time_source": generation_timing.get("source", "unavailable"),
                "join_similarity": round(similarity, 6) if similarity is not None else None,
                "continuity_check": (
                    "first_segment"
                    if similarity is None
                    else ("boundary_matched" if similarity >= BOUNDARY_SIMILARITY_MIN else "boundary_warning")
                ),
                "semantic_check": "manual_review_required",
                "first_frame_url": f"/media/{session.session_id}/{first_frame.name}",
                "last_frame_url": f"/media/{session.session_id}/{last_frame.name}",
                "media": media_validation,
                "ready_at": utc_now(),
            }
            with session.lock:
                session.clips.append(clip)
                session.generated_seconds += segment_duration
                session.active_request_id = ""
                session.active_cancel_url = ""
                session.cancel_attempted_request_id = ""
                session.active_queue_state = "READY"
            session.persist()
            index += 1
    except Exception as error:
        if session.stop_event.is_set():
            termination_reason = "user_stopped"
        else:
            traceback.print_exc()
            generation_error = error

    try:
        if generation_error is not None:
            with session.lock:
                session.status = "failed"
                session.message = "生成中止"
                session.error = str(generation_error)[:2000]
                session.completion_reason = ""
                session.active_request_id = ""
                session.active_cancel_url = ""
                session.cancel_attempted_request_id = ""
                session.completed_at = utc_now()
            session.persist()
        elif termination_reason == "target_reached":
            finalize_completed_session(session, termination_reason)
        elif duration_mode == "unlimited" and termination_reason in {
            "user_stopped",
            "budget_guard_reached",
        }:
            if session.clips:
                finalize_completed_session(session, termination_reason)
            else:
                mark_session_stopped(session, termination_reason)
        else:
            mark_session_stopped(session, termination_reason or "user_stopped")
    except Exception as error:
        traceback.print_exc()
        with session.lock:
            session.status = "failed"
            session.message = "成片导出失败"
            session.error = str(error)[:2000]
            session.completion_reason = ""
            session.active_request_id = ""
            session.active_cancel_url = ""
            session.cancel_attempted_request_id = ""
            session.completed_at = utc_now()
        session.persist()
    finally:
        with session.lock:
            session.api_key = ""
            session.config.pop("start_image", None)
            session.active_request_id = ""
            session.active_cancel_url = ""
            session.cancel_attempted_request_id = ""
        previous_data_uri = None


class UnsupportedMediaTypeError(ValueError):
    """Raised when a state-changing endpoint does not receive JSON."""


class AppHandler(SimpleHTTPRequestHandler):
    server_version = f"FrameCurrent/{APP_VERSION}"

    def log_message(self, format_string: str, *args: Any) -> None:
        sys.stdout.write("[%s] %s\n" % (self.log_date_time_string(), format_string % args))

    def _security_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")

    def _json(self, payload: Dict[str, Any], status: int = 200) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._security_headers()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(raw)

    def _local_authority(self) -> Optional[Tuple[str, int]]:
        values = self.headers.get_all("Host") or []
        if len(values) != 1:
            return None
        raw_host = values[0].strip()
        if not raw_host or any(character.isspace() for character in raw_host):
            return None
        parsed = urllib.parse.urlsplit(f"//{raw_host}")
        if parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return None
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            requested_port = parsed.port
        except ValueError:
            return None
        server_port = int(self.server.server_address[1])
        effective_port = requested_port if requested_port is not None else 80
        if host not in LOCAL_REQUEST_HOSTS or effective_port != server_port:
            return None
        return host, server_port

    def _origin_is_allowed(self, authority: Tuple[str, int]) -> bool:
        values = self.headers.get_all("Origin") or []
        if not values:
            return True
        if len(values) != 1:
            return False
        raw_origin = values[0].strip()
        if not raw_origin or raw_origin == "null":
            return False
        parsed = urllib.parse.urlsplit(raw_origin)
        if (
            parsed.scheme.lower() != "http"
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            return False
        host = (parsed.hostname or "").lower().rstrip(".")
        try:
            port = parsed.port if parsed.port is not None else 80
        except ValueError:
            return False
        return (host, port) == authority

    def _read_json(self) -> Dict[str, Any]:
        content_types = self.headers.get_all("Content-Type") or []
        if len(content_types) != 1:
            raise UnsupportedMediaTypeError("请求必须使用 application/json")
        media_type = content_types[0].split(";", 1)[0].strip().lower()
        if media_type != "application/json":
            raise UnsupportedMediaTypeError("请求必须使用 application/json")
        if self.headers.get("Transfer-Encoding"):
            raise ValueError("不支持 Transfer-Encoding 请求")
        content_lengths = self.headers.get_all("Content-Length") or []
        if len(content_lengths) != 1:
            raise ValueError("请求体长度无效")
        try:
            length = int(content_lengths[0])
        except (TypeError, ValueError) as error:
            raise ValueError("请求体长度无效") from error
        if length <= 0 or length > MAX_JSON_BYTES:
            raise ValueError("请求体为空或过大")
        raw = self.rfile.read(length)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("请求体必须是JSON对象")
        return payload

    def do_HEAD(self) -> None:  # noqa: N802
        # The inherited handler would inspect files outside the public web root.
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        if self._local_authority() is None:
            self._json({"error": "仅接受当前本机服务地址"}, HTTPStatus.MISDIRECTED_REQUEST)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/health":
            swift_available = Path("/usr/bin/swiftc").exists()
            with SESSIONS_LOCK:
                active = next((session for session in SESSIONS.values()
                               if session.status in {"preparing", "generating", "finalizing"}), None)
                active_summary = {"session_id": active.session_id, "preset": active.config["preset"]} if active else None
            self._json(
                {
                    "ok": not SHUTTING_DOWN.is_set(),
                    "app_id": APP_ID,
                    "instance_id": INSTANCE_ID,
                    "active_session": active_summary,
                    "version": APP_VERSION,
                    "duration_modes": sorted(DURATION_MODES),
                    "duration_limits": {
                        "min_seconds": MIN_DURATION_SECONDS,
                        "max_seconds": MAX_DURATION_SECONDS,
                        "step_seconds": 1,
                    },
                    "aspect_ratios": list(ASPECT_RATIOS),
                    "max_local_estimated_budget_usd": MAX_LOCAL_ESTIMATED_BUDGET_USD,
                    "swift_media_tools": swift_available,
                    "avmediainfo": Path("/usr/bin/avmediainfo").exists(),
                    "presets": [
                        {"id": key, "name": value["name"], "subject": value["subject"]}
                        for key, value in PRESETS.items()
                    ],
                }
            )
            return
        if path == "/api/sessions":
            with SESSIONS_LOCK:
                sessions = [session.public() for session in SESSIONS.values()]
            self._json({"sessions": sessions})
            return
        if path.startswith("/api/session/"):
            session_id = path.rsplit("/", 1)[-1]
            with SESSIONS_LOCK:
                session = SESSIONS.get(session_id)
            if not session:
                self._json({"error": "找不到该任务"}, 404)
                return
            self._json(session.public())
            return
        if path.startswith("/media/"):
            relative = path[len("/media/") :]
            candidate = (SESSION_ROOT / relative).resolve()
            if is_within(candidate, SESSION_ROOT) and candidate.is_file():
                self._serve_file(candidate)
                return
            self.send_error(404)
            return
        if path.startswith("/download/") and path.endswith("/video.mp4"):
            parts = [part for part in path.split("/") if part]
            if len(parts) != 3:
                self.send_error(404)
                return
            session_id = parts[1]
            with SESSIONS_LOCK:
                session = SESSIONS.get(session_id)
            if not session:
                self.send_error(404)
                return
            with session.lock:
                final_filename = session.final_filename
                ready = session.status == "complete" and bool(final_filename)
            candidate = (session.directory / final_filename).resolve() if ready else Path("/")
            if ready and is_within(candidate, session.directory) and candidate.is_file():
                duration_seconds = (
                    session.config.get("duration_seconds")
                    if session.config.get("duration_mode", "fixed") == "fixed"
                    else session.generated_seconds
                )
                duration_label = format_duration_label(int(duration_seconds))
                orientation = ASPECT_RATIOS[
                    session.config.get("aspect_ratio", "9:16")
                ]["label"]
                self._serve_file(
                    candidate,
                    attachment_name=f"FrameCurrent-连续影像-{duration_label}-{orientation}.mp4",
                )
                return
            self.send_error(404)
            return
        self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        authority = self._local_authority()
        if authority is None:
            self._json({"error": "仅接受当前本机服务地址"}, HTTPStatus.MISDIRECTED_REQUEST)
            return
        if not self._origin_is_allowed(authority):
            self._json({"error": "请求来源与本机服务地址不一致"}, HTTPStatus.FORBIDDEN)
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        try:
            if path == "/api/key/check":
                payload = self._read_json()
                api_key = str(payload.get("api_key", "")).strip()
                if not api_key:
                    raise ValueError("请输入 fal API Key")
                result = check_fal_key(api_key)
                api_key = ""
                self._json(result)
                return
            if path == "/api/session/recover":
                payload = self._read_json()
                digest = client_request_hash(normalize_client_request_id(payload.get("client_request_id")))
                with SESSIONS_LOCK:
                    known = SESSIONS.get(CLIENT_REQUEST_SESSIONS.get(digest, ""))
                # Strictly a lookup. Missing IDs can never create a session.
                self._json({"session_id": known.session_id} if known else {"error": "尚未找到对应任务"}, 200 if known else 404)
                return
            if path == "/api/session/start":
                payload = self._read_json()
                normalized_request_id = normalize_client_request_id(
                    payload.get("client_request_id")
                )
                request_digest = client_request_hash(normalized_request_id)

                # Fast replay path: a retry after a lost response must not even
                # re-validate the paid payload, much less start a second worker.
                with SESSIONS_LOCK:
                    existing_session_id = CLIENT_REQUEST_SESSIONS.get(request_digest, "")
                    existing_session = SESSIONS.get(existing_session_id)
                    if existing_session_id and existing_session is None:
                        CLIENT_REQUEST_SESSIONS.pop(request_digest, None)
                if existing_session is not None:
                    normalized_request_id = ""
                    payload = {}
                    self._json(
                        {
                            "ok": True,
                            "idempotent_replay": True,
                            "session": existing_session.public(),
                        }
                    )
                    return

                config = validate_start_payload(payload)
                api_key = config.pop("api_key")
                session_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex
                session = SessionState(
                    session_id=session_id,
                    config=config,
                    api_key=api_key,
                    client_request_hash=request_digest,
                )
                replay_session: Optional[SessionState] = None
                with SESSIONS_LOCK:
                    if SHUTTING_DOWN.is_set():
                        session.api_key = ""
                        self._json({"error": "本机服务正在关闭，未启动新的生成任务"}, 503)
                        return
                    # A concurrent request may have registered the same UUID
                    # while this request was validating its payload. Re-check
                    # and atomically choose exactly one owning session.
                    existing_session_id = CLIENT_REQUEST_SESSIONS.get(request_digest, "")
                    replay_session = SESSIONS.get(existing_session_id)
                    if existing_session_id and replay_session is None:
                        CLIENT_REQUEST_SESSIONS.pop(request_digest, None)
                    if replay_session is not None:
                        api_key = ""
                        session.api_key = ""
                    elif any(
                        existing.status in {"preparing", "generating", "finalizing"}
                        for existing in SESSIONS.values()
                    ):
                        api_key = ""
                        session.api_key = ""
                        raise ValueError("已有一个生成任务正在运行，请先等待或停止它")
                    else:
                        SESSIONS[session_id] = session
                        CLIENT_REQUEST_SESSIONS[request_digest] = session_id
                normalized_request_id = ""
                payload = {}
                if replay_session is not None:
                    self._json(
                        {
                            "ok": True,
                            "idempotent_replay": True,
                            "session": replay_session.public(),
                        }
                    )
                    return

                thread = threading.Thread(target=run_session, args=(session,), daemon=True)
                try:
                    # Persist only the safe public projection and the one-way
                    # idempotency hash before any paid POST can begin.
                    session.persist()
                    thread.start()
                except Exception as error:
                    with session.lock:
                        session.api_key = ""
                        session.config.pop("start_image", None)
                        session.status = "failed"
                        session.message = "任务启动失败"
                        session.error = str(error)[:2000]
                        session.completed_at = utc_now()
                    try:
                        session.persist()
                    except Exception:
                        traceback.print_exc()
                    raise
                self._json(
                    {
                        "ok": True,
                        "idempotent_replay": False,
                        "session": session.public(),
                    },
                    201,
                )
                return
            if path.startswith("/api/session/") and path.endswith("/stop"):
                session_id = path.split("/")[-2]
                with SESSIONS_LOCK:
                    session = SESSIONS.get(session_id)
                if not session:
                    self._json({"error": "找不到该任务"}, 404)
                    return
                stop_generation_session(session)
                self._json({"ok": True, "session": session.public()})
                return
            self._json({"error": "未知接口"}, 404)
        except UnsupportedMediaTypeError as error:
            self._json({"error": str(error)}, HTTPStatus.UNSUPPORTED_MEDIA_TYPE)
        except (ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, 400)
        except Exception as error:
            traceback.print_exc()
            self._json({"error": str(error)}, 500)

    def _serve_static(self, path: str) -> None:
        if path in {"", "/"}:
            path = "/index.html"
        relative = path.lstrip("/")
        candidate = (WEB_ROOT / relative).resolve()
        if not is_within(candidate, WEB_ROOT) or not candidate.is_file():
            self.send_error(404)
            return
        self._serve_file(candidate)

    def _serve_file(self, path: Path, attachment_name: str = "") -> None:
        size = path.stat().st_size
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        range_header = self.headers.get("Range")
        if range_header and range_header.startswith("bytes="):
            try:
                range_spec = range_header[6:]
                if "," in range_spec:
                    raise ValueError
                start_text, separator, end_text = range_spec.partition("-")
                if not separator or (not start_text and not end_text):
                    raise ValueError
                if not start_text:
                    suffix_length = int(end_text)
                    if suffix_length <= 0:
                        raise ValueError
                    start = max(0, size - suffix_length)
                    end = size - 1
                else:
                    start = int(start_text)
                    end = int(end_text) if end_text else size - 1
                    end = min(end, size - 1)
                if start < 0 or start > end or start >= size:
                    raise ValueError
            except ValueError:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self._security_headers()
                self.end_headers()
                return
            length = end - start + 1
            self.send_response(206)
            self.send_header("Content-Type", mime)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Content-Length", str(length))
            if attachment_name:
                encoded_name = urllib.parse.quote(attachment_name)
                self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
            self.send_header("Cache-Control", "no-cache" if mime.startswith("video/") else "public, max-age=60")
            self._security_headers()
            self.end_headers()
            if self.command == "HEAD":
                return
            with path.open("rb") as source:
                source.seek(start)
                remaining = length
                while remaining:
                    chunk = source.read(min(1024 * 1024, remaining))
                    if not chunk:
                        break
                    try:
                        self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        # Browsers routinely cancel speculative range reads after
                        # obtaining enough data. This is not a playback failure.
                        return
                    remaining -= len(chunk)
            return
        self.send_response(200)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(size))
        if attachment_name:
            encoded_name = urllib.parse.quote(attachment_name)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{encoded_name}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store" if mime.startswith("text/html") else "public, max-age=60")
        if mime.startswith("text/html"):
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; img-src 'self' data:; media-src 'self'; "
                "style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; "
                "base-uri 'none'; form-action 'self'",
            )
        self._security_headers()
        self.end_headers()
        if self.command == "HEAD":
            return
        with path.open("rb") as source:
            try:
                shutil.copyfileobj(source, self.wfile)
            except (BrokenPipeError, ConnectionResetError):
                return


def restore_manifests() -> None:
    SESSION_ROOT.mkdir(parents=True, exist_ok=True)
    for manifest in SESSION_ROOT.glob("*/manifest.json"):
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            config = payload["config"]
            # Never surface historical local-demo evidence in the product UI.
            if config.get("mode") == "mock" or any(
                str(clip.get("request_id", "")).startswith("mock-")
                for clip in payload.get("clips", [])
            ):
                continue
            config.setdefault("duration_mode", "fixed")
            if config["duration_mode"] not in DURATION_MODES:
                raise ValueError("保存任务的时长模式无效")
            config.setdefault("clip_schedule", [clip.get("duration", 15) for clip in payload.get("clips", [])])
            if config["duration_mode"] == "fixed":
                config.setdefault("total_clips", len(config.get("clip_schedule", [])))
            else:
                config.setdefault("duration_seconds", None)
                config.setdefault("duration_label", "不限时长")
                config.setdefault("total_clips", None)
                config.setdefault("estimated_cost_usd", None)
            config.setdefault("max_budget_usd", config.get("estimated_cost_usd", 0))
            config.setdefault("aspect_ratio", "9:16")
            if config["aspect_ratio"] not in ASPECT_RATIOS:
                raise ValueError("保存任务的画面比例无效")
            config["preset"] = LEGACY_PRESET_ALIASES.get(
                config.get("preset", "hand_drawn_fantasy"),
                config.get("preset", "hand_drawn_fantasy"),
            )
            if config["preset"] not in PRESETS:
                raise ValueError("保存任务的画面方向无效")
            saved_request_hash = str(payload.get("_client_request_hash", ""))
            if saved_request_hash and not re.fullmatch(r"[0-9a-f]{64}", saved_request_hash):
                # Corrupt optional idempotency metadata must not hide an
                # otherwise valid historical result.
                saved_request_hash = ""
            session = SessionState(
                session_id=payload["session_id"],
                config=config,
                api_key="",
                client_request_hash=saved_request_hash,
                created_at=payload.get("created_at", ""),
                status=payload.get("status", "complete"),
                message=payload.get("message", ""),
                clips=payload.get("clips", []),
                generated_seconds=payload.get("generated_seconds", 0),
                submitted_seconds=payload.get("submitted_seconds", payload.get("generated_seconds", 0)),
                spent_estimate_usd=payload.get("spent_estimate_usd", 0),
                active_queue_state=payload.get("active_queue_state", ""),
                error=payload.get("error", ""),
                completion_reason=payload.get(
                    "completion_reason",
                    "target_reached" if payload.get("status") == "complete" else "",
                ),
                completed_at=payload.get("completed_at", ""),
                final_filename=payload.get("final_filename", ""),
                final_validation=payload.get("final_validation", {}),
            )
            if session.status in {"preparing", "generating", "finalizing"}:
                session.status = "interrupted"
                session.message = "应用上次退出时任务仍在运行；为防止重复扣费，没有自动恢复"
            elif session.status == "complete" and session.final_filename:
                final_path = (session.directory / session.final_filename).resolve()
                try:
                    if not is_within(final_path, session.directory) or not final_path.is_file():
                        raise RuntimeError("完整视频文件不存在或路径无效")
                    expected_duration = (
                        session.config["duration_seconds"]
                        if session.config.get("duration_mode", "fixed") == "fixed"
                        else session.generated_seconds
                    )
                    restored_validation = validate_media(
                        final_path,
                        expected_duration=expected_duration,
                        require_audio=True,
                        aspect_ratio=session.config["aspect_ratio"],
                    )
                    restored_validation["size_bytes"] = final_path.stat().st_size
                    restored_validation["sha256"] = file_sha256(final_path)
                    expected_hash = session.final_validation.get("sha256")
                    if expected_hash and expected_hash != restored_validation["sha256"]:
                        raise RuntimeError("成片校验值与保存记录不一致")
                    session.final_validation = restored_validation
                except Exception as error:
                    session.status = "invalid"
                    session.message = "已保存的完整视频未通过重新校验"
                    session.error = str(error)[:1000]
                    session.final_filename = ""
            SESSIONS[session.session_id] = session
            if saved_request_hash:
                CLIENT_REQUEST_SESSIONS.setdefault(
                    saved_request_hash,
                    session.session_id,
                )
        except Exception:
            traceback.print_exc()


def create_server(host: str, port: int) -> ThreadingHTTPServer:
    if host != "127.0.0.1":
        raise ValueError("连续影像只允许监听 127.0.0.1")
    return ThreadingHTTPServer((host, port), AppHandler)


def shutdown_running_sessions(timeout: float = 8.0) -> None:
    """Stop new clips immediately; cancellation and finalization are best effort."""
    with SESSIONS_LOCK:
        active = [session for session in SESSIONS.values()
                  if session.status in {"preparing", "generating", "finalizing"}]
    def stop_safely(session: SessionState) -> None:
        try:
            # This function sets the event and claims cancellation credentials
            # atomically. Setting the event outside it would race worker cleanup.
            stop_generation_session(session)
        except Exception:
            print("停止请求未能确认；已提交的一幕仍可能计费。", flush=True)
    workers = [threading.Thread(target=stop_safely, args=(session,), daemon=True) for session in active]
    for worker in workers:
        worker.start()
    deadline = time.monotonic() + timeout
    for worker in workers:
        worker.join(timeout=max(0, deadline - time.monotonic()))
    while active and time.monotonic() < deadline:
        if all(session.status not in {"preparing", "generating", "finalizing"} for session in active):
            return
        time.sleep(min(0.1, max(0, deadline - time.monotonic())))
    if active:
        print("服务即将关闭；请勿假定远端任务已取消。重启不会自动继续付费生成。", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="连续影像 FrameCurrent：H3 Max 固定或不限时长视频生成器")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=4173)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args()
    SHUTTING_DOWN.clear()

    for directory in (RUNTIME_ROOT, SESSION_ROOT, BIN_ROOT):
        directory.mkdir(parents=True, exist_ok=True)
    try:
        server = create_server(args.host, args.port)
    except OSError as error:
        if error.errno == 48 or error.errno == 98:
            parser.exit(1, f"端口 {args.port} 已被占用。请双击 run.command 重新连接现有服务；不要重复启动。\n")
        parser.exit(1, "本地服务无法启动，请运行 doctor.command 检查环境与文件夹权限。\n")
    try:
        print("正在检查本机历史作品；作品较多时请稍候，不会自动恢复付费生成。", flush=True)
        restore_manifests()
    except Exception:
        server.server_close()
        raise
    url = f"http://{args.host}:{server.server_address[1]}"
    print(f"连续影像 · FrameCurrent 已启动：{url}", flush=True)
    print("API Key 只保存在当前进程内存，不会写入磁盘。", flush=True)

    if not args.no_open:
        def open_browser() -> None:
            time.sleep(0.5)
            subprocess.run(["/usr/bin/open", url], check=False)

        threading.Thread(target=open_browser, daemon=True).start()

    stopping = threading.Event()
    def stop_server(_signum=None, _frame=None) -> None:
        if stopping.is_set():
            return
        stopping.set()
        with SESSIONS_LOCK:
            SHUTTING_DOWN.set()
        def finish_shutdown() -> None:
            # Stop accepting new HTTP requests before asking active workers to finish.
            server.shutdown()
        threading.Thread(target=finish_shutdown, daemon=True).start()

    signal.signal(signal.SIGINT, stop_server)
    signal.signal(signal.SIGTERM, stop_server)
    try:
        server.serve_forever(poll_interval=0.3)
    finally:
        shutdown_running_sessions()
        server.server_close()


if __name__ == "__main__":
    main()
