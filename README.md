# Bay300 Devices Admin (`bay300da`)

`bay300da` is the store-machine program that owns physical printer/scanner configuration.
After authorization its window title is **(Store Name) Devices Admin**. Bay300 receives only
device identity, type, capabilities, status, and task outcomes; printer names, scanner identifiers,
drivers, paths, and other local configuration remain on the store machine.

## Requirements and installation

- Python 3.11 or newer;
- an HTTPS connection to `https://bay300.com`;
- Tk/Tkinter for the graphical program;
- a locally installed printer driver/CUPS queue for current Bill printing.

Store Owner/OP users should normally open **Device Monitor → Install Devices Admin**. Bay300
provides separate Windows, Linux, and macOS bundles and highlights the likely package based on the
browser platform. Each bundle contains only this agent project and platform launchers. The stable
agent-only source tag is `bay300da-grace`; it is separate from the full application recovery tag.

The package launchers are the simplest Grace installation. Repository-authorized maintainers may
instead install from the private agent-only source tag on Windows, macOS, or Linux:

```bash
git clone --depth 1 --branch bay300da-grace git@github.com:yetaai/bay3000.git bay300da-grace
cd bay300da-grace
python -m venv .bay300da-venv
```

Activate and install:

```text
Windows PowerShell: .\.bay300da-venv\Scripts\Activate.ps1
macOS/Linux:        source .bay300da-venv/bin/activate
All platforms:      python -m pip install .
```

On Debian/Ubuntu, install Tk and CUPS first when absent:

```bash
sudo apt install python3-tk cups-client
```

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

Open the graphical program:

```bash
bay300da
```

It supports Add new device, Remove device, Edit/Config device, Block/Unblock, Check device status,
and Poll server now. Polling uses exponential idle backoff from 2 to 60 seconds; Poll server now,
local configuration changes, task activity, and connectivity recovery reset the cycle.

Headless operation is also available:

```bash
bay300da doctor
bay300da once
bay300da run
```

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
