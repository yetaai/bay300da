# Bay300 Devices Admin (`bay300da`)

`bay300da` is the store-machine program that owns physical printer/scanner configuration.
After authorization its window title is **(Store Name) Devices Admin**. Bay300 receives only
device identity, type, capabilities, status, and task outcomes; printer names, scanner identifiers,
drivers, paths, and other local configuration remain on the store machine.

## Requirements and installation

- Python 3.11 or newer;
- an HTTPS connection to `https://bay300.com`;
- Tk/Tkinter only when using the GUI app;
- a locally installed printer driver/CUPS queue for current Bill printing.

Store Owner/OP users should normally open **Device Monitor → Install Devices Admin**. Bay300
provides separate Windows, Linux, and macOS bundles and highlights the likely package based on the
browser platform. Each bundle contains only this agent project and platform launchers. The public
agent source is [yetaai/bay300da](https://github.com/yetaai/bay300da); it is separate from the
private Bay300 application and contains no service credentials or user authorization tokens.

Bay300 supports two operating styles. Choose based on how the store computer is used, not on anyone's
technical experience:

- **Install GUI app** lets a person add, edit, check, block, and remove local devices. It uses
  Tkinter, a standard Python window toolkit. You do not need to know or configure Tkinter. If it
  is absent, installation still completes and prints the platform-specific next step. Running
  `bay300da gui` repeats that guidance until Tkinter is available.
- **Install CLI app** installs command-line operation with no window and needs no Tkinter. It can
  authorize, add, list, edit, remove, block, unblock, and check devices, synchronize immediately,
  and process queued work with `bay300da run`. Installation does not automatically create a systemd service,
  macOS LaunchAgent, or Windows service/Scheduled Task.

On Linux or macOS, install the GUI app in one line:

```bash
curl -fsSL https://raw.githubusercontent.com/yetaai/bay300da/main/install.sh | bash
```

Install the CLI app in one line:

```bash
curl -fsSL https://raw.githubusercontent.com/yetaai/bay300da/main/install.sh | env BAY300DA_HEADLESS=1 bash
```

The installer checks the requirements for the selected style, creates a private virtual environment,
places a `bay300da` launcher in `~/.local/bin`, and adds that directory to the user's PATH. The PATH
change is idempotent and applies to newly opened terminals; the installer does not overwrite other
profile settings. A missing Tkinter installation does not prevent the CLI from working. At the end
of a GUI installation, the installer prints the command or action needed to add Tkinter. It never
creates an authorization token. Review the script before running it if required by store policy.
Windows users should use the ZIP package from Device Monitor.

To install manually from the public repository instead:

```bash
git clone --depth 1 https://github.com/yetaai/bay300da.git
cd bay300da
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
```

On Debian/Ubuntu, install Tk and CUPS first when absent:

```bash
sudo apt install python3-tk cups-client
```

Installing operating-system packages usually requires `sudo` on Linux. Fedora/RHEL normally uses
`sudo dnf install python3-tkinter`; Arch normally uses `sudo pacman -S tk`. On macOS, use a current
Homebrew formula matching the agent's Python—for example, `brew install python-tk@3.13`—or use a
current python.org Python build that includes Tcl/Tk; `sudo` is normally unnecessary. On Windows, open the
official Python installer, choose **Modify**, and enable **tcl/tk and IDLE**. These are operating-
system/Python-distribution components, so Tkinter is deliberately not declared as a pip dependency.
The displayed error also suggests the exact question to enter in **Ask Bay300 Help** for more detail.

## Authorize and run

```bash
bay300da authorize --url https://bay300.com
```

Enter an active Store Operator email or telephone login. Bay300 places a request at the top of
that user's workspace. Open it, choose the correct store, and approve. The program then writes:

```text
~/.bay300/authorization
```

The JSON contains the user login as audit metadata and a store-agent authorization token—not a
browser/user session token. Unix permissions are forced to `0600`. On Windows, `bay300da` removes
inherited permissions and restricts the file ACL to the running Windows account. The token expires
after 30 days; run `bay300da authorize` again after expiration.

Open the GUI app:

```bash
bay300da gui
```

If Tkinter is unavailable, this command exits with the appropriate installation command or action
and does not require an existing Bay300 authorization first.

It supports Add new device, Remove device, Edit/Config device, Block/Unblock, Check device status,
and Poll server now. Polling uses exponential idle backoff from 2 to 60 seconds; Poll server now,
local configuration changes, task activity, and connectivity recovery reset the cycle.

Use the CLI app when that better fits the store computer:

Start the interactive shell by omitting a subcommand:

```text
$ bay300da
bay300da> device list
bay300da> poll
bay300da> run
^C
Command interrupted. Returning to the bay300da prompt.
bay300da> exit
```

Within the shell, use `help`, `help device`, or `help device add`. `Ctrl+C` interrupts a running
command and returns to the prompt. `exit`, `quit`, or `Ctrl+D` closes the shell.

The same operations remain available as one-line commands:

```bash
bay300da device list
bay300da device add --name "Front counter" --type bill_printer --configuration "Front-CUPS"
bay300da device edit DEVICE_ID --name "Reception printer"
bay300da device block DEVICE_ID
bay300da device unblock DEVICE_ID
bay300da device check DEVICE_ID
bay300da device remove DEVICE_ID
bay300da poll
bay300da doctor
bay300da once
bay300da run
bay300da version
```

`bay300da version` prints the installed agent release, such as `bay300da 0.4.2`, and does
not require store authorization.

Use `bay300da device list --json` for scripts. Add `--yes` to `device remove` to skip its safety
prompt. Supported types are `bill_printer`, `check_printer`, `printer`, `scanner`, and `other`.
The GUI is available explicitly as `bay300da gui`.

Linux users may install `packaging/bay300-device-agent.service` as a systemd user service.
Windows production packaging should use a signed PyInstaller executable plus Scheduled Task or
Windows Service; macOS should use a signed/notarized app plus LaunchAgent. The pip installation is
the portable Grace-pilot distribution.

Rendered Bill PDF/HTML and the idempotency journal remain under `~/.bay300/work`. Reprints are new
audited server tasks. A processing cancellation is cooperative: the agent checks immediately before
rendering and immediately before sending output to the local print subsystem.

Bay300 assigns each task to the physical device selected by its requestor. `bay300da` polls once per
ready local device, and a device can claim only tasks assigned to its synchronized identity. Renaming
a local device preserves that identity; removing and recreating it creates a different destination.
