import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from bay300_device_agent.agent import DeviceAgent
from bay300_device_agent.cli import (build_parser,dispatch,enable_shell_line_editing,
                                     interactive_shell,main,manage_device,show_types)
from bay300_device_agent.client import Bay300Client
from bay300_device_agent.config import load_authorization,save_authorization
from bay300_device_agent.devices import DeviceRegistry
from bay300_device_agent.gui_requirements import tkinter_installation_help
from bay300_device_agent.local_devices import (discover_local_devices,
                                                normalize_local_configuration,
                                                print_local_devices)
from bay300_device_agent.uninstall import managed_install_root,uninstall_managed


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
                manage_device(parser.parse_args(["device","add","--name","Front","--type","printer",
                    "--configuration","Front-CUPS"]),authorization)
            registry=DeviceRegistry();device_id=registry.list()[0]["id"]
            manage_device(parser.parse_args(["device","edit",device_id,"--name","Reception"]),authorization)
            manage_device(parser.parse_args(["device","block","rec"]),authorization)
            self.assertEqual("blocked",registry.list()[0]["status"])
            manage_device(parser.parse_args(["device","unblock","RECEP"]),authorization)
            manage_device(parser.parse_args(["device","edit","reception","--type","scanner"]),authorization)
            manage_device(parser.parse_args(["device","check","re"]),authorization)
            listing=StringIO()
            with redirect_stdout(listing):
                manage_device(parser.parse_args(["device","list","--json"]),authorization)
            self.assertEqual("Reception",json.loads(listing.getvalue())[0]["name"])
            manage_device(parser.parse_args(["device","remove","rece","--yes"]),authorization)
            self.assertEqual([],registry.list());self.assertEqual(7,sync.call_count)

    def test_add_expands_unique_local_printer_prefix_to_complete_identifier(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }),patch("bay300_device_agent.local_devices.discover_local_devices",return_value=[
            {"kind":"printer","name":"PDFwriter","identifier":"PDFwriter"},
        ]),patch("bay300_device_agent.cli.DeviceAgent.sync"):
            parser=build_parser();authorization={"server":"https://bay300.test","token":"secret"}
            manage_device(parser.parse_args([
                "device","add","--name","pdf","--type","printer",
            ]),authorization)
            manage_device(parser.parse_args([
                "device","add","--name","PDF test","--type","printer","--configuration","PdF",
            ]),authorization)
            self.assertEqual(["PDFwriter","PDFwriter"],[
                row["configuration"] for row in DeviceRegistry().list()
            ])

    def test_local_configuration_prefix_must_be_unambiguous(self):
        rows=[
            {"kind":"printer","name":"PDFwriter","identifier":"PDFwriter"},
            {"kind":"printer","name":"PDF warehouse","identifier":"PDF_warehouse"},
        ]
        with self.assertRaisesRegex(ValueError,"ambiguous: PDF warehouse, PDFwriter"):
            normalize_local_configuration("pdf","bill_printer",rows)
        self.assertEqual("remote-queue",normalize_local_configuration(
            "remote-queue","bill_printer",rows))

    def test_registry_rejects_invalid_cli_and_gui_values(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry()
            with self.assertRaises(ValueError):registry.add("","bill_printer")
            with self.assertRaises(ValueError):registry.add("Front","unsupported")
            with self.assertRaises(KeyError):registry.remove("missing")
            self.assertEqual([],registry.add("Future scanner","scanner")["capabilities"])

    def test_device_add_records_card_reader_processor_without_payment_capability(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }),patch("bay300_device_agent.cli.DeviceAgent.sync") as sync:
            parser=build_parser();authorization={"server":"https://bay300.test","token":"secret"}
            output=StringIO()
            with redirect_stdout(output):
                manage_device(parser.parse_args([
                    "device","add","--name","Front counter","--type","cardReader",
                    "--processor","helcm",
                ]),authorization)
            row=DeviceRegistry().list()[0]
            self.assertEqual("card_reader",row["type"])
            self.assertEqual("helcim_smart_terminal",row["processor"])
            self.assertEqual("Helcim Smart Terminal",row["processorName"])
            self.assertEqual("integration_required",row["status"])
            self.assertEqual([],row["capabilities"])
            self.assertIn("Card reader integration is available through Bay300 Support",output.getvalue())
            self.assertNotIn("configuration",DeviceRegistry().server_rows()[0])
            sync.assert_called_once()

    def test_type_query_shows_short_names_and_needs_no_authorization(self):
        parser=build_parser();output=StringIO()
        with patch("bay300_device_agent.cli.load_authorization") as load,redirect_stdout(output):
            dispatch(parser.parse_args(["type"]))
        load.assert_not_called()
        self.assertIn("cardReader  Card reader",output.getvalue())
        for short,full_name in (("helcm","Helcim Smart Terminal"),
                                ("squar","Square Terminal"),
                                ("paypl","PayPal Point of Sale")):
            self.assertLessEqual(len(short),5)
            self.assertIn(f"{short}  {full_name}",output.getvalue())

    def test_card_reader_requires_known_or_named_other_processor(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry()
            with self.assertRaisesRegex(ValueError,"Choose a supported"):
                registry.add("Counter","card_reader")
            with self.assertRaisesRegex(ValueError,"only used with type cardReader"):
                registry.add("Front","bill_printer",processor="helcim_smart_terminal")
            with self.assertRaisesRegex(ValueError,"Processor name is required"):
                registry.add("Counter","card_reader",processor="other")
            custom=registry.add("Counter","card_reader",processor="other",
                                processor_name="Regional Processor")
            self.assertEqual("Regional Processor",custom["processorName"])
            self.assertEqual("integration_required",registry.check(custom["id"])["status"])
            registry.block(custom["id"])
            self.assertEqual("blocked",registry.update(custom["id"],name="Counter 2")["status"])
            self.assertEqual("integration_required",registry.block(custom["id"],False)["status"])

    def test_registry_resolves_unique_case_insensitive_name_prefix(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry()
            front=registry.add("Front-CUPS","bill_printer")
            registry.add("Back Office","bill_printer")
            self.assertEqual(front["id"],registry.resolve("fRoNt")["id"])
            self.assertEqual(front["id"],registry.resolve(front["id"])["id"])

    def test_registry_rejects_missing_or_ambiguous_name_prefix(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            registry=DeviceRegistry()
            registry.add("Front Counter","bill_printer")
            registry.add("Front Office","bill_printer")
            with self.assertRaisesRegex(ValueError,"ambiguous: Front Counter, Front Office"):
                registry.resolve("FRONT")
            with self.assertRaisesRegex(ValueError,"No local device matches"):
                registry.resolve("missing")

    def test_upgrade_removes_stale_executable_capabilities_from_reserved_types(self):
        with tempfile.TemporaryDirectory() as directory,patch.dict(os.environ,{
            "BAY300DA_DEVICES":f"{directory}/devices.json",
        }):
            Path(f"{directory}/devices.json").write_text(json.dumps([{
                "id":"legacy","name":"Generic","type":"printer",
                "capabilities":["bill_print","check_print"],"status":"ready",
            }]))
            self.assertEqual([],DeviceRegistry().list()[0]["capabilities"])

    def test_no_subcommand_opens_command_shell_without_requiring_authorization(self):
        with patch("bay300_device_agent.cli.interactive_shell") as shell:
            main([])
        shell.assert_called_once()

    def test_version_subcommand_is_stable_and_needs_no_authorization(self):
        output=StringIO()
        with patch("bay300_device_agent.cli.importlib.metadata.version",return_value="0.5.2"),\
             patch("bay300_device_agent.cli.load_authorization") as load,redirect_stdout(output):
            dispatch(build_parser().parse_args(["version"]))
        self.assertEqual("bay300da 0.5.2\n",output.getvalue())
        load.assert_not_called()

    def test_local_discovers_cups_printers_and_sane_document_scanners(self):
        outputs={("lpstat","-d"):"system default destination: Front-CUPS",
            ("lpstat","-p"):"printer Front-CUPS is idle. enabled since today\nprinter Back stopped since yesterday",
            ("scanimage","-L"):"device `airscan:e0:Office Scanner' is WSD Office Scanner ip=10.0.0.8"}
        with patch("bay300_device_agent.local_devices.shutil.which",side_effect=lambda name:f"/usr/bin/{name}"),\
             patch("bay300_device_agent.local_devices._run",side_effect=lambda command:outputs.get(tuple(command),"")):
            rows=discover_local_devices("Linux")
        self.assertEqual(["printer","printer","scanner"],[row["kind"] for row in rows])
        self.assertTrue(rows[0]["default"]);self.assertEqual("Front-CUPS",rows[0]["identifier"])
        self.assertEqual("airscan:e0:Office Scanner",rows[2]["identifier"])

    def test_local_output_is_read_only_and_states_current_support(self):
        output=StringIO()
        with redirect_stdout(output):
            print_local_devices([{"kind":"printer","name":"Front","identifier":"Front-CUPS",
                "source":"CUPS","default":True,"detail":"idle"}])
        self.assertIn("does not add or authorize",output.getvalue())
        self.assertIn("only bill_printer tasks are implemented",output.getvalue())

    def test_uninstall_removes_only_managed_program_and_preserves_local_data(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory)/"home";root=Path(directory)/"managed";venv=root/"venv"
            executable=venv/"bin/bay300da";executable.parent.mkdir(parents=True)
            executable.write_text("launcher");(root/".bay300da-managed-install").touch()
            launcher=home/".local/bin/bay300da";launcher.parent.mkdir(parents=True)
            launcher.symlink_to(executable)
            authorization=home/".bay300/authorization";authorization.parent.mkdir(parents=True)
            authorization.write_text("preserved")
            output=StringIO()
            with redirect_stdout(output):
                uninstall_managed(True,prefix=venv,home=home,system="Linux")
            self.assertFalse(root.exists());self.assertFalse(launcher.exists())
            self.assertEqual("preserved",authorization.read_text())
            self.assertIn("revoke its authorization",output.getvalue())

    def test_uninstall_rejects_an_unmanaged_virtual_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            prefix=Path(directory)/"project/.venv";prefix.mkdir(parents=True)
            with self.assertRaisesRegex(RuntimeError,"not in a managed installation"):
                managed_install_root(prefix,Path(directory)/"home","Linux")

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

    def test_shell_enables_terminal_line_editing_before_first_prompt(self):
        with patch("bay300_device_agent.cli.enable_shell_line_editing",return_value=True) as enable,\
             patch("builtins.input",return_value="exit"):
            interactive_shell(build_parser())
        enable.assert_called_once_with()

    def test_shell_line_editing_loads_readline(self):
        readline=type("Readline",(),{
            "set_auto_history":lambda self,value:setattr(self,"auto_history",value),
            "set_history_length":lambda self,value:setattr(self,"history_length",value),
        })()
        with patch("bay300_device_agent.cli.importlib.import_module",return_value=readline) as load:
            self.assertTrue(enable_shell_line_editing())
        load.assert_called_once_with("readline")
        self.assertTrue(readline.auto_history);self.assertEqual(200,readline.history_length)

    def test_platform_run_launchers_open_gui_explicitly(self):
        packaging=Path(__file__).resolve().parents[1]/"packaging"
        for relative in ("linux/run.sh","macos/run.command","windows/run.cmd"):
            self.assertRegex((packaging/relative).read_text(),r"bay300da(?:\.exe|%|\")?.*gui|BAY300DA.*gui")

    def test_missing_tkinter_help_is_platform_specific(self):
        self.assertIn("sudo apt install python3-tk",
                      tkinter_installation_help("Linux","ubuntu debian"))
        self.assertIn("sudo dnf install python3-tkinter",
                      tkinter_installation_help("Linux","fedora"))
        self.assertIn("python.org/downloads/macos",tkinter_installation_help("Darwin"))
        self.assertIn(f"brew install python-tk@{os.sys.version_info.major}.{os.sys.version_info.minor}",
                      tkinter_installation_help("Darwin"))
        self.assertIn("Ask Bay300 Help",tkinter_installation_help("Darwin"))
        windows=tkinter_installation_help("Windows")
        self.assertIn("tcl/tk and IDLE",windows)
        self.assertIn("Administrator access is normally not required",windows)

    def test_gui_reports_missing_tkinter_before_requiring_authorization(self):
        args=build_parser().parse_args(["gui"])
        with patch("bay300_device_agent.cli.require_tkinter",
                   side_effect=SystemExit("install tkinter")),\
             patch("bay300_device_agent.cli.load_authorization") as load:
            with self.assertRaisesRegex(SystemExit,"install tkinter"):dispatch(args)
        load.assert_not_called()


if __name__=="__main__":unittest.main()
