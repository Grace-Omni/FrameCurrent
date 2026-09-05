"""First-run tests. All network and media commands here are offline substitutes."""
import io
import json
import subprocess
import unittest
import urllib.error
from unittest import mock

import launcher


class LauncherTests(unittest.TestCase):
    def inspect(self, payload):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(launcher.urllib.request, "build_opener", return_value=opener):
            return launcher.existing_instance()

    def test_reopen_requires_product_checkout_and_version_match(self):
        health = {"ok": True, "app_id": "framecurrent", "instance_id": launcher.app.INSTANCE_ID,
                  "version": launcher.app.APP_VERSION}
        self.assertEqual(self.inspect(health), "current")
        for field in ("ok", "app_id", "instance_id", "version"):
            with self.subTest(field=field):
                self.assertEqual(self.inspect(dict(health, **{field: "wrong"})), "other")

    def test_absent_socket_is_distinct_from_occupied_unresponsive_service(self):
        for error, expected in ((ConnectionRefusedError(), "absent"), (TimeoutError(), "other")):
            opener = mock.Mock()
            opener.open.side_effect = urllib.error.URLError(error)
            with mock.patch.object(launcher.urllib.request, "build_opener", return_value=opener):
                self.assertEqual(launcher.existing_instance(), expected)

    def test_non_object_health_does_not_count_as_our_server(self):
        self.assertEqual(self.inspect(["not a health response"]), "other")

    def test_failed_swift_command_cannot_report_success(self):
        with mock.patch.object(launcher.sys, "platform", "darwin"), \
             mock.patch.object(launcher.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "swiftc")), \
             mock.patch.object(launcher.app, "prepare_media_tools") as prepare:
            self.assertFalse(launcher.diagnose())
        prepare.assert_not_called()

    def test_existing_app_is_reopened_without_preflight_or_generation(self):
        with mock.patch.object(launcher.sys, "argv", ["launcher.py"]), \
             mock.patch.object(launcher, "existing_instance", return_value="current"), \
             mock.patch.object(launcher, "diagnose") as diagnose, \
             mock.patch.object(launcher.subprocess, "run") as opened:
            self.assertEqual(launcher.main(), 0)
        diagnose.assert_not_called()
        opened.assert_called_once_with(["/usr/bin/open", launcher.LOCAL_URL], check=False)

    def test_foreign_service_is_not_opened_or_killed(self):
        with mock.patch.object(launcher.sys, "argv", ["launcher.py"]), \
             mock.patch.object(launcher, "existing_instance", return_value="other"), \
             mock.patch.object(launcher, "diagnose") as diagnose, \
             mock.patch.object(launcher.subprocess, "run") as command:
            self.assertEqual(launcher.main(), 1)
        diagnose.assert_not_called()
        command.assert_not_called()

    def test_health_redirect_is_not_followed(self):
        captured = []
        def build(*handlers):
            captured.extend(handlers)
            result = mock.Mock()
            result.open.side_effect = urllib.error.HTTPError("http://localhost", 302, "redirect", {}, None)
            return result
        with mock.patch.object(launcher.urllib.request, "build_opener", side_effect=build):
            self.assertEqual(launcher.existing_instance(), "other")
        redirect = captured[-1]
        self.assertIsNone(redirect.redirect_request(None, None, 302, "", {}, "https://example.com"))


if __name__ == "__main__":
    unittest.main()
