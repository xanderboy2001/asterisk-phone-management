# asterisk-phone-management

A Python CLI, web UI, and REST API for managing Asterisk PBX phones: register, replace, and remove Cisco SIP phones, search configs, reset voicemail PINs, edit caller IDs, toggle call forwarding, and reboot phones.

It edits the standard Asterisk configuration files (`sip.conf`, `extensions.conf`, `voicemail.conf`) and the Cisco `.cnf.xml` provisioning files served over TFTP. Every change is backed up first and rolled back if anything fails.

> [!WARNING]
> Login is optional and off by default. Without it, anyone who can reach the port can reboot phones, reset voicemail PINs, and change call routing. Always set `ASTERISK_CLI_ALLOWED_NETWORKS`, and set `ASTERISK_CLI_WEB_AUTH=basic` if more than your team can reach the server. Basic auth over plain HTTP sends the password unencrypted, so use HTTPS if the login matters.

## Features

| Feature                                        | CLI | Web UI | API |
| ---------------------------------------------- | :-: | :----: | :-: |
| Search by extension, MAC address, or caller ID | ✅  |   ✅   | ✅  |
| Register a new phone (with optional voicemail) | ✅  |        |     |
| Replace a phone (swap MAC address)             | ✅  |        |     |
| Remove a phone                                 | ✅  |        |     |
| Reset a voicemail PIN                          | ✅  |   ✅   |     |
| Edit a caller ID                               | ✅  |   ✅   |     |
| Toggle call forwarding                         | ✅  |   ✅   |     |
| Reboot a phone over SSH                        | ✅  |   ✅   |     |
| View active calls                              | ✅  |        |     |
| Edit config files in `$EDITOR`                 | ✅  |        |     |
| Reload Asterisk modules                        | ✅  |        |     |

## Requirements

- Python 3.11 or later
- [uv](https://docs.astral.sh/uv/)
- Asterisk using `chan_sip` (`sip.conf`), with the `asterisk` CLI available on the host
- Cisco SIP phones provisioned over TFTP with `SEP<MAC>.cnf.xml` files
- A provisioning template named `SEP0000000.cnf.xml` in the TFTP directory, containing the placeholders `--EXTENNUMBER--` and `--SEPMAC--`
- Write access to the Asterisk config directory and the TFTP directory
- `ssh` on the host, for rebooting phones

## Installation

```bash
git clone https://github.com/xanderboy2001/asterisk-phone-management.git
cd asterisk-phone-management
uv sync --no-dev
```

## Configuration

Settings are read from environment variables. A `.env` file in the working directory is also loaded.

| Variable                            | Default                                               | Purpose                                                    |
| ----------------------------------- | ----------------------------------------------------- | ---------------------------------------------------------- |
| `ASTERISK_CLI_ETC`                  | `/etc/asterisk`                                       | Asterisk configuration directory                           |
| `ASTERISK_CLI_TFTPBOOT`             | `/var/lib/tftpboot`                                   | TFTP directory with `.cnf.xml` files                       |
| `ASTERISK_CLI_PHONE_SSH_USER`       | _Required for reboot_                                 | SSH username for rebooting phones                          |
| `ASTERISK_CLI_PHONE_SSH_PASS`       | _Required for reboot_                                 | SSH password for rebooting phones                          |
| `ASTERISK_CLI_CALL_FORWARDING_FILE` | `/etc/asterisk-phone-management/call_forwarding.toml` | Call forwarding roster                                     |
| `ASTERISK_CLI_ALLOWED_NETWORKS`     | _None (allow all)_                                    | Comma-separated networks allowed to use the web UI and API |
| `ASTERISK_CLI_WEB_AUTH`             | `none`                                                | `none` or `basic` (one shared login)                       |
| `ASTERISK_CLI_WEB_USER`             | _Required for basic_                                  | Shared login username                                      |
| `ASTERISK_CLI_WEB_PASSWORD`         | _Required for basic_                                  | Shared login password                                      |

> [!IMPORTANT]
> Phone reboots need ASTERISK_CLI_PHONE_SSH_USER and ASTERISK_CLI_PHONE_SSH_PASS.
> There are no defaults. Use credentials you've changed from the phones' factory values.

### Call forwarding roster

Users who can have call forwarding toggled are listed in a TOML file. Copy the example and edit it:

```bash
sudo mkdir -p /etc/asterisk-phone-management
sudo cp call_forwarding.example.toml /etc/asterisk-phone-management/call_forwarding.toml
```

```toml
[[users]]
name = "Jane Example"
extension = "1001"
forwarding_number = "15555550100"
```

If the file is missing, the call forwarding menu reports that no users are configured.

## Usage

### CLI

```bash
uv run menu          # interactive menu
uv run menu -v       # with debug logging
```

### Web UI and API

```bash
uv run fastapi run --host 127.0.0.1 --port 8000
```

- Web UI: `http://127.0.0.1:8000/`
- API docs: `http://127.0.0.1:8000/docs`

API endpoints:

| Method | Path                                       | Description                    |
| ------ | ------------------------------------------ | ------------------------------ |
| `GET`  | `/api/v1/search/extension/{extension}`     | Find a 4-digit extension       |
| `GET`  | `/api/v1/search/mac_address/{mac_address}` | Find a MAC address             |
| `GET`  | `/api/v1/search/caller_id/{caller_id}`     | Find a caller ID in `sip.conf` |

Changes made from the web UI are written to the config files but don't reload Asterisk. Run **Reload Asterisk** from the CLI to apply them.

## Backups

Before every change, each affected config file is copied to a `backup/` folder next to it (for example, `/etc/asterisk/backup/`). If the change fails, the originals are restored automatically. Old backups aren't removed, so prune the folder periodically.

## Development

```bash
uv sync
uv run pre-commit install --install-hooks

uv run ruff check .
uv run ruff format .
uv run ty check
uv run pytest
```

Tests run against temporary copies of the config files and never touch a real Asterisk installation.

Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/).

## Security

Please report vulnerabilities privately through GitHub's **Report a vulnerability** button on the Security tab, not in a public issue.

## License

Copyright (C) 2026 Alexander Christian

This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. See [LICENSE](LICENSE) for the full text.
