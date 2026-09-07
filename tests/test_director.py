"""Offline tests of improvisation, frame evidence, novelty and paid request boundaries."""
import copy
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

import director
import test_app
from test_app import app, sample_plan, validated_config, FAKE_FAL_KEY, queue_submission


def second_plan():
    plan = sample_plan()
    plan.update(title="意外的回应", event_key="echo-reveals-hollow-root",
                action="The cat taps the exposed root with its paw, producing a hollow echo. The girl stops, kneels on dry ground and listens; the sound reveals that their intended stepping place is hollow and she signals a different approach.",
                state_change="A hollow echo exposes unstable footing and forces a different crossing decision.",
                cause="The cat's paw contacts an already visible exposed root.")
    return plan


def response(plan, cost=0.003):
    return {"output": json.dumps(plan), "usage": {"cost": cost}}


class ImprovisedStoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.patch = mock.patch.object(app, "SESSION_ROOT", Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        app.SHUTTING_DOWN.clear()

    def session(self, **kwargs):
        config, key = validated_config(duration_seconds=20, clip_duration=10,
                                       max_budget_usd=2.0, **kwargs)
        return app.SessionState("improvised-offline", config, api_key=key)

    def test_director_uses_actual_samples_past_memory_and_remaining_time(self):
        history = [sample_plan()]
        args = director.build_director_arguments({"genre": "healing"}, 10, 2,
            history, ["first", "middle", "last"], remaining_seconds=10)
        self.assertEqual(args["image_urls"], ["first", "middle", "last"])
        context = json.loads(args["prompt"])
        self.assertEqual(context["remaining_seconds_including_this_scene"], 10)
        self.assertEqual(context["all_previously_requested_events_not_proof_of_execution"][0]["event_key"], history[0]["event_key"])
        self.assertIn("LAST image is the current physical state", args["system_prompt"])
        self.assertIn("do NOT claim the proposed scene has already happened", args["system_prompt"])
        self.assertGreater(args["temperature"], 1)
        self.assertFalse(args["enable_web_search"])

    def test_new_broadcast_has_fresh_randomness_even_with_identical_world(self):
        contexts = [json.loads(director.build_director_arguments({}, 10, 1, [], ["first"])["prompt"])
                    for _ in range(10)]
        self.assertEqual(len({item["variation_nonce"] for item in contexts}), 10)
        self.assertTrue(all(item["remaining_seconds_including_this_scene"] is None for item in contexts))

    def test_event_key_representation_is_normalized_without_a_paid_retry(self):
        for key in ("commander_faces_beacon_alone", "Commander Faces Beacon Alone",
                    "commander–faces—beacon-alone", "commander-faces-beacon-alone"):
            with self.subTest(key=key):
                session = self.session()
                output = "```json\n" + json.dumps(dict(sample_plan(), event_key=key)) + "\n```"
                with mock.patch.object(app, "fal_generate", return_value=(
                        {"output": output, "usage": {"cost": .001}}, "job", .1, {})) as generate:
                    plan = app.plan_scene(session, 0, 10, "reference")
                self.assertEqual(plan["event_key"], "commander-faces-beacon-alone")
                self.assertEqual(generate.call_count, 1)
                self.assertAlmostEqual(session.director_spent_usd, .001)

    def test_normalizing_an_event_key_cannot_bypass_repeat_detection(self):
        candidate = dict(second_plan(), event_key="Discover_Shelter_Path")
        with self.assertRaises(director.StoryPlanError) as caught:
            director.parse_scene_plan(response(candidate), [sample_plan()])
        self.assertEqual(caught.exception.category, "novelty")

    def test_format_retry_uses_clean_fields_instead_of_escaped_raw_output(self):
        session = self.session()
        captured = []
        results = iter((response(dict(sample_plan(), event_key="event/invalid")), response(sample_plan())))
        def generate(_endpoint, args, *_rest):
            captured.append(copy.deepcopy(args))
            return next(results), "job", .1, {}
        with mock.patch.object(app, "fal_generate", side_effect=generate):
            app.plan_scene(session, 0, 10, "reference")
        context = json.loads(captured[1]["prompt"])
        self.assertEqual(context["retry_task"], "correct_format")
        self.assertEqual(context["rejected_candidate"]["action"], sample_plan()["action"])
        self.assertNotIn("previous_output", context["rejected_candidate"])
        self.assertIn("fix ONLY the invalid representation", captured[1]["system_prompt"])

    def test_broken_json_is_not_silently_repaired_or_sent_as_retry_context(self):
        session = self.session()
        broken = '{"title": "test", \\"action\\": \\"bad escaping\\"}'
        results = iter(({"output": broken}, response(sample_plan())))
        captured = []
        def generate(_endpoint, args, *_rest):
            captured.append(copy.deepcopy(args))
            return next(results), "job", .1, {}
        with self.assertRaises(director.StoryPlanError):
            director.parse_scene_plan({"output": broken}, [])
        with mock.patch.object(app, "fal_generate", side_effect=generate):
            app.plan_scene(session, 0, 10, "reference")
        context = json.loads(captured[1]["prompt"])
        self.assertEqual(context["retry_task"], "correct_format")
        self.assertEqual(context["rejected_candidate"], {})
        self.assertNotIn(broken, captured[1]["prompt"])

    def test_story_failure_detail_survives_restart_without_becoming_public(self):
        session = self.session()
        session.status = "failed"
        session.error = "剧情续写未通过检查：剧情续写字段不完整：event_key"
        session.persist()
        saved = json.loads((session.directory / "manifest.json").read_text())
        self.assertEqual(saved["_story_error_detail"], session.error)
        self.assertNotIn("event_key", saved["error"])
        self.assertNotIn("_story_error_detail", session.public())
        with mock.patch.object(app, "SESSIONS", {}), mock.patch.object(app, "CLIENT_REQUEST_SESSIONS", {}):
            app.restore_manifests()
            self.assertEqual(app.SESSIONS[session.session_id].error, session.error)
            self.assertIn("格式", app.SESSIONS[session.session_id].public()["error"])

    def test_rewording_or_numbering_an_old_event_does_not_bypass_novelty_gate(self):
        for candidate in (sample_plan(), dict(sample_plan(), event_key="a-different-name"),
                          dict(sample_plan(), action=sample_plan()["action"] + " Scene 27.")):
            with self.assertRaises(director.StoryPlanError):
                director.parse_scene_plan(response(candidate), [sample_plan()])
        self.assertEqual(director.parse_scene_plan(response(second_plan()), [sample_plan()])["event_key"], second_plan()["event_key"])

    def test_minor_changes_self_reported_repeats_and_malformed_plans_are_rejected(self):
        for candidate in (dict(sample_plan(), impact=2), dict(sample_plan(), repeats_event=True),
                          dict(sample_plan(), repeat_of=["old-event"]), dict(sample_plan(), cause=""),
                          dict(sample_plan(), action="Just wave the grass."), dict(sample_plan(), impact=True)):
            with self.assertRaises(director.StoryPlanError):
                director.parse_scene_plan(response(candidate), [])
        with self.assertRaises(director.StoryPlanError):
            director.parse_scene_plan({"output": "not json"}, [])

    def test_real_worker_uses_director_for_every_scene_and_keeps_audit_records(self):
        for mode in ("fixed", "unlimited"):
            session = self.session(duration_mode=mode)
            captured = []
            plans = iter((sample_plan(), second_plan()))
            def generate(endpoint, arguments, _key, event, progress):
                captured.append((endpoint, copy.deepcopy(arguments)))
                progress("SUBMITTED", f"job-{len(captured)}", queue_submission()["cancel_url"])
                if endpoint == director.DIRECTOR_ENDPOINT:
                    result = response(next(plans))
                else:
                    result = {"video": {"url": "https://fal.media/offline.mp4"}}
                    if len(captured) == 4:
                        event.set()
                return result, "job", .1, {"seconds": .1, "source": "result_ready"}
            with mock.patch.object(app.traceback, "print_exc"):
                test_app.PublicStateTests.run_with_offline_media(self, session, generate, real_director=True)
            self.assertEqual([item[0] for item in captured],
                [director.DIRECTOR_ENDPOINT, "minimax/h3-max/image-to-video"] * 2)
            self.assertEqual(len(captured[2][1]["image_urls"]), 3)
            self.assertIn(sample_plan()["event_key"], captured[2][1]["prompt"])
            self.assertIn(second_plan()["action"], captured[3][1]["prompt"])
            self.assertEqual(session.status, "complete")
            self.assertAlmostEqual(session.director_spent_usd, .006)
            self.assertAlmostEqual(session.spent_estimate_usd, 1.006)
            saved = json.loads((session.directory / "manifest.json").read_text())
            self.assertEqual(len(saved["_story_history"]), 2)
            self.assertNotIn("_story_history", session.public())
            self.assertNotIn(FAKE_FAL_KEY, json.dumps(saved))
            self.assertIn(second_plan()["action"], (session.directory / "prompt-002.json").read_text())

    def test_duplicate_candidate_gets_one_revision_and_never_a_script_fallback(self):
        session = self.session()
        session.story_history = [sample_plan()]
        captured = []
        def generate(_endpoint, args, *_rest):
            captured.append(copy.deepcopy(args))
            return response(sample_plan()), "job", .1, {}
        with mock.patch.object(app, "fal_generate", side_effect=generate):
            with self.assertRaisesRegex(director.StoryPlanError, "未通过检查"):
                app.plan_scene(session, 1, 10, "last-frame")
        self.assertEqual(len(captured), 2)
        self.assertTrue(json.loads(captured[1]["prompt"])["previous_rejection"])
        self.assertEqual(json.loads(captured[1]["prompt"])["retry_task"], "new_story")
        self.assertEqual(len(session.story_history), 1)
        self.assertAlmostEqual(session.director_spent_usd, .006)

    def test_budget_includes_director_and_does_not_submit_an_unaffordable_video(self):
        session = self.session()
        session.config["max_budget_usd"] = .51
        with mock.patch.object(app, "fal_generate") as generate:
            with self.assertRaises(app.StoryBudgetReached):
                app.plan_scene(session, 0, 10, "reference")
            generate.assert_not_called()
        self.assertEqual(session.director_spent_usd, 0)

    def test_lost_planner_response_is_not_resubmitted_and_reservation_is_retained(self):
        session = self.session()
        with mock.patch.object(app, "fal_generate", side_effect=TimeoutError("response lost")) as generate:
            with self.assertRaises(TimeoutError):
                app.plan_scene(session, 0, 10, "reference")
        self.assertEqual(generate.call_count, 1)
        self.assertAlmostEqual(session.director_spent_usd, .02)

    def test_stop_during_planning_does_not_submit_video(self):
        session = self.session()
        calls = []
        def generate(endpoint, args, _key, event, progress):
            calls.append(endpoint)
            event.set()
            return response(sample_plan()), "job", .1, {}
        test_app.PublicStateTests.run_with_offline_media(self, session, generate, real_director=True)
        self.assertEqual(calls, [director.DIRECTOR_ENDPOINT])
        self.assertEqual(session.submitted_seconds, 0)
        self.assertEqual(session.status, "stopped")

    def test_paid_dialog_allowance_matches_server_for_irregular_durations(self):
        for duration in (10, 11, 30, 47, 300, 1800):
            config, _ = validated_config(duration_seconds=duration, clip_duration=10, max_budget_usd=150)
            self.assertAlmostEqual(config["estimated_cost_usd"],
                duration * .05 + len(config["clip_schedule"]) * .04)
