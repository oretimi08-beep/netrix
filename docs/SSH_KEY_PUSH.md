# NETRIX Live Push — SSH Key Support

## Authentication methods

| Method | Fields | When to use |
|--------|--------|-------------|
| Password | Username + Password (+ Enable) | Simple lab devices with AAA password |
| SSH key (file) | **Key path** on NETRIX *server* filesystem | Keys stored under `~/.ssh/` on the host running Flask |
| SSH key (PEM paste) | Advanced → paste PEM private key | Demo laptops; key not stored on server disk |
| Mixed | Key + optional password | Devices that accept key then still need enable secret |

**Priority:** if `private_key_path` or `private_key_data` is set, Paramiko uses the key. Password is optional alongside a key.

## Supported key types

- **Ed25519** (recommended)
- **ECDSA**
- **RSA**
- **DSA** (legacy)

OpenSSH and PEM private key formats are loaded via Paramiko.

## Generate a lab key pair

```bash
ssh-keygen -t ed25519 -f ~/.ssh/netrix_lab -C "netrix-lab"
# Private: ~/.ssh/netrix_lab
# Public:  ~/.ssh/netrix_lab.pub
```

Protect the private key (`chmod 600`). Prefer a passphrase for non-demo keys.

## Install the public key on a device

**Cisco IOS (example – platform specific):** use `ip ssh pubkey-chain` / AAA methods supported by your IOS version, or terminate SSH on a jump host.

**Linux-based NOS / server:**

```bash
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... netrix-lab" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

## NETRIX UI steps

1. Generate a project and open **Live Push**.
2. **Seed from project devices** (or add rows).
3. Set **Host / IP** to the management address (not `127.0.0.1` for real SSH).
4. Either:
   - **Key path:** e.g. `/home/you/.ssh/netrix_lab` (must be readable by the user running NETRIX), and **Key pass** if encrypted; or
   - **Advanced:** paste the PEM private key block.
5. Leave **Dry-run** enabled first → **Run push** (loads key, probes TCP, does not write config).
6. Uncheck dry-run only when ready to apply; confirm the dialog.

## API payload example

`POST /projects/<id>/push`

```json
{
  "dry_run": true,
  "targets": [
    {
      "name": "R-Edge",
      "device_type": "router",
      "host": "192.168.10.1",
      "port": 22,
      "username": "netrix",
      "password": "",
      "enable_secret": "cisco",
      "private_key_path": "/home/netops/.ssh/netrix_lab",
      "private_key_passphrase": "",
      "private_key_data": ""
    }
  ]
}
```

Use `private_key_data` with a full PEM string instead of `private_key_path` when the key is not on disk.

## Security notes

- Private keys pasted in the browser are sent to the NETRIX server in the push request body — use HTTPS in any non-local deployment.
- Key **paths** are read only from the server filesystem (not from the user’s laptop unless that is the same machine).
- Prefer dry-run before apply. NETRIX blocks obviously destructive lines (`reload`, `write erase`, …) but is not a substitute for change control.
- Do not commit private keys into the NETRIX git repository.

## Troubleshooting

| Symptom | Likely cause |
|---------|----------------|
| `Key file not found on server` | Path is on your laptop but NETRIX runs elsewhere — use PEM paste or copy the key to the server |
| `Could not load key file` | Wrong passphrase, unsupported format, or truncated PEM |
| `SSH push failed: Authentication failed` | Public key not installed on device, wrong username, or password-only device |
| Dry-run says host not reachable | Firewall / wrong management VRF / IP; config is still prepared |
