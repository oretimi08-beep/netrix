"""
Live device configuration push for NETRIX.

Pushes generated Cisco-style configuration text to network devices over SSH.
Authentication options:
  - Password
  - SSH private key (file path or PEM content)
  - Optional key passphrase
  - Optional enable secret for privileged mode

Supports dry-run (default) and apply mode. Uses Paramiko when available;
falls back to simulated push for lab hosts (127.0.0.1, lab.local, etc.).

SAFETY: Production use requires operator confirmation, correct credentials,
and out-of-band recovery paths. NETRIX does not replace change-control process.
"""
from __future__ import annotations

import io
import os
import re
import socket
import time
from typing import List, Optional, Dict, Any, Tuple


class PushTarget:
    def __init__(
        self,
        name,
        host,
        device_type='router',
        port=22,
        username='admin',
        password='',
        enable_secret='',
        config_text='',
        private_key_path='',
        private_key_data='',
        private_key_passphrase='',
        allow_agent=False,
    ):
        self.name = name
        self.host = host
        self.device_type = device_type
        self.port = port
        self.username = username
        self.password = password
        self.enable_secret = enable_secret
        self.config_text = config_text
        self.private_key_path = (private_key_path or '').strip()
        self.private_key_data = (private_key_data or '').strip()
        self.private_key_passphrase = private_key_passphrase or ''
        self.allow_agent = bool(allow_agent)


class PushResult:
    def __init__(self, name, host, success, dry_run, mode, message,
                 lines_sent=0, elapsed_ms=0, transcript=None, auth_method=''):
        self.name = name
        self.host = host
        self.success = success
        self.dry_run = dry_run
        self.mode = mode
        self.message = message
        self.lines_sent = lines_sent
        self.elapsed_ms = elapsed_ms
        self.transcript = transcript or []
        self.auth_method = auth_method

    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'host': self.host,
            'success': self.success,
            'dry_run': self.dry_run,
            'mode': self.mode,
            'message': self.message,
            'lines_sent': self.lines_sent,
            'elapsed_ms': self.elapsed_ms,
            'transcript': self.transcript,
            'auth_method': self.auth_method,
        }


def _strip_dangerous_lines(config_text: str) -> List[str]:
    """Return executable config lines, skipping comments and risky reload ops."""
    blocked = re.compile(
        r'^\s*(reload|write\s+erase|erase\s+startup|format\s+|delete\s+flash:)',
        re.I,
    )
    lines = []
    for raw in (config_text or '').splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith('!') or line.lstrip().startswith('#'):
            continue
        if blocked.search(line):
            continue
        lines.append(line)
    return lines


def _load_private_key(target: PushTarget):
    """
    Load a Paramiko key object from path or PEM text.
    Supports RSA, ECDSA, Ed25519, and legacy DSA.
    Returns (pkey, auth_label) or (None, reason).
    """
    try:
        import paramiko
    except ImportError:
        return None, 'Paramiko not installed'

    passphrase = target.private_key_passphrase or None
    key_classes = []
    for name in ('Ed25519Key', 'ECDSAKey', 'RSAKey', 'DSSKey'):
        cls = getattr(paramiko, name, None)
        if cls is not None:
            key_classes.append(cls)
    if not key_classes:
        return None, 'No Paramiko key classes available'

    errors = []

    def try_load(factory):
        for cls in key_classes:
            try:
                return cls.from_private_key(**factory), cls.__name__.replace('Key', '')
            except Exception as e:
                errors.append(f'{cls.__name__}: {e}')
        return None, None

    # 1) Explicit PEM pasted in UI
    if target.private_key_data:
        pem = target.private_key_data
        if 'BEGIN' not in pem:
            return None, 'private_key_data does not look like a PEM private key'
        result, label = try_load(dict(file_obj=io.StringIO(pem), password=passphrase))
        if result:
            return result, f'key-data/{label}'
        return None, 'Could not parse private_key_data (' + '; '.join(errors[-4:]) + ')'

    # 2) Path on the NETRIX server filesystem
    if target.private_key_path:
        path = os.path.expanduser(target.private_key_path)
        if not os.path.isfile(path):
            return None, f'Key file not found on server: {path}'
        # Refuse world-readable keys as a soft warning path still attempts load
        result, label = try_load(dict(filename=path, password=passphrase))
        if result:
            return result, f'key-file/{label}:{path}'
        return None, f'Could not load key file {path} (' + '; '.join(errors[-4:]) + ')'

    return None, 'No private key provided'


def _auth_summary(target: PushTarget) -> str:
    if target.private_key_data:
        return 'ssh-key (PEM pasted)'
    if target.private_key_path:
        return f'ssh-key (file: {target.private_key_path})'
    if target.password:
        return 'password'
    if target.allow_agent:
        return 'ssh-agent'
    return 'none'


def _try_paramiko_push(target: PushTarget, lines: List[str], dry_run: bool) -> PushResult:
    start = time.time()
    transcript: List[str] = []
    auth_method = _auth_summary(target)

    try:
        import paramiko
    except ImportError:
        return PushResult(
            name=target.name, host=target.host, success=False, dry_run=dry_run,
            mode='error',
            message='Paramiko not installed. Run: pip install paramiko',
            elapsed_ms=int((time.time() - start) * 1000),
            auth_method=auth_method,
        )

    pkey = None
    key_label = ''
    if target.private_key_path or target.private_key_data:
        pkey, key_info = _load_private_key(target)
        if pkey is None:
            return PushResult(
                name=target.name, host=target.host, success=False, dry_run=dry_run,
                mode='error',
                message=f'SSH key load failed: {key_info}',
                elapsed_ms=int((time.time() - start) * 1000),
                auth_method=auth_method,
            )
        key_label = key_info
        auth_method = key_info

    if dry_run:
        try:
            sock = socket.create_connection((target.host, target.port), timeout=5)
            sock.close()
            reachable = True
            transcript.append(f'TCP {target.host}:{target.port} reachable')
        except OSError as e:
            reachable = False
            transcript.append(f'TCP probe failed: {e}')

        transcript.append(f'Auth method: {auth_method}')
        if pkey is not None:
            transcript.append(f'Private key loaded OK ({key_label})')
        elif target.password:
            transcript.append('Password authentication will be used on apply')
        else:
            transcript.append('Warning: no password and no key — apply will fail unless ssh-agent works')

        return PushResult(
            name=target.name,
            host=target.host,
            success=True,
            dry_run=True,
            mode='dry-run',
            message=(
                f'Dry-run OK — {len(lines)} line(s) for {target.name}; auth={auth_method}. '
                + ('Host reachable.' if reachable else 'Host not reachable (config still prepared).')
            ),
            lines_sent=0,
            elapsed_ms=int((time.time() - start) * 1000),
            transcript=transcript + [f'Would send: {ln}' for ln in lines[:40]]
            + (['...'] if len(lines) > 40 else []),
            auth_method=auth_method,
        )

    # Apply mode
    if pkey is None and not target.password and not target.allow_agent:
        return PushResult(
            name=target.name, host=target.host, success=False, dry_run=False,
            mode='error',
            message='No SSH credentials: provide a password or private key (path or PEM)',
            elapsed_ms=int((time.time() - start) * 1000),
            auth_method=auth_method,
        )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kwargs = dict(
        hostname=target.host,
        port=target.port,
        username=target.username,
        look_for_keys=False,
        allow_agent=target.allow_agent,
        timeout=15,
        auth_timeout=15,
        banner_timeout=15,
    )
    if pkey is not None:
        connect_kwargs['pkey'] = pkey
        # password may still be needed for some setups; include if provided
        if target.password:
            connect_kwargs['password'] = target.password
    else:
        connect_kwargs['password'] = target.password

    try:
        client.connect(**connect_kwargs)
        transcript.append(f'SSH connected as {target.username} via {auth_method}')
        chan = client.invoke_shell()
        chan.settimeout(10)
        time.sleep(0.6)
        if chan.recv_ready():
            transcript.append(chan.recv(65535).decode(errors='ignore'))

        def send(cmd: str, wait: float = 0.35):
            chan.send(cmd + '\n')
            time.sleep(wait)
            out = ''
            if chan.recv_ready():
                out = chan.recv(65535).decode(errors='ignore')
                transcript.append(out)
            return out

        send('terminal length 0', 0.2)
        send('enable', 0.3)
        if target.enable_secret:
            send(target.enable_secret, 0.3)
        send('configure terminal', 0.4)

        sent = 0
        for ln in lines:
            if ln.strip().lower() in ('end', 'exit'):
                continue
            send(ln, 0.25)
            sent += 1
            if sent >= 400:
                transcript.append('Stopped at 400 lines safety cap')
                break

        send('end', 0.3)
        send('write memory', 0.8)
        client.close()
        return PushResult(
            name=target.name,
            host=target.host,
            success=True,
            dry_run=False,
            mode='applied',
            message=f'Applied {sent} line(s) to {target.name} ({target.host}) via {auth_method}; saved config.',
            lines_sent=sent,
            elapsed_ms=int((time.time() - start) * 1000),
            transcript=transcript[-30:],
            auth_method=auth_method,
        )
    except Exception as e:
        try:
            client.close()
        except Exception:
            pass
        return PushResult(
            name=target.name,
            host=target.host,
            success=False,
            dry_run=False,
            mode='error',
            message=f'SSH push failed ({auth_method}): {e}',
            elapsed_ms=int((time.time() - start) * 1000),
            transcript=transcript,
            auth_method=auth_method,
        )


def _simulated_push(target: PushTarget, lines: List[str], dry_run: bool) -> PushResult:
    auth_method = _auth_summary(target)
    start = time.time()
    mode = 'dry-run' if dry_run else 'simulated'
    return PushResult(
        name=target.name,
        host=target.host or 'simulated',
        success=True,
        dry_run=dry_run,
        mode=mode,
        message=(
            f'{"Dry-run" if dry_run else "Simulated apply"}: {len(lines)} line(s) for {target.name}; '
            f'auth={auth_method}. No live SSH session (demo host).'
        ),
        lines_sent=0 if dry_run else len(lines),
        elapsed_ms=int((time.time() - start) * 1000),
        transcript=[f'[sim] {ln}' for ln in lines[:25]] + (['...'] if len(lines) > 25 else []),
        auth_method=auth_method,
    )


def split_device_configs(router_config: str, switch_config: str) -> Dict[str, str]:
    """Split concatenated multi-device config text into per-hostname blocks."""
    blocks: Dict[str, str] = {}

    def consume(blob: str, default_prefix: str):
        if not blob:
            return
        parts = re.split(r'\n(?=! -{2,}|\nhostname\s+)', blob)
        current_name = None
        current_lines: List[str] = []
        for part in parts:
            hm = re.search(r'hostname\s+(\S+)', part, re.I)
            nm = re.search(r'! -{2,}\s*(?:Router|Switch)\s*:\s*(\S+)', part, re.I)
            name = (hm.group(1) if hm else None) or (nm.group(1) if nm else None)
            if name:
                if current_name and current_lines:
                    blocks[current_name] = '\n'.join(current_lines)
                current_name = name
                current_lines = [part]
            else:
                if current_name:
                    current_lines.append(part)
                else:
                    current_name = f'{default_prefix}-1'
                    current_lines = [part]
        if current_name and current_lines:
            blocks[current_name] = '\n'.join(current_lines)

    consume(router_config or '', 'Router')
    consume(switch_config or '', 'Switch')
    if not blocks:
        if router_config:
            blocks['Router'] = router_config
        if switch_config:
            blocks['Switch'] = switch_config
    return blocks


def push_configs(
    targets: List[Dict[str, Any]],
    router_config: str = '',
    switch_config: str = '',
    dry_run: bool = True,
    allow_simulate: bool = True,
) -> Dict[str, Any]:
    """
    Push configs to targets. Each target may include:
      name, host, port, username, password, enable_secret, device_type,
      private_key_path, private_key_data, private_key_passphrase, allow_agent
    """
    blocks = split_device_configs(router_config, switch_config)
    results: List[PushResult] = []

    for t in targets:
        name = (t.get('name') or '').strip() or 'Device'
        host = (t.get('host') or '').strip()
        device_type = (t.get('device_type') or 'router').lower()
        cfg = blocks.get(name)
        if not cfg:
            for k, v in blocks.items():
                if k.lower() == name.lower():
                    cfg = v
                    break
        if not cfg:
            cfg = router_config if device_type == 'router' else switch_config
        lines = _strip_dangerous_lines(cfg or '')
        target = PushTarget(
            name=name,
            host=host,
            device_type=device_type,
            port=int(t.get('port') or 22),
            username=t.get('username') or 'admin',
            password=t.get('password') or '',
            enable_secret=t.get('enable_secret') or '',
            config_text=cfg or '',
            private_key_path=t.get('private_key_path') or '',
            private_key_data=t.get('private_key_data') or '',
            private_key_passphrase=t.get('private_key_passphrase') or '',
            allow_agent=bool(t.get('allow_agent', False)),
        )
        if not lines:
            results.append(PushResult(
                name=name, host=host, success=False, dry_run=dry_run,
                mode='error', message='No configuration lines available for this device',
                auth_method=_auth_summary(target),
            ))
            continue

        simulate_hosts = {'', '127.0.0.1', 'localhost', 'lab.local', 'simulate', 'demo'}
        if allow_simulate and host.lower() in simulate_hosts:
            results.append(_simulated_push(target, lines, dry_run))
            continue

        results.append(_try_paramiko_push(target, lines, dry_run))

    ok = all(r.success for r in results) if results else False
    return {
        'success': ok,
        'dry_run': dry_run,
        'device_count': len(results),
        'results': [r.to_dict() for r in results],
        'blocks_available': list(blocks.keys()),
        'auth_notes': (
            'SSH key preferred when private_key_path or private_key_data is set; '
            'otherwise password auth is used. Supported key types: Ed25519, ECDSA, RSA, DSA.'
        ),
    }
