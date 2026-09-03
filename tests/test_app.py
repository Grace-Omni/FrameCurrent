"""Offline acceptance tests for the H3 Max continuous-video server.

No test in this module submits a fal generation job. Tests that start a
session replace ``run_session`` before making the HTTP request, and the
key-check endpoint replaces ``request_json`` with a local mock.
"""

from __future__ import annotations

import importlib.util
import base64
import http.client
import json
import math
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("h3_app", ROOT / "app.py")
app = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = app
SPEC.loader.exec_module(app)


# This has the documented fal credential *shape*, but it is intentionally not
# a real credential and cannot authorize any remote request.
FAKE_FAL_KEY = "offline_test_id:" + "not_a_real_secret_" * 2
# fal's public key-creation contract promises ``key_id:key_secret`` but does
# not promise UUID IDs, hexadecimal secrets, or fixed component lengths. This
# mirrors the opaque example in the official Platform API documentation.
DOCS_EXAMPLE_FAL_KEY = "docs_example_id:docs_example_secret_not_real"
SECRET_START_IMAGE = "data:image/png;base64,private-reference-image"


class RecordingStopEvent:
    """Threading-event test double that records backoff without sleeping."""

    def __init__(self):
        self.stopped = False
        self.waits = []

    def is_set(self):
        return self.stopped

    def set(self):
        self.stopped = True

    def wait(self, seconds):
        self.waits.append(seconds)
        return self.stopped


def queue_submission(request_id="offline-request"):
    root = "https://queue.fal.run/minimax/h3-max/text-to-video/requests"
    return {
        "request_id": request_id,
        "status_url": f"{root}/{request_id}/status",
        "response_url": f"{root}/{request_id}/response",
        "cancel_url": f"{root}/{request_id}/cancel",
    }


def valid_payload(**overrides):
    payload = {
        "client_request_id": str(uuid.uuid4()),
        "duration_seconds": 300,
        "clip_duration": 15,
        "resolution": "480P",
        "aspect_ratio": "9:16",
        "preset": "hand_drawn_fantasy",
        "api_key": FAKE_FAL_KEY,
        "paid_confirmed": True,
        "max_budget_usd": 15,
    }
    payload.update(overrides)
    return payload


def validated_config(**overrides):
    config = app.validate_start_payload(valid_payload(**overrides))
    key = config.pop("api_key")
    return config, key


def clip_record(number: int, duration: int = 15):
    return {
        "index": number - 1,
        "number": number,
        "filename": f"clip-{number:03d}.mp4",
        "url": f"/media/unit/clip-{number:03d}.mp4",
        "duration": duration,
        "generation_seconds": 1.25,
        "generation_time_seconds": 1.2,
        "generation_time_source": "gpu_core",
        "first_frame_url": f"/media/unit/clip-{number:03d}-first.jpg",
        "last_frame_url": f"/media/unit/clip-{number:03d}-last.jpg",
        "continuity_check": "passed",
        "media": {
            "duration": float(duration),
            "width": 480,
            "height": 854,
            "has_audio": True,
            "validation": "PASS",
        },
        "ready_at": "2026-09-01T00:00:00+00:00",
    }


def all_mapping_keys(value):
    """Collect every key recursively from a JSON-compatible object."""
    keys = set()
    if isinstance(value, dict):
        for key, child in value.items():
            keys.add(key)
            keys.update(all_mapping_keys(child))
    elif isinstance(value, list):
        for child in value:
            keys.update(all_mapping_keys(child))
    return keys


class ConfigBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.internal_qa = mock.patch.object(app, "INTERNAL_QA", False)
        self.internal_qa.start()

    def tearDown(self):
        self.internal_qa.stop()

    def test_duration_is_a_free_integer_range_from_ten_seconds_to_thirty_minutes(self):
        self.assertEqual(app.MIN_DURATION_SECONDS, 10)
        self.assertEqual(app.MAX_DURATION_SECONDS, 1800)

    def test_visual_presets_are_distinct_genres_with_their_own_story_beats(self):
        expected = {
            "hand_drawn_fantasy",
            "cinematic_scifi",
            "studio_variety",
            "travel_aerial",
            "costume_drama",
            "custom_channel",
        }
        self.assertEqual(set(app.PRESETS), expected)
        self.assertEqual(len({preset["name"] for preset in app.PRESETS.values()}), 6)
        self.assertEqual(len({preset["base"] for preset in app.PRESETS.values()}), 6)

        for preset_id, preset in app.PRESETS.items():
            with self.subTest(preset=preset_id):
                config = app.validate_start_payload(valid_payload(preset=preset_id))
                self.assertEqual(config["preset"], preset_id)
                self.assertGreaterEqual(len(preset["beats"]), 6)
                prompt = app.build_prompt(config, 0, False)
                self.assertIn(preset["base"], prompt)
                self.assertIn(preset["beats"][0], prompt)

        for legacy, replacement in app.LEGACY_PRESET_ALIASES.items():
            with self.subTest(legacy=legacy):
                config = app.validate_start_payload(valid_payload(preset=legacy))
                self.assertEqual(config["preset"], replacement)

    def test_custom_channel_fields_are_scoped_truncated_and_used_in_the_prompt(self):
        config = app.validate_start_payload(
            valid_payload(
                preset="custom_channel",
                custom_channel_name="频" * 60,
                custom_channel_style="赛博国风、固定长焦、强烈红黑对比" * 40,
            )
        )
        self.assertEqual(config["preset"], "custom_channel")
        self.assertEqual(len(config["custom_channel_name"]), 40)
        self.assertEqual(len(config["custom_channel_style"]), 300)
        self.assertEqual(config["preset_name"], config["custom_channel_name"])
        prompt = app.build_prompt(config, 0, False)
        self.assertIn("CUSTOM CHANNEL STYLE LOCK", prompt)
        self.assertIn(config["custom_channel_style"], prompt)

        normal = app.validate_start_payload(
            valid_payload(
                preset="costume_drama",
                custom_channel_name="不应写入",
                custom_channel_style="不应写入",
            )
        )
        self.assertNotIn("custom_channel_name", normal)
        self.assertNotIn("custom_channel_style", normal)
        with self.assertRaisesRegex(ValueError, "未知"):
            app.validate_start_payload(
                valid_payload(preset="伪造频道", custom_channel_name="hand_drawn_fantasy")
            )

    def test_unlimited_mode_requires_an_explicit_confirmed_budget_for_one_full_clip(self):
        unlimited = valid_payload(
            duration_mode="unlimited",
            duration_seconds="stale-hidden-value",
            clip_duration=10,
            max_budget_usd=0.5,
        )
        config = app.validate_start_payload(unlimited)
        self.assertEqual(config["duration_mode"], "unlimited")
        self.assertIsNone(config["duration_seconds"])
        self.assertEqual(config["duration_label"], "不限时长")
        self.assertEqual(config["clip_schedule"], [])
        self.assertIsNone(config["total_clips"])
        self.assertIsNone(config["estimated_cost_usd"])

        missing_budget = dict(unlimited)
        missing_budget.pop("max_budget_usd")
        with self.assertRaisesRegex(ValueError, "显式设置"):
            app.validate_start_payload(missing_budget)
        for too_small in (0.49, 0.499):
            with self.subTest(max_budget_usd=too_small):
                with self.assertRaisesRegex(ValueError, "至少需要覆盖一幕"):
                    app.validate_start_payload(dict(unlimited, max_budget_usd=too_small))
        with self.assertRaisesRegex(ValueError, "确认"):
            app.validate_start_payload(dict(unlimited, paid_confirmed=False))
        with self.assertRaisesRegex(ValueError, "时长模式"):
            app.validate_start_payload(valid_payload(duration_mode="forever"))

    def test_budget_guard_uses_submitted_seconds_and_exact_cap_boundaries(self):
        config = app.validate_start_payload(
            valid_payload(
                duration_mode="unlimited",
                clip_duration=10,
                max_budget_usd=1.0,
            )
        )
        self.assertTrue(app.budget_allows_segment(config, 0, 10))
        self.assertTrue(app.budget_allows_segment(config, 10, 10))
        self.assertFalse(app.budget_allows_segment(config, 20, 10))

    def test_any_integer_duration_inside_the_range_validates(self):
        for duration in (10, 11, 59, 60, 61, 299, 300, 901, 1799, 1800):
            with self.subTest(duration=duration):
                budget = app.estimate_cost_usd(duration, "480P")
                config = app.validate_start_payload(
                    valid_payload(duration_seconds=duration, max_budget_usd=budget)
                )
                self.assertEqual(config["duration_seconds"], duration)
                self.assertEqual(sum(config["clip_schedule"]), duration)
                self.assertTrue(all(5 <= value <= 15 for value in config["clip_schedule"]))

        for invalid in (9, 1801, -1, 10.5, "10.5", True, "nan"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "时长"):
                    app.validate_start_payload(valid_payload(duration_seconds=invalid))

    def test_mode_mock_and_caller_supplied_schedules_have_no_effect(self):
        baseline = app.validate_start_payload(valid_payload())
        attempted_mock = app.validate_start_payload(
            valid_payload(
                mode="mock",
                mock=True,
                mock_url="https://example.invalid/free.mp4",
                qa_schedule=[5],
                clip_schedule=[5],
            )
        )
        self.assertEqual(attempted_mock, baseline)
        self.assertNotIn("mode", attempted_mock)
        self.assertEqual(attempted_mock["clip_schedule"], [15] * 20)

    def test_every_legal_clip_preference_produces_an_exact_plan(self):
        for duration in range(app.MIN_DURATION_SECONDS, app.MAX_DURATION_SECONDS + 1):
            for preferred in sorted(app.CLIP_DURATIONS):
                with self.subTest(duration=duration, preferred=preferred):
                    schedule = app.build_clip_schedule(duration, preferred)
                    self.assertEqual(sum(schedule), duration)
                    self.assertTrue(all(5 <= seconds <= 15 for seconds in schedule))
                    self.assertLessEqual(max(schedule) - min(schedule), 1)

        self.assertEqual(app.build_clip_schedule(300, 15), [15] * 20)
        self.assertEqual(app.build_clip_schedule(300, 12), [12] * 25)
        self.assertEqual(app.build_clip_schedule(300, 10), [10] * 30)
        self.assertEqual(app.build_clip_schedule(300, 5), [5] * 60)
        self.assertEqual(app.build_clip_schedule(300, 14), [15] * 6 + [14] * 15)
        self.assertEqual(app.build_clip_schedule(11, 5), [6, 5])

    def test_start_requires_a_fal_credential_pair_and_literal_paid_confirmation(self):
        missing_key = valid_payload()
        missing_key.pop("api_key")
        with self.assertRaisesRegex(ValueError, "API Key"):
            app.validate_start_payload(missing_key)

        invalid_keys = (
            "mock-key",
            ":" + "a" * 60,
            "a" * 60 + ":",
            "key id:" + "a" * 60,
            "key-id:" + "a" * 30 + "\x00" + "a" * 30,
        )
        for invalid_key in invalid_keys:
            with self.subTest(key=invalid_key[:18]):
                with self.assertRaisesRegex(ValueError, "格式无效"):
                    app.validate_start_payload(valid_payload(api_key=invalid_key))

        for unconfirmed in (False, None, 0, 1, "false", "true"):
            with self.subTest(paid_confirmed=repr(unconfirmed)):
                with self.assertRaisesRegex(ValueError, "确认"):
                    app.validate_start_payload(valid_payload(paid_confirmed=unconfirmed))

        accepted = app.validate_start_payload(valid_payload(paid_confirmed=True))
        self.assertEqual(accepted["api_key"], FAKE_FAL_KEY)
        self.assertTrue(accepted["paid_confirmed"])

        documented_shape = app.validate_start_payload(
            valid_payload(api_key=DOCS_EXAMPLE_FAL_KEY, paid_confirmed=True)
        )
        self.assertEqual(documented_shape["api_key"], DOCS_EXAMPLE_FAL_KEY)

    def test_budget_guard_uses_the_full_five_minute_standard_rate(self):
        self.assertEqual(app.estimate_cost_usd(300, "480P"), 15.0)
        self.assertEqual(app.estimate_cost_usd(300, "768P"), 24.0)

        for resolution, required in (("480P", 15.0), ("768P", 24.0)):
            with self.subTest(resolution=resolution):
                with self.assertRaisesRegex(ValueError, "费用上限不足"):
                    app.validate_start_payload(
                        valid_payload(
                            resolution=resolution,
                            max_budget_usd=required - 0.01,
                        )
                    )
                accepted = app.validate_start_payload(
                    valid_payload(resolution=resolution, max_budget_usd=required)
                )
                self.assertEqual(accepted["estimated_cost_usd"], required)
                self.assertEqual(accepted["max_budget_usd"], required)

        for invalid_budget in (-1, "nan", "inf", "-inf"):
            with self.subTest(budget=invalid_budget):
                with self.assertRaisesRegex(ValueError, "有效的非负数字"):
                    app.validate_start_payload(valid_payload(max_budget_usd=invalid_budget))

    def test_local_estimated_budget_has_a_server_side_absolute_limit(self):
        accepted = app.validate_start_payload(
            valid_payload(
                duration_seconds=1800,
                resolution="768P",
                max_budget_usd=144,
            )
        )
        self.assertEqual(accepted["max_budget_usd"], 144)

        with self.assertRaisesRegex(ValueError, r"不能超过 \$150\.00"):
            app.validate_start_payload(
                valid_payload(
                    duration_mode="unlimited",
                    max_budget_usd=150.01,
                )
            )

    def test_continuation_prompt_contains_identity_and_camera_locks(self):
        config, _key = validated_config(
            scene_setting="a connected floating-island route",
            story_action="pass one windmill, then approach a whale",
            camera_direction="steady rear follow",
            avoid_content="no collisions",
        )
        prompt = app.build_prompt(config, 1, True)
        self.assertIn("exact first frame", prompt)
        self.assertIn("IDENTITY LOCK", prompt)
        self.assertIn("one continuous take", prompt)
        self.assertIn("portrait 9:16", prompt)
        self.assertIn("00:00-00:04", prompt)
        self.assertIn("never pass through solid geometry", prompt)
        self.assertIn("Do not restart or replay", prompt)
        self.assertIn("WORLD LOCK", prompt)
        self.assertIn("CAMERA LOCK", prompt)
        self.assertNotIn("pass one windmill, then approach a whale", prompt)

        first_prompt = app.build_prompt(config, 0, False)
        self.assertIn("pass one windmill, then approach a whale", first_prompt)
        self.assertIn("Do not rush to complete the whole journey", first_prompt)

        reference_first_prompt = app.build_prompt(config, 0, True)
        self.assertIn("exact first frame of this new shot", reference_first_prompt)
        self.assertIn("pass one windmill, then approach a whale", reference_first_prompt)
        self.assertNotIn("Do not restart or replay", reference_first_prompt)

        landscape, _key = validated_config(aspect_ratio="16:9")
        landscape_prompt = app.build_prompt(landscape, 0, False)
        self.assertIn("landscape 16:9", landscape_prompt)
        self.assertNotIn("portrait 9:16", landscape_prompt)

    def test_aspect_ratio_is_validated_and_reference_image_must_match(self):
        portrait = app.validate_start_payload(valid_payload(aspect_ratio="9:16"))
        landscape = app.validate_start_payload(valid_payload(aspect_ratio="16:9"))
        self.assertEqual(portrait["aspect_ratio"], "9:16")
        self.assertEqual(landscape["aspect_ratio"], "16:9")
        with self.assertRaisesRegex(ValueError, "画面比例"):
            app.validate_start_payload(valid_payload(aspect_ratio="1:1"))

        image = "data:image/png;base64," + base64.b64encode(b"x" * 2048).decode("ascii")
        landscape_sips = mock.Mock(
            returncode=0,
            stdout="pixelWidth: 1344\npixelHeight: 768\n",
            stderr="",
        )
        with mock.patch.object(app.subprocess, "run", return_value=landscape_sips):
            config = app.validate_start_payload(
                valid_payload(aspect_ratio="16:9", start_image=image)
            )
            self.assertEqual(config["aspect_ratio"], "16:9")
            with self.assertRaisesRegex(ValueError, "9:16"):
                app.validate_start_payload(
                    valid_payload(aspect_ratio="9:16", start_image=image)
                )


class MediaDurationNormalizationTests(unittest.TestCase):
    @staticmethod
    def receipt(
        duration: float,
        *,
        audio: bool = True,
        dimensions: tuple[int, int] = (768, 1344),
    ) -> str:
        width, height = dimensions
        tracks = [
            f"Duration: {duration:.3f} seconds ({int(duration * 1000)}/1000)",
            "Track count: 2" if audio else "Track count: 1",
            (
                f"Track 1: Video, Enabled, Format: H.264, Dimensions: {width} x {height}, "
                f"24.000 fps, 4000000 bytes, {duration:.3f} seconds"
            ),
        ]
        if audio:
            tracks.append(
                "Track 2: Sound, Enabled, Format: MPEG-4 AAC, 130000 bytes, "
                f"{duration + 0.017:.3f} seconds"
            )
        return "\n".join(tracks)

    def test_media_aspect_ratio_accepts_the_selected_orientation_only(self):
        landscape_receipt = self.receipt(10.0, dimensions=(1344, 768))
        with mock.patch.object(app, "media_info", return_value=landscape_receipt):
            result = app.validate_media(
                Path("landscape.mp4"),
                expected_duration=10,
                require_audio=True,
                aspect_ratio="16:9",
            )
        self.assertEqual(result["aspect_ratio"], "16:9")
        self.assertEqual((result["width"], result["height"]), (1344, 768))

        with mock.patch.object(app, "media_info", return_value=landscape_receipt):
            with self.assertRaisesRegex(RuntimeError, "9:16"):
                app.validate_media(
                    Path("wrong-orientation.mp4"),
                    expected_duration=10,
                    require_audio=True,
                    aspect_ratio="9:16",
                )

    def test_real_h3_four_extra_frames_are_accepted_for_source_normalization(self):
        with mock.patch.object(app, "media_info", return_value=self.receipt(5.167)):
            result = app.validate_media(
                Path("unused-real-h3.mp4"),
                expected_duration=5,
                allow_generation_rounding=True,
                require_audio=True,
            )
        self.assertEqual(result["duration"], 5.167)
        self.assertEqual(result["target_duration"], 5)
        self.assertEqual(result["normalization_seconds"], 0.167)
        self.assertEqual(result["frame_rate"], 24.0)
        self.assertTrue(result["has_audio"])
        self.assertEqual(result["audio_codec"], "AAC")

    def test_source_rounding_does_not_weaken_final_duration_validation(self):
        with mock.patch.object(app, "media_info", return_value=self.receipt(5.167)):
            with self.assertRaisesRegex(RuntimeError, "实际时长"):
                app.validate_media(
                    Path("not-a-final.mp4"),
                    expected_duration=5,
                    require_audio=True,
                )

        with mock.patch.object(app, "media_info", return_value=self.receipt(300.0)):
            final = app.validate_media(
                Path("exact-final.mp4"),
                expected_duration=300,
                require_audio=True,
            )
        self.assertEqual(final["duration"], 300.0)
        self.assertEqual(final["duration_delta"], 0.0)

        for drifted_duration in (299.987, 300.013):
            with self.subTest(final_duration=drifted_duration):
                with mock.patch.object(
                    app,
                    "media_info",
                    return_value=self.receipt(drifted_duration),
                ):
                    with self.assertRaisesRegex(RuntimeError, "实际时长"):
                        app.validate_media(
                            Path("drifted-final.mp4"),
                            expected_duration=300,
                            require_audio=True,
                        )

    def test_excessive_overrun_and_missing_audio_are_rejected(self):
        with mock.patch.object(app, "media_info", return_value=self.receipt(5.250)):
            with self.assertRaisesRegex(RuntimeError, "实际时长"):
                app.validate_media(
                    Path("too-long.mp4"),
                    expected_duration=5,
                    allow_generation_rounding=True,
                    require_audio=True,
                )

        with mock.patch.object(app, "media_info", return_value=self.receipt(5.167, audio=False)):
            with self.assertRaisesRegex(RuntimeError, "缺少原生音轨"):
                app.validate_media(
                    Path("silent.mp4"),
                    expected_duration=5,
                    allow_generation_rounding=True,
                    require_audio=True,
                )

    def test_full_media_report_accepts_multiple_aac_format_descriptions(self):
        receipt = """Asset: merged.mp4
Duration: 10.000 seconds (6000/600)
Track count: 2
Track 1: Sound 'soun'
    Enabled: Yes
    Format Description 1:
        Format: MPEG-4 AAC 'aac '
        Sample rate: 32000.0
    Format Description 2:
        Format: MPEG-4 AAC 'aac '
        Sample rate: 32000.0
    Duration: 10.000 seconds
Track 2: Video 'vide'
    Enabled: Yes
    Format Description 1:
        Format: H.264 'avc1'
        Dimensions: 768 x 1344
    Duration: 10.000 seconds
    Nominal frame rate: 24.000 fps

Movie analyzed with 0 error.
"""
        completed = mock.Mock(returncode=0, stdout=receipt, stderr="")
        with mock.patch.object(app.subprocess, "run", return_value=completed) as run:
            result = app.validate_media(
                Path("merged-with-two-aac-descriptions.mp4"),
                expected_duration=10,
                require_audio=True,
            )

        command = run.call_args.args[0]
        self.assertEqual(
            command,
            ["/usr/bin/avmediainfo", "merged-with-two-aac-descriptions.mp4"],
        )
        self.assertNotIn("--brief", command)
        self.assertEqual(result["validation"], "PASS")
        self.assertEqual(result["duration"], 10.0)
        self.assertTrue(result["has_audio"])
        self.assertEqual(result["audio_codec"], "AAC")

    def test_full_media_report_still_rejects_non_aac_audio(self):
        non_aac_receipt = self.receipt(10.0).replace(
            "Format: MPEG-4 AAC",
            "Format: Linear PCM",
        )
        with mock.patch.object(app, "media_info", return_value=non_aac_receipt):
            with self.assertRaisesRegex(RuntimeError, "音频编码不是 AAC"):
                app.validate_media(
                    Path("merged-with-pcm-audio.mp4"),
                    expected_duration=10,
                    require_audio=True,
                )

    def test_mixed_aac_and_non_aac_descriptions_are_rejected(self):
        mixed_receipt = """Asset: mixed-audio.mp4
Duration: 10.000 seconds (6000/600)
Track count: 2
Track 1: Sound 'soun'
    Format Description 1:
        Format: MPEG-4 AAC 'aac '
    Format Description 2:
        Format: Linear PCM 'lpcm'
    Duration: 10.000 seconds
Track 2: Video 'vide'
    Format Description 1:
        Format: H.264 'avc1'
        Dimensions: 768 x 1344
    Duration: 10.000 seconds
    Nominal frame rate: 24.000 fps
"""
        with mock.patch.object(app, "media_info", return_value=mixed_receipt):
            with self.assertRaisesRegex(RuntimeError, "音频编码不是 AAC"):
                app.validate_media(
                    Path("merged-with-mixed-audio.mp4"),
                    expected_duration=10,
                    require_audio=True,
                )

    def test_full_media_report_is_size_bounded(self):
        completed = mock.Mock(
            returncode=0,
            stdout=self.receipt(10.0) + ("x" * app.MAX_MEDIA_INFO_CHARS),
            stderr="",
        )
        with mock.patch.object(app.subprocess, "run", return_value=completed):
            receipt = app.media_info(Path("oversized-report.mp4"))

        self.assertEqual(len(receipt), app.MAX_MEDIA_INFO_CHARS)


class KeyCheckWordingTests(unittest.TestCase):
    def test_pricing_auth_does_not_claim_that_generation_is_proven(self):
        for billing_error in (
            "fal API HTTP 403: admin scope required",
            "fal API 网络错误: temporary outage",
        ):
            with self.subTest(billing_error=billing_error):
                responses = [
                    {"prices": [{"endpoint_id": "minimax/h3-max/text-to-video"}]},
                    RuntimeError(billing_error),
                ]
                with mock.patch.object(app, "request_json", side_effect=responses):
                    result = app.check_fal_key(FAKE_FAL_KEY)

                wording = f"{result['message']} {result['balance_note']}"
                self.assertTrue(result["ok"])
                self.assertTrue(result["pricing_verified"])
                self.assertFalse(result.get("generation_verified", False))
                self.assertIn("价格", wording)
                self.assertNotIn("可以生成", wording)
                self.assertNotIn("服务连接成功", wording)
                self.assertNotIn("密钥有效", wording)


class GenerationTimingTests(unittest.TestCase):
    def test_top_level_gpu_core_timing_is_truncated_to_one_decimal(self):
        timing = app.build_generation_timing(
            {"metrics": {"inference_time": 8.76}},
            {"timings": {"inference": 4.29}},
            12.98,
        )

        self.assertEqual(timing, {"seconds": 4.2, "source": "gpu_core"})

    def test_nested_gpu_core_timing_is_supported(self):
        timing = app.build_generation_timing(
            {},
            {"data": {"timings": {"inference": 1.99}}},
            12.98,
        )

        self.assertEqual(timing, {"seconds": 1.9, "source": "gpu_core"})

    def test_fal_processing_supports_top_level_and_nested_metrics(self):
        cases = (
            ({"metrics": {"inference_time": 6.78}}, 6.7),
            ({"data": {"metrics": {"inference_time": 7.89}}}, 7.8),
        )
        for status, expected in cases:
            with self.subTest(status=status):
                timing = app.build_generation_timing(status, {}, 12.98)
                self.assertEqual(
                    timing,
                    {"seconds": expected, "source": "fal_processing"},
                )

    def test_source_priority_is_semantic_not_the_shortest_number(self):
        timing = app.build_generation_timing(
            {"metrics": {"inference_time": 2.91}},
            {"timings": {"inference": 3.91}},
            1.91,
        )

        self.assertEqual(timing, {"seconds": 3.9, "source": "gpu_core"})

    def test_invalid_provider_values_fall_back_without_numeric_coercion(self):
        invalid_values = (None, True, False, "1.23", 0, -1, math.nan, math.inf)
        for invalid in invalid_values:
            with self.subTest(source="gpu_core", invalid=invalid):
                timing = app.build_generation_timing(
                    {"metrics": {"inference_time": 5.59}},
                    {"timings": {"inference": invalid}},
                    9.99,
                )
                self.assertEqual(
                    timing,
                    {"seconds": 5.5, "source": "fal_processing"},
                )

            with self.subTest(source="fal_processing", invalid=invalid):
                timing = app.build_generation_timing(
                    {"metrics": {"inference_time": invalid}},
                    {},
                    9.99,
                )
                self.assertEqual(
                    timing,
                    {"seconds": 9.9, "source": "result_ready"},
                )

    def test_missing_provider_timings_use_result_ready_fallback(self):
        timing = app.build_generation_timing({}, {}, 2.99)

        self.assertEqual(timing, {"seconds": 2.9, "source": "result_ready"})


class FalQueueReliabilityTests(unittest.TestCase):
    def test_pre_stopped_generation_never_submits_the_paid_post(self):
        event = RecordingStopEvent()
        event.set()
        with mock.patch.object(app, "request_json") as request:
            with self.assertRaisesRegex(RuntimeError, "用户停止"):
                app.fal_generate(
                    "minimax/h3-max/text-to-video",
                    {"prompt": "offline test"},
                    FAKE_FAL_KEY,
                    event,
                    lambda *_args: None,
                )
        request.assert_not_called()

    def test_submission_disables_io_storage_and_is_never_retried(self):
        calls = []

        def fail_submission(*args, **kwargs):
            calls.append((args, kwargs))
            raise app.FalAPIError("offline connection loss", network_error=True)

        with mock.patch.object(app, "request_json", side_effect=fail_submission):
            with self.assertRaisesRegex(app.FalAPIError, "connection loss"):
                app.fal_generate(
                    "minimax/h3-max/text-to-video",
                    {"prompt": "offline test"},
                    FAKE_FAL_KEY,
                    RecordingStopEvent(),
                    lambda *_args: None,
                )

        self.assertEqual(len(calls), 1)
        args, kwargs = calls[0]
        self.assertEqual(args[1], "POST")
        self.assertEqual(kwargs["extra_headers"], {"X-Fal-Store-IO": "0"})

    def test_completed_status_and_result_errors_are_not_treated_as_success(self):
        submitted = queue_submission()
        with self.subTest(phase="status"):
            responses = [
                submitted,
                {
                    "status": "COMPLETED",
                    "error": "request rejected",
                    "error_type": "content_policy",
                },
            ]
            with mock.patch.object(app, "request_json", side_effect=responses) as request:
                with self.assertRaisesRegex(RuntimeError, "content_policy"):
                    app.fal_generate(
                        "minimax/h3-max/text-to-video",
                        {"prompt": "offline test"},
                        FAKE_FAL_KEY,
                        RecordingStopEvent(),
                        lambda *_args: None,
                    )
            self.assertEqual(request.call_count, 2)

        with self.subTest(phase="result"):
            responses = [
                submitted,
                {"status": "COMPLETED"},
                {
                    "data": {
                        "error": {"message": "render failed"},
                        "error_type": "runner_error",
                    }
                },
            ]
            with mock.patch.object(app, "request_json", side_effect=responses) as request:
                with self.assertRaisesRegex(RuntimeError, "runner_error"):
                    app.fal_generate(
                        "minimax/h3-max/text-to-video",
                        {"prompt": "offline test"},
                        FAKE_FAL_KEY,
                        RecordingStopEvent(),
                        lambda *_args: None,
                    )
            self.assertEqual(request.call_count, 3)

    def test_only_transient_queue_gets_retry_with_bounded_backoff(self):
        submitted = queue_submission()
        event = RecordingStopEvent()
        counts = {"POST": 0, "status": 0, "response": 0}

        def fake_request(url, method, api_key, payload=None, timeout=90, extra_headers=None):
            self.assertEqual(api_key, FAKE_FAL_KEY)
            if method == "POST":
                counts["POST"] += 1
                return submitted
            if url == submitted["status_url"]:
                counts["status"] += 1
                if counts["status"] == 1:
                    raise app.FalAPIError("offline network error", network_error=True)
                return {
                    "status": "COMPLETED",
                    "metrics": {"inference_time": 1.29},
                }
            if url == submitted["response_url"]:
                counts["response"] += 1
                if counts["response"] == 1:
                    raise app.FalAPIError(
                        "offline rate limit",
                        status_code=429,
                        retry_after=0.25,
                    )
                return {"video": {"url": "https://v3.fal.media/files/offline.mp4"}}
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(app, "request_json", side_effect=fake_request):
            result, request_id, _elapsed, generation_timing = app.fal_generate(
                "minimax/h3-max/text-to-video",
                {"prompt": "offline test"},
                FAKE_FAL_KEY,
                event,
                lambda *_args: None,
            )

        self.assertEqual(request_id, submitted["request_id"])
        self.assertEqual(result["video"]["url"], "https://v3.fal.media/files/offline.mp4")
        self.assertEqual(
            generation_timing,
            {"seconds": 1.2, "source": "fal_processing"},
        )
        self.assertEqual(counts, {"POST": 1, "status": 2, "response": 2})
        self.assertEqual(event.waits, [0.5, 0.25])

    def test_queue_get_retry_is_bounded_and_skips_nontransient_errors(self):
        event = RecordingStopEvent()
        transient = app.FalAPIError("offline 503", status_code=503)
        with mock.patch.object(app, "request_json", side_effect=transient) as request:
            with self.assertRaisesRegex(app.FalAPIError, "503"):
                app.request_queue_json_with_retry(
                    queue_submission()["status_url"],
                    FAKE_FAL_KEY,
                    timeout=10,
                    stop_event=event,
                )
        self.assertEqual(request.call_count, app.QUEUE_GET_MAX_ATTEMPTS)
        self.assertEqual(event.waits, list(app.QUEUE_GET_BACKOFF_SECONDS))

        event = RecordingStopEvent()
        nontransient = app.FalAPIError("offline 422", status_code=422)
        with mock.patch.object(app, "request_json", side_effect=nontransient) as request:
            with self.assertRaisesRegex(app.FalAPIError, "422"):
                app.request_queue_json_with_retry(
                    queue_submission()["status_url"],
                    FAKE_FAL_KEY,
                    timeout=10,
                    stop_event=event,
                )
        self.assertEqual(request.call_count, 1)
        self.assertEqual(event.waits, [])


class PublicStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.session_root_patch = mock.patch.object(
            app, "SESSION_ROOT", Path(self.temp.name) / "sessions"
        )
        self.session_root_patch.start()
        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()

    def tearDown(self):
        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()
        self.session_root_patch.stop()
        self.temp.cleanup()

    def make_session(self, **overrides):
        config, key = validated_config(**overrides)
        return app.SessionState("unit", config, api_key=key)

    def run_with_offline_media(self, session, generate_side_effect):
        def fake_download(_url, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"offline-video" * 200)

        def fake_extract(_video, output, _position):
            output.write_bytes(b"offline-frame" * 200)
            return output

        def fake_merge(current):
            output = current.directory / f"h3-max-{current.generated_seconds}s-test.mp4"
            output.write_bytes(b"offline-final" * 200)
            return output, {
                "validation": "PASS",
                "duration": float(current.generated_seconds),
                "has_audio": True,
            }

        media_validation = {
            "validation": "PASS",
            "duration": 10.0,
            "width": 480,
            "height": 854,
            "aspect_ratio": "9:16",
            "has_audio": True,
            "video_codec": "H.264",
        }
        with mock.patch.object(
            app, "fal_generate", side_effect=generate_side_effect
        ) as generate, mock.patch.object(
            app, "download_file", side_effect=fake_download
        ), mock.patch.object(
            app, "validate_media", return_value=media_validation
        ), mock.patch.object(
            app, "extract_frame", side_effect=fake_extract
        ), mock.patch.object(
            app, "compare_images", return_value=1.0
        ), mock.patch.object(
            app, "merge_session_clips", side_effect=fake_merge
        ) as merge:
            app.run_session(session)
        return generate, merge

    def test_unlimited_public_state_has_no_fake_target_or_eta(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=1.0,
        )
        session.status = "generating"
        session.clips = [clip_record(1, 10)]
        session.generated_seconds = 10
        public = session.public()
        self.assertEqual(public["config"]["duration_mode"], "unlimited")
        self.assertIsNone(public["target_seconds"])
        self.assertIsNone(public["eta_seconds"])
        self.assertIn("第 2 幕", public["next_chapter"])

    def test_public_clip_exposes_normalized_generation_timing_and_source(self):
        session = self.make_session()
        session.clips = [clip_record(1)]
        session.generated_seconds = 15

        public_clip = session.public()["clips"][0]

        self.assertEqual(public_clip["generation_seconds"], 1.25)
        self.assertEqual(public_clip["generation_time_seconds"], 1.2)
        self.assertEqual(public_clip["generation_time_source"], "gpu_core")

    def test_unlimited_budget_cap_finishes_without_one_extra_submission(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=1.0,
        )
        calls = 0

        def fake_generate(_endpoint, _arguments, _key, _event, progress):
            nonlocal calls
            calls += 1
            submitted = queue_submission(f"offline-{calls}")
            progress("SUBMITTED", submitted["request_id"], submitted["cancel_url"])
            return (
                {"video": {"url": "https://fal.media/offline.mp4"}},
                submitted["request_id"],
                0.1,
                {"seconds": 0.1, "source": "result_ready"},
            )

        generate, merge = self.run_with_offline_media(session, fake_generate)
        public = session.public()
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(merge.call_count, 1)
        self.assertEqual(public["status"], "complete")
        self.assertEqual(public["completion_reason"], "budget_guard_reached")
        self.assertEqual(public["generated_seconds"], 20)
        self.assertEqual(public["submitted_seconds"], 20)
        self.assertEqual(public["spent_estimate_usd"], 1.0)
        self.assertEqual(
            [clip["generation_time_seconds"] for clip in public["clips"]],
            [0.1, 0.1],
        )
        self.assertEqual(
            [clip["generation_time_source"] for clip in public["clips"]],
            ["result_ready", "result_ready"],
        )
        self.assertTrue(public["ready_to_download"])
        self.assertEqual(session.api_key, "")

    def test_start_image_is_used_once_then_released_from_session_memory(self):
        session = self.make_session(
            duration_seconds=10,
            clip_duration=10,
            max_budget_usd=0.5,
        )
        session.config["start_image"] = SECRET_START_IMAGE
        seen_images = []

        def fake_generate(endpoint, arguments, _key, _event, progress):
            seen_images.append((endpoint, arguments.get("image_url")))
            submitted = queue_submission("offline-reference")
            progress("SUBMITTED", submitted["request_id"], submitted["cancel_url"])
            return (
                {"video": {"url": "https://fal.media/offline.mp4"}},
                submitted["request_id"],
                0.1,
                {"seconds": 0.1, "source": "result_ready"},
            )

        self.run_with_offline_media(session, fake_generate)

        self.assertEqual(
            seen_images,
            [("minimax/h3-max/image-to-video", SECRET_START_IMAGE)],
        )
        self.assertNotIn("start_image", session.config)
        self.assertNotIn(SECRET_START_IMAGE, repr(session))
        self.assertNotIn(
            SECRET_START_IMAGE,
            (session.directory / "manifest.json").read_text(encoding="utf-8"),
        )

    def test_unlimited_user_stop_after_one_clip_exports_that_clip(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=2.0,
        )

        def fake_generate(_endpoint, _arguments, _key, event, progress):
            submitted = queue_submission("offline-first")
            progress("SUBMITTED", submitted["request_id"], submitted["cancel_url"])
            event.set()
            return (
                {"video": {"url": "https://fal.media/offline.mp4"}},
                submitted["request_id"],
                0.1,
                {"seconds": 0.1, "source": "result_ready"},
            )

        generate, merge = self.run_with_offline_media(session, fake_generate)
        public = session.public()
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(merge.call_count, 1)
        self.assertEqual(public["status"], "complete")
        self.assertEqual(public["completion_reason"], "user_stopped")
        self.assertEqual(public["generated_seconds"], 10)

    def test_fixed_target_completion_wins_a_stop_after_the_last_clip(self):
        session = self.make_session(
            duration_seconds=10,
            clip_duration=10,
            max_budget_usd=0.5,
        )

        def fake_generate(_endpoint, _arguments, _key, event, progress):
            submitted = queue_submission("offline-fixed-last")
            progress("SUBMITTED", submitted["request_id"], submitted["cancel_url"])
            event.set()
            return (
                {"video": {"url": "https://fal.media/offline.mp4"}},
                submitted["request_id"],
                0.1,
                {"seconds": 0.1, "source": "result_ready"},
            )

        generate, merge = self.run_with_offline_media(session, fake_generate)
        public = session.public()
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(merge.call_count, 1)
        self.assertEqual(public["status"], "complete")
        self.assertEqual(public["completion_reason"], "target_reached")

    def test_unlimited_stop_during_second_submission_exports_only_downloaded_clip(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=2.0,
        )
        calls = 0

        def fake_generate(_endpoint, _arguments, _key, event, progress):
            nonlocal calls
            calls += 1
            submitted = queue_submission(f"offline-{calls}")
            progress("SUBMITTED", submitted["request_id"], submitted["cancel_url"])
            if calls == 2:
                event.set()
                raise RuntimeError("任务已由用户停止")
            return (
                {"video": {"url": "https://fal.media/offline.mp4"}},
                submitted["request_id"],
                0.1,
                {"seconds": 0.1, "source": "result_ready"},
            )

        generate, merge = self.run_with_offline_media(session, fake_generate)
        public = session.public()
        self.assertEqual(generate.call_count, 2)
        self.assertEqual(merge.call_count, 1)
        self.assertEqual(public["status"], "complete")
        self.assertEqual(public["completion_reason"], "user_stopped")
        self.assertEqual(public["generated_seconds"], 10)
        self.assertEqual(public["submitted_seconds"], 20)
        self.assertEqual(public["spent_estimate_usd"], 1.0)

    def test_stop_before_first_submission_never_merges_or_spends(self):
        for duration_mode in ("fixed", "unlimited"):
            with self.subTest(duration_mode=duration_mode):
                overrides = {
                    "duration_mode": duration_mode,
                    "duration_seconds": 10,
                    "clip_duration": 10,
                    "max_budget_usd": 0.5,
                }
                session = self.make_session(**overrides)
                session.stop_event.set()
                generate, merge = self.run_with_offline_media(
                    session,
                    AssertionError("paid generation must not be called"),
                )
                public = session.public()
                generate.assert_not_called()
                merge.assert_not_called()
                self.assertEqual(public["status"], "stopped")
                self.assertEqual(public["submitted_seconds"], 0)
                self.assertFalse(public["ready_to_download"])

    def test_unlimited_partial_merge_uses_actual_completed_duration(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=1.0,
        )
        session.directory.mkdir(parents=True)
        session.clips = [clip_record(1, 10)]
        session.generated_seconds = 10
        (session.directory / "clip-001.mp4").write_bytes(b"offline-input")

        def fake_run(arguments, **_kwargs):
            Path(arguments[1]).write_bytes(b"offline-output")
            return mock.Mock(returncode=0, stderr="")

        receipt = {"validation": "PASS", "duration": 10.0, "has_audio": True}
        with mock.patch.object(
            app, "compile_swift_tool", return_value=Path("/offline/merge_clips")
        ), mock.patch.object(
            app.subprocess, "run", side_effect=fake_run
        ) as run, mock.patch.object(
            app, "validate_media", return_value=receipt
        ) as validate:
            output, result = app.merge_session_clips(session)

        self.assertEqual(output.name, "h3-max-10s-9x16.mp4")
        self.assertEqual(result["duration"], 10.0)
        self.assertEqual(len(run.call_args.args[0]), 3)
        validate.assert_called_once_with(
            output,
            expected_duration=10,
            require_audio=True,
            aspect_ratio="9:16",
        )

        fixed = self.make_session(
            duration_seconds=20,
            clip_duration=10,
            max_budget_usd=1.0,
        )
        fixed.clips = [clip_record(1, 10)]
        fixed.generated_seconds = 10
        with self.assertRaisesRegex(RuntimeError, "片段数量不完整"):
            app.merge_session_clips(fixed)

    def test_public_state_recursively_omits_sensitive_generation_fields(self):
        session = self.make_session()
        session.config.update(
            {
                "api_key": "config-api-key-secret",
                "start_image": SECRET_START_IMAGE,
                "request_id": "config-request-secret",
                "prompt": "config-prompt-secret",
                "media_info": "config-media-receipt-secret",
            }
        )
        clip = clip_record(1)
        clip.update(
            {
                "request_id": "clip-request-secret",
                "prompt": "clip-prompt-secret",
                "media_info": "clip-media-receipt-secret",
            }
        )
        clip["media"].update(
            {
                "request_id": "nested-request-secret",
                "prompt": "nested-prompt-secret",
                "media_info": "nested-media-receipt-secret",
            }
        )
        session.clips.append(clip)
        session.active_request_id = "active-request-secret"
        session.active_cancel_url = (
            "https://queue.fal.run/private/active-cancel-url-secret"
        )
        session.cancel_attempted_request_id = "cancel-attempt-request-secret"
        # Remote error bodies can echo queue metadata. The public projection
        # must not turn its human-readable error field into a side channel.
        session.error = (
            "fal failure: api_key=error-key-secret; "
            "request_id=error-request-secret; prompt=error-prompt-secret; "
            "media_info=error-media-receipt-secret"
        )

        public = session.public()
        forbidden_keys = {
            "api_key",
            "start_image",
            "request_id",
            "active_request_id",
            "active_cancel_url",
            "cancel_url",
            "cancel_attempted_request_id",
            "prompt",
            "media_info",
        }
        self.assertTrue(forbidden_keys.isdisjoint(all_mapping_keys(public)))

        serialized = json.dumps(public, ensure_ascii=False)
        for secret in (
            "config-api-key-secret",
            SECRET_START_IMAGE,
            "config-request-secret",
            "config-prompt-secret",
            "config-media-receipt-secret",
            "clip-request-secret",
            "clip-prompt-secret",
            "clip-media-receipt-secret",
            "nested-request-secret",
            "nested-prompt-secret",
            "nested-media-receipt-secret",
            "active-request-secret",
            "active-cancel-url-secret",
            "cancel-attempt-request-secret",
            "error-key-secret",
            "error-request-secret",
            "error-prompt-secret",
            "error-media-receipt-secret",
        ):
            self.assertNotIn(secret, serialized)
        self.assertEqual(public["clips"][0]["media"]["validation"], "PASS")

    def test_stop_cancels_once_and_keeps_queue_credentials_out_of_manifests(self):
        session = self.make_session()
        submitted = queue_submission("private-request-id")
        session.status = "generating"
        session.active_request_id = submitted["request_id"]
        session.active_cancel_url = submitted["cancel_url"]

        with mock.patch.object(
            app,
            "request_json",
            return_value={"status": "CANCELLATION_REQUESTED"},
        ) as request:
            outcome = app.stop_generation_session(session)
            duplicate = app.stop_generation_session(session)

        self.assertEqual(outcome, "CANCELLATION_REQUESTED")
        self.assertEqual(duplicate, "CANCEL_ALREADY_ATTEMPTED")
        self.assertTrue(session.stop_event.is_set())
        request.assert_called_once_with(
            submitted["cancel_url"],
            "PUT",
            FAKE_FAL_KEY,
            timeout=15,
        )

        manifest = (session.directory / "manifest.json").read_text(encoding="utf-8")
        public = json.dumps(session.public(), ensure_ascii=False)
        representation = repr(session)
        for private_value in (
            FAKE_FAL_KEY,
            submitted["request_id"],
            submitted["cancel_url"],
        ):
            self.assertNotIn(private_value, manifest)
            self.assertNotIn(private_value, public)
            self.assertNotIn(private_value, representation)

    def test_stop_claims_cancel_credentials_before_worker_finalization_race(self):
        session = self.make_session(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=1.0,
        )
        submitted = queue_submission("race-request")
        session.status = "generating"
        session.active_request_id = submitted["request_id"]
        session.active_cancel_url = submitted["cancel_url"]
        persist_calls = 0

        def racing_persist():
            nonlocal persist_calls
            persist_calls += 1
            if persist_calls == 1:
                # Model the worker clearing its public active state immediately
                # after observing stop_event, before the HTTP handler sends PUT.
                session.active_request_id = ""
                session.active_cancel_url = ""

        with mock.patch.object(
            session, "persist", side_effect=racing_persist
        ), mock.patch.object(
            app,
            "best_effort_cancel_fal_request",
            return_value="CANCELLATION_REQUESTED",
        ) as cancel:
            outcome = app.stop_generation_session(session)

        self.assertEqual(outcome, "CANCELLATION_REQUESTED")
        cancel.assert_called_once_with(submitted["cancel_url"], FAKE_FAL_KEY)

    def test_already_completed_cancel_race_is_benign(self):
        for status_code, detail in (
            (400, '{"status":"ALREADY_COMPLETED"}'),
            (409, '{"detail":"Request already completed"}'),
        ):
            with self.subTest(status_code=status_code):
                already_complete = app.FalAPIError(
                    f"fal API HTTP {status_code}: {detail}",
                    status_code=status_code,
                )
                with mock.patch.object(app, "request_json", side_effect=already_complete):
                    result = app.best_effort_cancel_fal_request(
                        queue_submission()["cancel_url"],
                        FAKE_FAL_KEY,
                    )
                self.assertEqual(result, "ALREADY_COMPLETED")

    def test_preview_and_final_download_flags_follow_real_artifact_state(self):
        session = self.make_session()
        session.status = "generating"
        self.assertFalse(session.public()["ready_to_preview"])

        session.clips = [clip_record(1)]
        session.generated_seconds = 15
        self.assertFalse(session.public()["ready_to_preview"])

        session.status = "finalizing"
        self.assertTrue(session.public()["ready_to_preview"])
        self.assertTrue(session.public()["finalizing"])

        session.status = "generating"
        session.clips.append(clip_record(2))
        session.generated_seconds = 30
        self.assertTrue(session.public()["ready_to_preview"])

        session.status = "complete"
        session.final_filename = "h3-max-5min.mp4"
        absent = session.public()
        self.assertFalse(absent["ready_to_download"])
        self.assertEqual(absent["final_url"], "")
        self.assertEqual(absent["download_url"], "")

        session.directory.mkdir(parents=True, exist_ok=True)
        (session.directory / session.final_filename).write_bytes(b"offline-test-video")
        session.final_validation = {"validation": "PASS", "duration": 300.0}
        ready = session.public()
        self.assertTrue(ready["ready_to_download"])
        self.assertEqual(ready["final_url"], "/media/unit/h3-max-5min.mp4")
        self.assertEqual(ready["download_url"], "/download/unit/video.mp4")
        self.assertEqual(ready["final_validation"]["validation"], "PASS")

    def test_rejected_remote_submission_does_not_count_as_spend(self):
        session = self.make_session()
        rejected = RuntimeError(
            'fal API HTTP 403: {"detail":"User is locked. Reason: Exhausted balance."}'
        )
        with mock.patch.object(
            app, "fal_generate", side_effect=rejected
        ), mock.patch.object(app.traceback, "print_exc"):
            app.run_session(session)
        public = session.public()
        self.assertEqual(public["status"], "failed")
        self.assertEqual(public["submitted_seconds"], 0)
        self.assertEqual(public["spent_estimate_usd"], 0)
        self.assertIn("余额不足", public["error"])
        self.assertEqual(session.api_key, "")

    def test_landscape_session_passes_aspect_ratio_to_first_text_to_video_job(self):
        session = self.make_session(
            duration_seconds=10,
            clip_duration=10,
            aspect_ratio="16:9",
            max_budget_usd=0.5,
        )
        rejected_after_capture = RuntimeError("offline stop after argument capture")
        with mock.patch.object(
            app, "fal_generate", side_effect=rejected_after_capture
        ) as generate, mock.patch.object(app.traceback, "print_exc"):
            app.run_session(session)

        endpoint, arguments = generate.call_args.args[:2]
        self.assertEqual(endpoint, "minimax/h3-max/text-to-video")
        self.assertEqual(arguments["aspect_ratio"], "16:9")
        self.assertEqual(arguments["duration"], 10)
        self.assertEqual(session.public()["status"], "failed")

    def test_restore_revalidates_a_saved_final_against_its_landscape_ratio(self):
        session = self.make_session(
            duration_seconds=10,
            clip_duration=10,
            aspect_ratio="16:9",
            max_budget_usd=0.5,
        )
        session.directory.mkdir(parents=True)
        session.status = "complete"
        session.final_filename = "h3-max-10s-16x9.mp4"
        (session.directory / session.final_filename).write_bytes(b"offline-landscape")
        session.persist()
        manifest_path = session.directory / "manifest.json"
        legacy_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        legacy_manifest["config"].pop("duration_mode")
        legacy_manifest.pop("completion_reason")
        manifest_path.write_text(
            json.dumps(legacy_manifest, ensure_ascii=False),
            encoding="utf-8",
        )
        app.SESSIONS.clear()

        restored_receipt = {
            "validation": "PASS",
            "duration": 10.0,
            "width": 1344,
            "height": 768,
            "aspect_ratio": "16:9",
            "has_audio": True,
        }
        with mock.patch.object(
            app, "validate_media", return_value=restored_receipt
        ) as validate:
            app.restore_manifests()

        validate.assert_called_once_with(
            (session.directory / session.final_filename).resolve(),
            expected_duration=10,
            require_audio=True,
            aspect_ratio="16:9",
        )
        self.assertEqual(app.SESSIONS["unit"].config["aspect_ratio"], "16:9")
        self.assertEqual(app.SESSIONS["unit"].config["duration_mode"], "fixed")
        self.assertEqual(app.SESSIONS["unit"].completion_reason, "target_reached")
        self.assertEqual(app.SESSIONS["unit"].status, "complete")
        app.SESSIONS.clear()

    def test_restore_uses_generated_duration_for_unlimited_and_never_resumes(self):
        config, key = validated_config(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=1.0,
            preset="custom_channel",
            custom_channel_name="夜航频道",
            custom_channel_style="深蓝电影夜景",
        )
        complete = app.SessionState("unlimited-complete", config, api_key=key)
        complete.directory.mkdir(parents=True)
        complete.status = "complete"
        complete.generated_seconds = 10
        complete.submitted_seconds = 10
        complete.completion_reason = "user_stopped"
        complete.final_filename = "h3-max-10s-9x16.mp4"
        (complete.directory / complete.final_filename).write_bytes(b"offline-unlimited")
        complete.persist()

        interrupted = app.SessionState(
            "unlimited-interrupted",
            dict(config),
            api_key=FAKE_FAL_KEY,
            status="generating",
            generated_seconds=10,
            submitted_seconds=10,
        )
        interrupted.persist()
        app.SESSIONS.clear()

        restored_receipt = {
            "validation": "PASS",
            "duration": 10.0,
            "width": 480,
            "height": 854,
            "aspect_ratio": "9:16",
            "has_audio": True,
        }
        with mock.patch.object(
            app, "validate_media", return_value=restored_receipt
        ) as validate, mock.patch.object(app, "run_session") as run:
            app.restore_manifests()

        validate.assert_called_once_with(
            (complete.directory / complete.final_filename).resolve(),
            expected_duration=10,
            require_audio=True,
            aspect_ratio="9:16",
        )
        run.assert_not_called()
        restored = app.SESSIONS["unlimited-complete"]
        self.assertEqual(restored.config["duration_mode"], "unlimited")
        self.assertEqual(restored.completion_reason, "user_stopped")
        self.assertEqual(restored.status, "complete")
        self.assertEqual(app.SESSIONS["unlimited-interrupted"].status, "interrupted")
        self.assertEqual(app.SESSIONS["unlimited-interrupted"].api_key, "")
        app.SESSIONS.clear()

    def test_restore_rebuilds_idempotency_index_from_only_a_one_way_hash(self):
        raw_request_id = str(uuid.uuid4())
        request_digest = app.client_request_hash(raw_request_id)
        session = self.make_session()
        session.client_request_hash = request_digest
        session.status = "failed"
        session.persist()

        manifest_path = session.directory / "manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        self.assertEqual(manifest["_client_request_hash"], request_digest)
        self.assertNotIn(raw_request_id, manifest_text)
        self.assertNotIn(FAKE_FAL_KEY, manifest_text)
        self.assertNotIn("client_request_id", manifest_text)
        self.assertNotIn("client_request_hash", json.dumps(session.public()))

        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()
        app.restore_manifests()

        self.assertEqual(app.CLIENT_REQUEST_SESSIONS[request_digest], "unit")
        self.assertEqual(app.SESSIONS["unit"].client_request_hash, request_digest)
        self.assertEqual(app.SESSIONS["unit"].api_key, "")


class UrlTrustTests(unittest.TestCase):
    @staticmethod
    def start_http_server(handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, thread

    def test_queue_urls_require_https_and_the_exact_fal_queue_host(self):
        allowed = "https://queue.fal.run/minimax/h3-max/requests/abc/status"
        self.assertTrue(
            app.is_allowed_https_url(allowed, exact_hosts=app.ALLOWED_QUEUE_HOSTS)
        )
        self.assertEqual(app.require_queue_url(allowed, "status_url"), allowed)

        rejected = (
            "http://queue.fal.run/job",
            "https://queue.fal.run.evil.example/job",
            "https://sub.queue.fal.run/job",
            "https://queue.fal.run@evil.example/job",
            "https://user@queue.fal.run/job",
            "https://queue.fal.run:444/job",
        )
        for url in rejected:
            with self.subTest(url=url):
                self.assertFalse(
                    app.is_allowed_https_url(url, exact_hosts=app.ALLOWED_QUEUE_HOSTS)
                )
                with self.assertRaisesRegex(RuntimeError, "不受信任"):
                    app.require_queue_url(url, "status_url")

    def test_media_urls_allow_fal_media_subdomains_but_not_impostors(self):
        for url in (
            "https://fal.media/files/video.mp4",
            "https://v3.fal.media/files/video.mp4",
        ):
            with self.subTest(url=url):
                self.assertTrue(
                    app.is_allowed_https_url(url, root_hosts=app.ALLOWED_MEDIA_ROOTS)
                )

        for url in (
            "http://fal.media/files/video.mp4",
            "https://fal.media.evil.example/video.mp4",
            "https://notfal.media/video.mp4",
            "https://fal.media@evil.example/video.mp4",
            "https://user@fal.media/video.mp4",
            "https://cdn.fal.media:444/video.mp4",
        ):
            with self.subTest(url=url):
                self.assertFalse(
                    app.is_allowed_https_url(url, root_hosts=app.ALLOWED_MEDIA_ROOTS)
                )

    def test_authenticated_requests_never_follow_http_redirects(self):
        observations = {"source": 0, "sink": 0, "sink_authorization": None}

        class SinkHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def _record(self):
                observations["sink"] += 1
                observations["sink_authorization"] = self.headers.get("Authorization")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b"{}")

            do_GET = _record
            do_POST = _record
            do_PUT = _record

        sink, sink_thread = self.start_http_server(SinkHandler)
        sink_url = f"http://127.0.0.1:{sink.server_address[1]}/credential-sink"

        class RedirectHandler(BaseHTTPRequestHandler):
            redirect_code = 302

            def log_message(self, *_args):
                return

            def _redirect(self):
                observations["source"] += 1
                self.send_response(self.redirect_code)
                self.send_header("Location", sink_url)
                self.end_headers()

            do_GET = _redirect
            do_POST = _redirect
            do_PUT = _redirect

        source, source_thread = self.start_http_server(RedirectHandler)
        source_url = f"http://127.0.0.1:{source.server_address[1]}/redirect"
        try:
            for method, code in (("GET", 302), ("POST", 307), ("PUT", 308)):
                with self.subTest(method=method, code=code):
                    RedirectHandler.redirect_code = code
                    payload = {"offline": True} if method == "POST" else None
                    with self.assertRaisesRegex(app.FalAPIError, "重定向") as raised:
                        app.request_json(
                            source_url,
                            method,
                            FAKE_FAL_KEY,
                            payload=payload,
                            timeout=2,
                        )
                    self.assertNotIn(FAKE_FAL_KEY, str(raised.exception))
            self.assertEqual(observations["source"], 3)
            self.assertEqual(observations["sink"], 0)
            self.assertIsNone(observations["sink_authorization"])
        finally:
            source.shutdown()
            source.server_close()
            source_thread.join(timeout=5)
            sink.shutdown()
            sink.server_close()
            sink_thread.join(timeout=5)

    def test_media_download_never_follows_a_redirect(self):
        observations = {"source": 0, "sink": 0}

        class SinkHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_GET(self):
                observations["sink"] += 1
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"offline-video" * 200)

        sink, sink_thread = self.start_http_server(SinkHandler)
        sink_url = f"http://127.0.0.1:{sink.server_address[1]}/media"

        class RedirectHandler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                return

            def do_GET(self):
                observations["source"] += 1
                self.send_response(302)
                self.send_header("Location", sink_url)
                self.end_headers()

        source, source_thread = self.start_http_server(RedirectHandler)
        source_url = f"http://127.0.0.1:{source.server_address[1]}/redirect"
        try:
            with tempfile.TemporaryDirectory() as temporary:
                destination = Path(temporary) / "video.mp4"
                with mock.patch.object(app, "is_allowed_https_url", return_value=True):
                    with self.assertRaises(urllib.error.HTTPError):
                        app.download_file(source_url, destination)
                self.assertFalse(destination.exists())
            self.assertEqual(observations, {"source": 1, "sink": 0})
        finally:
            source.shutdown()
            source.server_close()
            source_thread.join(timeout=5)
            sink.shutdown()
            sink.server_close()
            sink_thread.join(timeout=5)


class StaticFrontendContractTests(unittest.TestCase):
    def test_paid_confirmation_controls_exist_only_in_the_start_dialog(self):
        source = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        for retired_id in (
            "maxBudget",
            "costEstimate",
            "costDetail",
            "paidConfirmed",
        ):
            with self.subTest(retired_id=retired_id):
                self.assertNotIn(f'id="{retired_id}"', source)

        for dialog_id in (
            "paidDialog",
            "paidDialogCost",
            "paidDialogDetail",
            "paidDialogBudgetField",
            "confirmMaxBudget",
            "cancelPaidDialog",
            "confirmPaidStart",
        ):
            with self.subTest(dialog_id=dialog_id):
                self.assertEqual(source.count(f'id="{dialog_id}"'), 1)

        self.assertIn('id="confirmMaxBudget" type="number" min="0" max="150"', source)
        self.assertIn("不是 fal 最终账单保证", source)


class HttpBoundaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.original_session_root = app.SESSION_ROOT
        app.SESSION_ROOT = Path(cls.temp.name) / "sessions"
        app.SESSION_ROOT.mkdir(parents=True)
        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()
        cls.server = app.create_server("127.0.0.1", 0)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()
        app.SESSION_ROOT = cls.original_session_root
        cls.temp.cleanup()

    def setUp(self):
        app.SESSIONS.clear()
        app.CLIENT_REQUEST_SESSIONS.clear()

    def request_json(self, path, payload=None):
        data = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base + path,
            data=data,
            headers={"Content-Type": "application/json"} if data is not None else {},
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def get_status(self, path):
        request = urllib.request.Request(self.base + path, method="GET")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                response.read()
                return response.status
        except urllib.error.HTTPError as error:
            error.read()
            return error.code

    def test_health_reports_the_public_duration_boundary(self):
        status, health = self.request_json("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(health["ok"])
        self.assertEqual(
            health["duration_limits"],
            {"min_seconds": 10, "max_seconds": 1800, "step_seconds": 1},
        )
        self.assertEqual(health["duration_modes"], ["fixed", "unlimited"])
        self.assertEqual(health["aspect_ratios"], ["9:16", "16:9"])
        self.assertEqual(health["max_local_estimated_budget_usd"], 150.0)
        self.assertEqual(
            {preset["id"] for preset in health["presets"]},
            set(app.PRESETS),
        )

    def test_http_rejects_untrusted_authority_origin_and_non_json_posts(self):
        port = self.server.server_address[1]
        with self.assertRaisesRegex(ValueError, "127.0.0.1"):
            app.create_server("0.0.0.0", 0)

        def raw_request(method, path, *, body=None, headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            try:
                connection.request(method, path, body=body, headers=headers or {})
                response = connection.getresponse()
                raw = response.read()
                return response.status, json.loads(raw.decode("utf-8"))
            finally:
                connection.close()

        status, body = raw_request(
            "GET",
            "/api/health",
            headers={"Host": "attacker.invalid"},
        )
        self.assertEqual(status, 421)
        self.assertIn("本机", body["error"])

        valid_host = f"127.0.0.1:{port}"
        payload = json.dumps({"api_key": FAKE_FAL_KEY}).encode("utf-8")
        status, body = raw_request(
            "POST",
            "/api/key/check",
            body=payload,
            headers={
                "Host": valid_host,
                "Origin": "https://attacker.invalid",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(status, 403)
        self.assertIn("来源", body["error"])

        status, body = raw_request(
            "POST",
            "/api/key/check",
            body=payload,
            headers={"Host": valid_host, "Content-Type": "text/plain"},
        )
        self.assertEqual(status, 415)
        self.assertIn("application/json", body["error"])

        with mock.patch.object(app, "check_fal_key", return_value={"ok": True}):
            status, body = raw_request(
                "POST",
                "/api/key/check",
                body=payload,
                headers={
                    "Host": valid_host,
                    "Origin": f"http://{valid_host}",
                    "Content-Type": "application/json; charset=utf-8",
                },
            )
        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])

    def test_http_rejects_only_out_of_range_or_fractional_durations(self):
        for duration in (9, 1801, -1, 10.25):
            with self.subTest(duration=duration):
                status, body = self.request_json(
                    "/api/session/start",
                    valid_payload(duration_seconds=duration, mode="mock", mock=True),
                )
                self.assertEqual(status, 400)
                self.assertIn("时长", body["error"])

    def test_http_start_still_requires_key_and_literal_paid_confirmation(self):
        without_key = valid_payload(mode="mock", mock=True)
        without_key.pop("api_key")
        status, body = self.request_json("/api/session/start", without_key)
        self.assertEqual(status, 400)
        self.assertIn("API Key", body["error"])

        status, body = self.request_json(
            "/api/session/start",
            valid_payload(mode="mock", mock=True, paid_confirmed=False),
        )
        self.assertEqual(status, 400)
        self.assertIn("确认", body["error"])

    def test_start_rejects_missing_noncanonical_or_oversized_client_request_ids(self):
        canonical = str(uuid.uuid4())
        invalid_values = {
            "missing": None,
            "non_string": 123,
            "too_short": canonical[:-1],
            "too_long": canonical + "0",
            "no_hyphens": canonical.replace("-", ""),
            "braced": "{" + canonical + "}",
            "leading_space": " " + canonical,
            "trailing_space": canonical + " ",
            "invalid_hex": "z" + canonical[1:],
        }
        with mock.patch.object(app, "run_session") as run:
            for label, value in invalid_values.items():
                with self.subTest(label=label):
                    payload = valid_payload()
                    if label == "missing":
                        payload.pop("client_request_id")
                    else:
                        payload["client_request_id"] = value
                    status, body = self.request_json("/api/session/start", payload)
                    self.assertEqual(status, 400)
                    self.assertIn("client_request_id", body["error"])

        run.assert_not_called()
        self.assertEqual(app.SESSIONS, {})
        self.assertEqual(app.CLIENT_REQUEST_SESSIONS, {})

    def test_retry_with_same_client_request_id_reuses_session_and_safe_receipt(self):
        raw_request_id = str(uuid.uuid4())
        ignored_payload_marker = "must-not-be-written-as-request-payload"
        ran_sessions = []
        ran = threading.Event()

        def offline_session_stub(session):
            ran_sessions.append(session.session_id)
            ran.set()

        first_payload = valid_payload(
            client_request_id=raw_request_id.upper(),
            ignored_payload_marker=ignored_payload_marker,
        )
        with mock.patch.object(app, "run_session", side_effect=offline_session_stub) as run:
            first_status, first = self.request_json(
                "/api/session/start", first_payload
            )
            self.assertTrue(ran.wait(2))
            # A browser can retry only the idempotency key after losing the
            # first response. It must not need to repeat the key or paid body.
            retry_status, retry = self.request_json(
                "/api/session/start",
                {"client_request_id": raw_request_id},
            )

        self.assertEqual(first_status, 201)
        self.assertFalse(first["idempotent_replay"])
        self.assertEqual(retry_status, 200)
        self.assertTrue(retry["idempotent_replay"])
        self.assertEqual(
            first["session"]["session_id"], retry["session"]["session_id"]
        )
        self.assertEqual(ran_sessions, [first["session"]["session_id"]])
        self.assertEqual(run.call_count, 1)

        session_id = first["session"]["session_id"]
        manifest_path = app.SESSION_ROOT / session_id / "manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        expected_digest = app.client_request_hash(raw_request_id)
        self.assertEqual(manifest["_client_request_hash"], expected_digest)
        for private_value in (
            raw_request_id,
            raw_request_id.upper(),
            FAKE_FAL_KEY,
            ignored_payload_marker,
        ):
            self.assertNotIn(private_value, manifest_text)
        for response in (first, retry):
            serialized = json.dumps(response, ensure_ascii=False)
            self.assertNotIn(raw_request_id, serialized.lower())
            self.assertNotIn(expected_digest, serialized)
            self.assertNotIn("_client_request_hash", all_mapping_keys(response))

    def test_concurrent_same_client_request_id_atomically_starts_one_worker(self):
        raw_request_id = str(uuid.uuid4())
        payload = valid_payload(client_request_id=raw_request_id)
        caller_count = 8
        start_gate = threading.Barrier(caller_count + 1)
        worker_started = threading.Event()
        release_worker = threading.Event()
        results = []
        client_errors = []
        shared_lock = threading.Lock()
        generated_sessions = []

        def offline_session_stub(session):
            with shared_lock:
                generated_sessions.append(session.session_id)
            worker_started.set()
            release_worker.wait(5)

        def concurrent_start():
            try:
                start_gate.wait(timeout=5)
                response = self.request_json("/api/session/start", dict(payload))
                with shared_lock:
                    results.append(response)
            except Exception as error:  # pragma: no cover - asserted below
                with shared_lock:
                    client_errors.append(error)

        callers = [
            threading.Thread(target=concurrent_start, daemon=True)
            for _ in range(caller_count)
        ]
        with mock.patch.object(app, "run_session", side_effect=offline_session_stub) as run:
            try:
                for caller in callers:
                    caller.start()
                start_gate.wait(timeout=5)
                for caller in callers:
                    caller.join(timeout=5)
                self.assertTrue(worker_started.wait(2))
            finally:
                release_worker.set()
                for caller in callers:
                    caller.join(timeout=5)

        self.assertEqual(client_errors, [])
        self.assertTrue(all(not caller.is_alive() for caller in callers))
        self.assertEqual(len(results), caller_count)
        statuses = [status for status, _body in results]
        self.assertEqual(statuses.count(201), 1)
        self.assertEqual(statuses.count(200), caller_count - 1)
        session_ids = {
            body["session"]["session_id"] for _status, body in results
        }
        self.assertEqual(len(session_ids), 1)
        self.assertEqual(generated_sessions, list(session_ids))
        self.assertEqual(run.call_count, 1)
        self.assertEqual(len(app.SESSIONS), 1)
        self.assertEqual(len(app.CLIENT_REQUEST_SESSIONS), 1)
        self.assertEqual(
            app.CLIENT_REQUEST_SESSIONS[app.client_request_hash(raw_request_id)],
            next(iter(session_ids)),
        )

    def test_valid_confirmed_start_is_accepted_without_running_generation(self):
        ran_offline_stub = threading.Event()

        def offline_session_stub(_session):
            ran_offline_stub.set()

        with mock.patch.object(app, "run_session", side_effect=offline_session_stub):
            status, body = self.request_json(
                "/api/session/start",
                valid_payload(mode="mock", mock=True),
            )

        self.assertEqual(status, 201)
        self.assertTrue(body["ok"])
        self.assertTrue(ran_offline_stub.wait(2))
        serialized = json.dumps(body, ensure_ascii=False)
        self.assertNotIn(FAKE_FAL_KEY, serialized)
        self.assertNotIn("api_key", all_mapping_keys(body))
        self.assertEqual(body["session"]["config"]["duration_seconds"], 300)

    def test_arbitrary_landscape_duration_is_accepted_without_running_generation(self):
        ran_offline_stub = threading.Event()

        def offline_session_stub(_session):
            ran_offline_stub.set()

        with mock.patch.object(app, "run_session", side_effect=offline_session_stub):
            status, body = self.request_json(
                "/api/session/start",
                valid_payload(
                    duration_seconds=47,
                    clip_duration=15,
                    aspect_ratio="16:9",
                    max_budget_usd=2.35,
                ),
            )

        self.assertEqual(status, 201)
        self.assertTrue(ran_offline_stub.wait(2))
        config = body["session"]["config"]
        self.assertEqual(config["duration_seconds"], 47)
        self.assertEqual(sum(config["clip_schedule"]), 47)
        self.assertEqual(config["aspect_ratio"], "16:9")

    def test_http_unlimited_start_requires_explicit_cap_and_has_no_fixed_target(self):
        ran_offline_stub = threading.Event()

        def offline_session_stub(_session):
            ran_offline_stub.set()

        payload = valid_payload(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=0.5,
            preset="custom_channel",
            custom_channel_name="夜航频道",
            custom_channel_style="深蓝电影夜景",
        )
        payload.pop("duration_seconds")
        with mock.patch.object(app, "run_session", side_effect=offline_session_stub):
            status, body = self.request_json("/api/session/start", payload)

        self.assertEqual(status, 201)
        self.assertTrue(ran_offline_stub.wait(2))
        config = body["session"]["config"]
        self.assertEqual(config["duration_mode"], "unlimited")
        self.assertIsNone(config["duration_seconds"])
        self.assertIsNone(body["session"]["target_seconds"])
        self.assertEqual(config["custom_channel_name"], "夜航频道")
        self.assertNotIn("custom_channel_style", config)

        missing_cap = dict(payload)
        missing_cap["client_request_id"] = str(uuid.uuid4())
        missing_cap.pop("max_budget_usd")
        status, body = self.request_json("/api/session/start", missing_cap)
        self.assertEqual(status, 400)
        self.assertIn("本地预计费用上限", body["error"])

    def test_key_check_is_fully_mocked_and_never_calls_a_real_network(self):
        calls = []

        def fake_request_json(url, method, api_key, payload=None, timeout=90):
            calls.append((url, method, api_key, payload, timeout))
            if url.startswith("https://api.fal.ai/v1/models/pricing?"):
                return {"prices": [{"endpoint_id": "minimax/h3-max/text-to-video"}]}
            if url == "https://api.fal.ai/v1/account/billing?expand=credits":
                return {"credits": {"current_balance": 7.5, "currency": "USD"}}
            raise AssertionError(f"unexpected network target: {url}")

        with mock.patch.object(app, "request_json", side_effect=fake_request_json):
            status, body = self.request_json(
                "/api/key/check", {"api_key": FAKE_FAL_KEY}
            )

        self.assertEqual(status, 200)
        self.assertTrue(body["ok"])
        self.assertEqual(body["provider"], "fal")
        self.assertEqual(body["balance"]["current_balance"], 7.5)
        self.assertFalse(body["generation_verified"])
        wording = f"{body['message']} {body['balance_note']}"
        self.assertIn("价格", wording)
        self.assertNotIn("可以生成", wording)
        self.assertNotIn("服务连接成功", wording)
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[0][0].startswith("https://api.fal.ai/v1/models/pricing?"))
        self.assertIn("minimax%2Fh3-max%2Ftext-to-video", calls[0][0])
        self.assertIn("minimax%2Fh3-max%2Fimage-to-video", calls[0][0])
        self.assertEqual(calls[0][1], "GET")
        self.assertEqual(
            calls[1][0], "https://api.fal.ai/v1/account/billing?expand=credits"
        )
        self.assertEqual(calls[1][1], "GET")
        self.assertNotIn(FAKE_FAL_KEY, json.dumps(body, ensure_ascii=False))

    def test_static_and_media_path_traversal_are_rejected(self):
        traversal_paths = (
            "/../app.py",
            "/%2e%2e/app.py",
            "/media/../app.py",
            "/media/%2e%2e/%2e%2e/app.py",
        )
        for path in traversal_paths:
            with self.subTest(path=path):
                self.assertEqual(self.get_status(path), 404)

    def test_final_download_is_404_until_a_complete_file_exists(self):
        config, key = validated_config()
        session = app.SessionState("download-test", config, api_key=key)
        with app.SESSIONS_LOCK:
            app.SESSIONS[session.session_id] = session

        self.assertEqual(self.get_status("/download/download-test/video.mp4"), 404)

        session.directory.mkdir(parents=True, exist_ok=True)
        session.final_filename = "h3-max-5min.mp4"
        (session.directory / session.final_filename).write_bytes(b"0123456789")
        session.status = "complete"
        self.assertTrue(session.public()["ready_to_download"])
        self.assertEqual(self.get_status("/download/download-test/video.mp4"), 200)

        ranged = urllib.request.Request(
            self.base + "/download/download-test/video.mp4",
            headers={"Range": "bytes=2-5"},
        )
        with urllib.request.urlopen(ranged, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"2345")
            self.assertEqual(response.headers["Content-Range"], "bytes 2-5/10")
            self.assertIn("attachment", response.headers["Content-Disposition"])

        suffix = urllib.request.Request(
            self.base + "/download/download-test/video.mp4",
            headers={"Range": "bytes=-4"},
        )
        with urllib.request.urlopen(suffix, timeout=5) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(response.read(), b"6789")

        invalid = urllib.request.Request(
            self.base + "/download/download-test/video.mp4",
            headers={"Range": "bytes=bad"},
        )
        with self.assertRaises(urllib.error.HTTPError) as raised:
            urllib.request.urlopen(invalid, timeout=5)
        self.assertEqual(raised.exception.code, 416)

    def test_unlimited_download_uses_generated_duration_instead_of_null_target(self):
        config, key = validated_config(
            duration_mode="unlimited",
            clip_duration=10,
            max_budget_usd=0.5,
        )
        session = app.SessionState("unlimited-download", config, api_key=key)
        session.directory.mkdir(parents=True, exist_ok=True)
        session.status = "complete"
        session.generated_seconds = 10
        session.completion_reason = "budget_guard_reached"
        session.final_filename = "h3-max-10s-9x16.mp4"
        (session.directory / session.final_filename).write_bytes(b"offline-unlimited")
        with app.SESSIONS_LOCK:
            app.SESSIONS[session.session_id] = session

        request = urllib.request.Request(
            self.base + "/download/unlimited-download/video.mp4",
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 200)
            self.assertIn("10", response.headers["Content-Disposition"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
