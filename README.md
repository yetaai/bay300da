# Bay300 Print Agent

The print agent is a small headless Python program installed on a trusted store machine.
It polls Bay300 for versioned Bill print jobs, verifies each SHA-256 checksum, creates a
self-contained printable HTML file, submits it to the local print command, and retains a
local SQLite journal plus Printed/Failed folders.

The Bay300 server retains the immutable serialized Bill and job metadata. It does not
retain rendered HTML/PDF. Each requested reprint receives a new job and copy number.

## Store-machine requirements

- Python 3.11 or newer;
- an HTTPS connection to `https://bay300.com`;
- CUPS and a configured printer on Linux (`lpstat -p`, then `lp file.html`);
- a dedicated non-administrator operating-system account is recommended.

## Install and enroll

From a checkout of the `bay300grace` tag:

```bash
git clone https://github.com/yetaai/bay3000.git
cd bay3000
git checkout bay300grace
python3 -m venv ~/.local/share/bay300-print-agent/venv
~/.local/share/bay300-print-agent/venv/bin/pip install ./apps/print-agent
```

In Bay300, open Owner Workspace, show the Store dashboard, open **Bill Printing
Monitor**, and choose **Generate enrollment code**. Within 15 minutes run:

```bash
~/.local/share/bay300-print-agent/venv/bin/bay300-print-agent enroll \
  --url https://bay300.com --printer YOUR_CUPS_PRINTER
~/.local/share/bay300-print-agent/venv/bin/bay300-print-agent doctor
~/.local/share/bay300-print-agent/venv/bin/bay300-print-agent once
```

The one-time code is prompted without terminal echo. Configuration containing the device
token is stored with mode `0600` at
`~/.config/bay300-print-agent/config.json`. Revoke the agent in Bay300 immediately if
that file or machine is lost.

## Run continuously with systemd

Install the supplied user unit, then run:

```bash
mkdir -p ~/.config/systemd/user
cp apps/print-agent/packaging/bay300-print-agent.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now bay300-print-agent.service
systemctl --user status bay300-print-agent.service
```

Enable user lingering if the agent must run while nobody is logged in:

```bash
sudo loginctl enable-linger "$USER"
```

Files are under `~/.local/share/bay300-print-agent/{Pending,Printed,Failed}`. The local
SQLite journal prevents a successfully spooled job from being printed twice after a
normal restart. A power loss exactly between printer acceptance and acknowledgement is
inherently ambiguous; inspect the physical output and request an audited reprint rather
than resetting the old job.
