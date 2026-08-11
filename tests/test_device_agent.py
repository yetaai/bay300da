import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from bay300_device_agent.agent import DeviceAgent
from bay300_device_agent.cli import build_parser,interactive_shell,main,manage_device
from bay300_device_agent.client import Bay300Client
from bay300_device_agent.config import load_authorization,save_authorization
from bay300_device_agent.devices import DeviceRegistry


class FakeResponse:
    def __init__(self,value):self.value=value
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self):return json.dumps(self.value).encode()


class DeviceAuthorizationTests(unittest.TestCase):
    @patch("urllib.request.urlopen")
    def test_request_and_poll_use_separate_unauthenticated_secrets(self,urlopen):
        urlopen.side_effect=[FakeResponse({"authorizationRequestId":"r1","pollingToken":"poll"}),
                             FakeResponse({"status":"pending_authorization"})]
        client=Bay300Client("https://bay300.test")
        pending=client.request_authorization("op@example.test","Store Devices Admin")
        result=client.poll_authorization(pending["authorizationRequestId"],pending["pollingToken"])
        self.assertEqual("pending_authorization",result["status"])
        first=urlopen.call_args_list[0].args[0];second=urlopen.call_args_list[1].args[0]
        self.assertNotIn("X-Device-Credential",first.headers)
        self.assertEqual("poll",second.headers["X-device-poll-token"])

    def test_authorization_is_mode_600_and_local_registry_owns_configuration(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_AUTHORIZATION":f"{directory}/authorization",
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            save_authorization({"server":"https://bay300.test","storeId":"s1","storeName":"Lovell","token":"secret"})
            self.assertEqual("secret",load_authorization()["token"])
            self.assertEqual(0,os.stat(f"{directory}/authorization").st_mode&0o077)
            registry=DeviceRegistry();row=registry.add("Front","bill_printer","Front-CUPS")
            self.assertEqual(["bill_print"],row["capabilities"])
            self.assertEqual("Front-CUPS",registry.list()[0]["configuration"])
            self.assertNotIn("configuration",registry.server_rows()[0])

    def test_unknown_job_type_is_failed_without_execution(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_WORK":f"{directory}/work","BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry();device=registry.add("Front","bill_printer","")
            agent=DeviceAgent({"server":"https://bay300.test","token":"secret"},registry)
            agent.client.sync_devices=lambda rows:None
            agent.client.claim=lambda device_id:{"jobId":"job1","jobType":"scanner_upload"}
            failures=[];agent.client.failed=lambda job_id,message:failures.append((job_id,message))
            self.assertTrue(agent.run_once());self.assertEqual(device["id"],registry.list()[0]["id"])
            self.assertIn("Unsupported",failures[0][1])

    def test_cli_device_management_matches_gui_registry_operations(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_WORK":f"{directory}/work","BAY300DA_DEVICES":f"{directory}/devices.json",
        }),patch("bay300_device_agent.cli.DeviceAgent.sync") as sync:
            parser=build_parser();authorization={"server":"https://bay300.test","token":"secret"}
            output=StringIO()
            with redirect_stdout(output):
                manage_device(parser.parse_args(["device","add","--name","Front","--type","bill_printer",
                    "--configuration","Front-CUPS"]),authorization)
            registry=DeviceRegistry();device_id=registry.list()[0]["id"]
            manage_device(parser.parse_args(["device","edit",device_id,"--name","Reception"]),authorization)
            manage_device(parser.parse_args(["device","block",device_id]),authorization)
            self.assertEqual("blocked",registry.list()[0]["status"])
            manage_device(parser.parse_args(["device","unblock",device_id]),authorization)
            manage_device(parser.parse_args(["device","edit",device_id,"--type","other"]),authorization)
            manage_device(parser.parse_args(["device","check",device_id]),authorization)
            listing=StringIO()
            with redirect_stdout(listing):
                manage_device(parser.parse_args(["device","list","--json"]),authorization)
            self.assertEqual("Reception",json.loads(listing.getvalue())[0]["name"])
            manage_device(parser.parse_args(["device","remove",device_id,"--yes"]),authorization)
            self.assertEqual([],registry.list());self.assertEqual(7,sync.call_count)

    def test_registry_rejects_invalid_cli_and_gui_values(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry()
            with self.assertRaises(ValueError):registry.add("","bill_printer")
            with self.assertRaises(ValueError):registry.add("Front","unsupported")
            with self.assertRaises(KeyError):registry.remove("missing")

    def test_no_subcommand_opens_command_shell_without_requiring_authorization(self):
        with patch("bay300_device_agent.cli.interactive_shell") as shell:
            main([])
        shell.assert_called_once()

    def test_shell_ctrl_c_interrupts_run_and_returns_to_prompt(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_AUTHORIZATION":f"{directory}/authorization",
            "BAY300DA_WORK":f"{directory}/work",
        }):
            save_authorization({"server":"https://bay300.test","storeId":"s1","storeName":"Lovell",
                                "token":"secret","tokenExpiresAt":"2099-01-01T00:00:00Z"})
            output=StringIO()
            with patch("builtins.input",side_effect=["run","exit"]),\
                 patch("bay300_device_agent.cli.DeviceAgent.run_forever",side_effect=KeyboardInterrupt),\
                 redirect_stdout(output):
                interactive_shell(build_parser())
            self.assertIn("Command interrupted",output.getvalue())
            self.assertIn("shell closed",output.getvalue())

    def test_platform_run_launchers_open_gui_explicitly(self):
        packaging=Path(__file__).resolve().parents[1]/"packaging"
        for relative in ("linux/run.sh","macos/run.command","windows/run.cmd"):
            self.assertRegex((packaging/relative).read_text(),r"bay300da(?:\.exe|%|\")?.*gui|BAY300DA.*gui")


if __name__=="__main__":unittest.main()
