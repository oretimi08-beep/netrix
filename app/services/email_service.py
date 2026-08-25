"""
NETRIX email service — send PDF reports via SMTP.
Configure with MAIL_* environment variables (see .env.example).
"""
from __future__ import annotations

import io
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional, Sequence, Union


def _mail_config(app=None) -> dict:
    if app is not None:
        cfg = app.config
        return {
            'server': cfg.get('MAIL_SERVER') or os.environ.get('MAIL_SERVER', ''),
            'port': int(cfg.get('MAIL_PORT') or os.environ.get('MAIL_PORT', 587)),
            'use_tls': str(cfg.get('MAIL_USE_TLS', os.environ.get('MAIL_USE_TLS', 'true'))).lower() in ('1', 'true', 'yes'),
            'use_ssl': str(cfg.get('MAIL_USE_SSL', os.environ.get('MAIL_USE_SSL', 'false'))).lower() in ('1', 'true', 'yes'),
            'username': cfg.get('MAIL_USERNAME') or os.environ.get('MAIL_USERNAME', ''),
            'password': cfg.get('MAIL_PASSWORD') or os.environ.get('MAIL_PASSWORD', ''),
            'default_sender': cfg.get('MAIL_DEFAULT_SENDER')
                or os.environ.get('MAIL_DEFAULT_SENDER')
                or cfg.get('MAIL_USERNAME')
                or os.environ.get('MAIL_USERNAME', ''),
        }
    return {
        'server': os.environ.get('MAIL_SERVER', ''),
        'port': int(os.environ.get('MAIL_PORT', 587)),
        'use_tls': os.environ.get('MAIL_USE_TLS', 'true').lower() in ('1', 'true', 'yes'),
        'use_ssl': os.environ.get('MAIL_USE_SSL', 'false').lower() in ('1', 'true', 'yes'),
        'username': os.environ.get('MAIL_USERNAME', ''),
        'password': os.environ.get('MAIL_PASSWORD', ''),
        'default_sender': os.environ.get('MAIL_DEFAULT_SENDER') or os.environ.get('MAIL_USERNAME', ''),
    }


def is_mail_configured(app=None) -> bool:
    c = _mail_config(app)
    return bool(c['server'] and c['default_sender'])


def send_email(
    to_addresses: Union[str, Sequence[str]],
    subject: str,
    body_text: str,
    body_html: Optional[str] = None,
    attachments: Optional[list] = None,
    app=None,
    reply_to: Optional[str] = None,
) -> dict:
    """
    Send an email with optional attachments.

    attachments: list of dicts:
      { 'filename': str, 'content': bytes, 'mimetype': str }
    """
    cfg = _mail_config(app)
    if not cfg['server'] or not cfg['default_sender']:
        return {
            'ok': False,
            'error': 'Email is not configured. Set MAIL_SERVER, MAIL_USERNAME, '
                     'MAIL_PASSWORD and MAIL_DEFAULT_SENDER in environment variables.',
        }

    if isinstance(to_addresses, str):
        recipients = [a.strip() for a in to_addresses.split(',') if a.strip()]
    else:
        recipients = [a.strip() for a in to_addresses if a and str(a).strip()]

    if not recipients:
        return {'ok': False, 'error': 'At least one recipient email is required.'}

    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = cfg['default_sender']
    msg['To'] = ', '.join(recipients)
    if reply_to:
        msg['Reply-To'] = reply_to

    msg.set_content(body_text or '')
    if body_html:
        msg.add_alternative(body_html, subtype='html')

    for att in attachments or []:
        content = att.get('content') or b''
        if isinstance(content, str):
            content = content.encode('utf-8')
        filename = att.get('filename') or 'attachment.bin'
        mimetype = att.get('mimetype') or 'application/octet-stream'
        maintype, _, subtype = mimetype.partition('/')
        if not subtype:
            maintype, subtype = 'application', 'octet-stream'
        msg.add_attachment(
            content,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    try:
        if cfg['use_ssl']:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg['server'], cfg['port'], context=context, timeout=30) as server:
                if cfg['username']:
                    server.login(cfg['username'], cfg['password'])
                server.send_message(msg)
        else:
            with smtplib.SMTP(cfg['server'], cfg['port'], timeout=30) as server:
                server.ehlo()
                if cfg['use_tls']:
                    context = ssl.create_default_context()
                    server.starttls(context=context)
                    server.ehlo()
                if cfg['username']:
                    server.login(cfg['username'], cfg['password'])
                server.send_message(msg)
        return {'ok': True, 'recipients': recipients}
    except smtplib.SMTPAuthenticationError:
        return {
            'ok': False,
            'error': 'SMTP authentication failed. Check MAIL_USERNAME / MAIL_PASSWORD '
                     '(for Gmail use an App Password, not your normal password).',
        }
    except Exception as e:
        return {'ok': False, 'error': f'Failed to send email: {e}'}


def send_pdf_report_email(
    to_addresses: Union[str, Sequence[str]],
    project_name: str,
    company_name: str,
    pdf_bytes: bytes,
    sender_name: Optional[str] = None,
    message: Optional[str] = None,
    app=None,
    reply_to: Optional[str] = None,
) -> dict:
    """Compose and send a NETRIX PDF planning report."""
    safe_name = ''.join(c if c.isalnum() or c in '-_' else '_' for c in (project_name or 'report'))
    filename = f'NETRIX_{safe_name}_report.pdf'
    subject = f'NETRIX Network Planning Report — {project_name or "Project"}'
    intro = message or (
        f'Please find attached the NETRIX enterprise network planning report '
        f'for project "{project_name}"'
        + (f' ({company_name})' if company_name else '')
        + '.'
    )
    body_text = (
        f'{intro}\n\n'
        f'This document was generated by the NETRIX Enterprise Network Planning Framework.\n'
        f'It includes executive summary, VLSM/IPv4/IPv6 plans, VLAN allocation, topology notes, '
        f'validation results, and device configuration excerpts.\n\n'
        f'— NETRIX\n'
    )
    if sender_name:
        body_text += f'\nSent by: {sender_name}\n'

    body_html = f'''
    <html><body style="font-family: Tahoma, Arial, sans-serif; color:#1a1a1a; line-height:1.5;">
      <p>{intro}</p>
      <p>This document was generated by the <strong>NETRIX Enterprise Network Planning Framework</strong>.
         It includes executive summary, VLSM / IPv4 / IPv6 plans, VLAN allocation, topology notes,
         validation results, and device configuration excerpts.</p>
      <p style="color:#555;">— NETRIX</p>
      {f'<p style="color:#555;">Sent by: {sender_name}</p>' if sender_name else ''}
    </body></html>
    '''

    return send_email(
        to_addresses=to_addresses,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
        attachments=[{
            'filename': filename,
            'content': pdf_bytes,
            'mimetype': 'application/pdf',
        }],
        app=app,
        reply_to=reply_to,
    )
