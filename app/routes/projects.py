from flask import Blueprint, request, jsonify, send_file, current_app
from flask_login import current_user
from app import db
from app.models import Project, Department, GeneratedData
from app.services.network_engine import generate_network_data, generate_packet_tracer_lab
from app.services.device_push import push_configs
from app.services.reports import (
    generate_pdf_report, generate_excel_report, generate_word_report,
    generate_csv_vlsm, generate_csv_ipv4
)
from app.utils.rbac import (
    login_required_api, permission_required, can_access_project, can_modify_project, has_permission
)
import io

projects_bp = Blueprint('projects', __name__)


def _get_project(project_id):
    p = Project.query.get(project_id)
    if not p or not can_access_project(p):
        return None
    return p


@projects_bp.route('/', methods=['GET'])
@permission_required('project.list')
def list_projects():
    if has_permission('project.view_all'):
        projects = Project.query.order_by(Project.updated_at.desc()).all()
    else:
        projects = Project.query.filter_by(user_id=current_user.id).order_by(Project.updated_at.desc()).all()
    result = []
    for p in projects:
        d = p.to_dict()
        d['owner_name'] = p.owner.full_name or p.owner.username if p.owner else None
        d['can_edit'] = can_modify_project(p)
        result.append(d)
    return jsonify(result)


@projects_bp.route('/<int:project_id>', methods=['GET'])
@permission_required('project.view')
def get_project(project_id):
    p = _get_project(project_id)
    if not p:
        return jsonify({'error': 'Project not found or access denied'}), 404
    data = p.to_dict(include_generated=True)
    data['owner_name'] = p.owner.full_name or p.owner.username if p.owner else None
    data['can_edit'] = can_modify_project(p)
    return jsonify(data)


@projects_bp.route('/', methods=['POST'])
@permission_required('project.create')
def create_project():
    data = request.get_json() or {}
    company = (data.get('company_name') or '').strip()
    name = (data.get('project_name') or '').strip()
    base = (data.get('base_network') or '192.168.10.0/24').strip()
    routing = data.get('routing_protocol') or 'OSPF'
    router = data.get('router_name') or 'R1'
    switch = data.get('switch_name') or 'S1'
    depts = data.get('departments') or []
    routers = data.get('routers') or (data.get('devices') or {}).get('routers') or []
    switches = data.get('switches') or (data.get('devices') or {}).get('switches') or []
    internet = data.get('internet') or (data.get('devices') or {}).get('internet') or {'enabled': True, 'name': 'Internet', 'wan_ip': 'Auto'}
    design = data.get('design') or (data.get('devices') or {}).get('design') or {}
    if routers:
        router = routers[0].get('name') or router
    if switches:
        switch = switches[0].get('name') or switch

    if not company or not name:
        return jsonify({'error': 'Company and project name required'}), 400

    project = Project(
        user_id=current_user.id,
        company_name=company,
        project_name=name,
        base_network=base,
        routing_protocol=routing,
        router_name=router,
        switch_name=switch,
        status='Draft',
    )
    design = data.get('design') or (data.get('devices') or {}).get('design') or {}
    project.set_devices({
        'routers': routers or [{'name': router, 'role': 'edge', 'model': 'Cisco ISR'}],
        'switches': switches or [{'name': switch, 'role': 'access', 'model': 'Cisco Catalyst'}],
        'internet': internet,
        'design': design,
    })
    db.session.add(project)
    db.session.flush()

    for d in depts:
        try:
            hosts = int(d.get('hosts', 20))
        except (TypeError, ValueError):
            hosts = 20
        try:
            vlan_id = int(d.get('vlan_id') or d.get('vlanId') or 10)
        except (TypeError, ValueError):
            vlan_id = 10
        dept = Department(
            project_id=project.id,
            name=(d.get('name') or 'Dept').strip() or 'Dept',
            hosts=max(1, hosts),
            vlan_id=max(1, vlan_id),
            location=d.get('location') or 'HQ',
            gateway=d.get('gateway') or 'Auto',
        )
        db.session.add(dept)

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Database error while saving project: {e}'}), 500
    return jsonify(project.to_dict()), 201


@projects_bp.route('/<int:project_id>', methods=['PUT'])
@permission_required('project.edit')
def update_project(project_id):
    p = _get_project(project_id)
    if not p:
        return jsonify({'error': 'Not found or access denied'}), 404
    if not can_modify_project(p):
        return jsonify({'error': 'Read-only access (viewer role)'}), 403

    data = request.get_json() or {}
    for field in ['company_name', 'project_name', 'base_network', 'routing_protocol',
                  'router_name', 'switch_name', 'status']:
        if field in data:
            setattr(p, field, data[field])
    if any(k in data for k in ('routers', 'switches', 'internet')):
        devices = p.get_devices()
        if 'routers' in data:
            devices['routers'] = data['routers'] or devices['routers']
        if 'switches' in data:
            devices['switches'] = data['switches'] or devices['switches']
        if 'internet' in data:
            devices['internet'] = data['internet'] or devices['internet']
        p.set_devices(devices)
    if 'departments' in data:
        Department.query.filter_by(project_id=p.id).delete()
        for d in data['departments']:
            dept = Department(
                project_id=p.id,
                name=d.get('name', 'Dept'),
                hosts=int(d.get('hosts', 20)),
                vlan_id=int(d.get('vlan_id', 10)),
                location=d.get('location', 'HQ'),
                gateway=d.get('gateway', 'Auto'),
            )
            db.session.add(dept)
    db.session.commit()
    return jsonify(p.to_dict())


@projects_bp.route('/<int:project_id>', methods=['DELETE'])
@permission_required('project.delete')
def delete_project(project_id):
    p = _get_project(project_id)
    if not p:
        return jsonify({'error': 'Not found or access denied'}), 404
    if not can_modify_project(p):
        return jsonify({'error': 'Read-only access (viewer role)'}), 403
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})


@projects_bp.route('/<int:project_id>/generate', methods=['POST'])
@permission_required('project.generate')
def generate(project_id):
    p = _get_project(project_id)
    if not p:
        return jsonify({'error': 'Not found or access denied'}), 404
    if not can_modify_project(p):
        return jsonify({'error': 'Read-only access (viewer role)'}), 403

    depts = [d.to_dict() for d in p.departments]
    if not depts:
        return jsonify({'error': 'Add at least one department before generating'}), 400

    try:
        result = generate_network_data(
            p.base_network, depts, p.routing_protocol or 'OSPF',
            p.router_name or 'R1', p.switch_name or 'S1',
            devices=p.get_devices(),
        )
    except Exception as e:
        return jsonify({'error': f'Network generation failed: {e}'}), 500

    try:
        if p.generated:
            gen = p.generated
        else:
            gen = GeneratedData(project_id=p.id)
            db.session.add(gen)

        gen.set_vlsm(result.get('vlsm') or [])
        gen.set_ipv4(result.get('ipv4') or [])
        ipv6_rows = result.get('ipv6') or []
        design_meta = result.get('design') or {}
        # Prefer design from generation; fall back to project device options
        if not design_meta:
            design_meta = (p.get_devices() or {}).get('design') or {}
        if hasattr(gen, 'set_ipv6'):
            gen.set_ipv6(ipv6_rows)
        else:
            try:
                gen.ipv6_json = __import__('json').dumps(ipv6_rows)
            except Exception:
                pass
        if hasattr(gen, 'set_design'):
            gen.set_design(design_meta)
        else:
            try:
                gen.design_json = __import__('json').dumps(design_meta)
            except Exception:
                pass
        gen.set_vlan(result.get('vlan') or [])
        gen.router_config = result.get('router_config') or ''
        gen.switch_config = result.get('switch_config') or ''
        gen.topology_html = result.get('topology') or ''
        gen.set_validation(result.get('validation') or [])
        gen.network_summary = result.get('network_summary') or ''
        p.status = 'Completed'
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to save generated data: {e}'}), 500

    return jsonify({'success': True, 'project': p.to_dict(include_generated=True)})


@projects_bp.route('/<int:project_id>/download/<doc_type>', methods=['GET'])
@permission_required('project.download')
def download(project_id, doc_type):
    p = _get_project(project_id)
    if not p or not p.generated:
        return jsonify({'error': 'Project or generated data not found'}), 404

    proj_dict = p.to_dict()
    gen_dict = p.generated.to_dict() if p.generated else {}
    # Enrich design / ipv6 for reports (older projects or partial saves)
    devices = p.get_devices() if hasattr(p, 'get_devices') else {}
    design = gen_dict.get('design') or devices.get('design') or {}
    gen_dict['design'] = design
    if not gen_dict.get('ipv6'):
        # Rebuild IPv6 plan when design requests it but rows were not stored
        ip_ver = (design.get('ip_version') or 'ipv4').lower()
        if ip_ver in ('ipv6', 'dual'):
            try:
                from app.services.network_engine import ipv6_ula_subnet
                depts = [d.to_dict() for d in p.departments]
                rows = []
                for i, d in enumerate(depts):
                    sub = ipv6_ula_subnet(0x100 + i)
                    rows.append({
                        'dept': d.get('name') or f'Dept{i+1}',
                        'vlan_id': d.get('vlan_id') or (10 + i * 10),
                        'network': sub['network'],
                        'gateway': sub['gateway'],
                        'range': sub['range'],
                        'prefix': sub['prefix'],
                    })
                if (devices.get('internet') or {}).get('enabled', True):
                    wan6 = ipv6_ula_subnet(0x200)
                    rows.append({
                        'dept': 'WAN / Internet', 'vlan_id': 0,
                        'network': wan6['network'], 'gateway': wan6['gateway'],
                        'range': wan6['range'], 'prefix': wan6['prefix'],
                    })
                gen_dict['ipv6'] = rows
            except Exception:
                pass
    fname_base = f"{p.project_name.replace(' ', '_')}_{p.id}"

    if doc_type == 'pdf':
        data = generate_pdf_report(proj_dict, gen_dict)
        return send_file(io.BytesIO(data), mimetype='application/pdf',
                         as_attachment=True, download_name=f'{fname_base}_report.pdf')
    if doc_type == 'excel':
        data = generate_excel_report(proj_dict, gen_dict)
        return send_file(io.BytesIO(data),
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=f'{fname_base}_plan.xlsx')
    if doc_type == 'word':
        data = generate_word_report(proj_dict, gen_dict)
        return send_file(io.BytesIO(data),
                         mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                         as_attachment=True, download_name=f'{fname_base}_report.docx')
    if doc_type == 'vlsm-csv':
        csv_data = generate_csv_vlsm(gen_dict.get('vlsm', []))
        return send_file(io.BytesIO(csv_data.encode()), mimetype='text/csv',
                         as_attachment=True, download_name=f'{fname_base}_vlsm.csv')
    if doc_type == 'ipv4-csv':
        csv_data = generate_csv_ipv4(gen_dict.get('ipv4', []))
        return send_file(io.BytesIO(csv_data.encode()), mimetype='text/csv',
                         as_attachment=True, download_name=f'{fname_base}_ipv4.csv')
    if doc_type == 'router':
        return send_file(io.BytesIO(gen_dict.get('router_config', '').encode()), mimetype='text/plain',
                         as_attachment=True, download_name=f'{fname_base}_router.txt')
    if doc_type == 'switch':
        return send_file(io.BytesIO(gen_dict.get('switch_config', '').encode()), mimetype='text/plain',
                         as_attachment=True, download_name=f'{fname_base}_switch.txt')
    if doc_type == 'vlan-txt':
        lines = ['VLAN Allocation Report', '=' * 30, '']
        for v in gen_dict.get('vlan', []):
            lines.append(f"VLAN {v.get('id')}: {v.get('dept')} -> {v.get('network')}")
        return send_file(io.BytesIO('\n'.join(lines).encode()), mimetype='text/plain',
                         as_attachment=True, download_name=f'{fname_base}_vlan.txt')
    if doc_type in ('packet-tracer', 'pt-lab', 'pkt-guide'):
        lab = generate_packet_tracer_lab(proj_dict, gen_dict)
        return send_file(
            io.BytesIO(lab.encode('utf-8')),
            mimetype='text/plain',
            as_attachment=True,
            download_name=f'{fname_base}_PacketTracer_Lab.txt',
        )

    return jsonify({'error': 'Unknown document type'}), 400



@projects_bp.route('/<int:project_id>/email-report', methods=['POST'])
@permission_required('project.download')
def email_report(project_id):
    """Generate PDF and email it to one or more recipients (user or client)."""
    p = Project.query.get(project_id)
    if not p or not can_access_project(p):
        return jsonify({'error': 'Not found or access denied'}), 404
    if not p.generated:
        return jsonify({'error': 'Generate the network plan before emailing a report'}), 400

    data = request.get_json(silent=True) or {}
    to_email = (data.get('to') or data.get('email') or data.get('to_email') or '').strip()
    cc = (data.get('cc') or '').strip()
    message = (data.get('message') or '').strip()
    if not to_email:
        return jsonify({'error': 'Recipient email (to) is required'}), 400

    recipients = [to_email]
    if cc:
        recipients.extend([x.strip() for x in cc.split(',') if x.strip()])

    proj_dict = p.to_dict()
    gen_dict = p.generated.to_dict() if p.generated else {}
    # Enrich design / ipv6 (same as download)
    devices = p.get_devices() if hasattr(p, 'get_devices') else {}
    design = gen_dict.get('design') or devices.get('design') or {}
    gen_dict['design'] = design
    if not gen_dict.get('ipv6'):
        ip_ver = (design.get('ip_version') or 'ipv4').lower()
        if ip_ver in ('ipv6', 'dual'):
            try:
                from app.services.network_engine import ipv6_ula_subnet
                depts = [d.to_dict() for d in p.departments]
                rows = []
                for i, d in enumerate(depts):
                    sub = ipv6_ula_subnet(0x100 + i)
                    rows.append({
                        'dept': d.get('name') or f'Dept{i+1}',
                        'vlan_id': d.get('vlan_id') or (10 + i * 10),
                        'network': sub['network'],
                        'gateway': sub['gateway'],
                        'range': sub['range'],
                        'prefix': sub['prefix'],
                    })
                if (devices.get('internet') or {}).get('enabled', True):
                    wan6 = ipv6_ula_subnet(0x200)
                    rows.append({
                        'dept': 'WAN / Internet', 'vlan_id': 0,
                        'network': wan6['network'], 'gateway': wan6['gateway'],
                        'range': wan6['range'], 'prefix': wan6['prefix'],
                    })
                gen_dict['ipv6'] = rows
            except Exception:
                pass

    try:
        pdf_bytes = generate_pdf_report(proj_dict, gen_dict)
    except Exception as e:
        return jsonify({'error': f'PDF generation failed: {e}'}), 500

    from app.services.email_service import send_pdf_report_email, is_mail_configured
    if not is_mail_configured(current_app):
        return jsonify({
            'error': 'Email is not configured on this server. Set MAIL_SERVER, MAIL_USERNAME, '
                     'MAIL_PASSWORD and MAIL_DEFAULT_SENDER environment variables.',
            'configured': False,
        }), 503

    from flask_login import current_user
    sender_name = None
    reply_to = None
    try:
        sender_name = current_user.full_name or current_user.username
        reply_to = current_user.email
    except Exception:
        pass

    result = send_pdf_report_email(
        to_addresses=recipients,
        project_name=p.project_name or 'Network Project',
        company_name=p.company_name or '',
        pdf_bytes=pdf_bytes,
        sender_name=sender_name,
        message=message or None,
        app=current_app,
        reply_to=reply_to,
    )
    if not result.get('ok'):
        return jsonify({'error': result.get('error') or 'Send failed', 'configured': True}), 502
    return jsonify({
        'success': True,
        'message': f"Report emailed to {', '.join(result.get('recipients') or recipients)}",
        'recipients': result.get('recipients'),
    })


@projects_bp.route('/<int:project_id>/push', methods=['POST'])
@permission_required('project.generate')
def push_to_devices(project_id):
    """Live (or dry-run) SSH configuration push to routers/switches."""
    p = Project.query.get(project_id)
    if not p or not can_access_project(p):
        return jsonify({'error': 'Project not found'}), 404
    if not can_modify_project(p):
        return jsonify({'error': 'Forbidden'}), 403
    if not p.generated:
        return jsonify({'error': 'Generate the project before pushing configurations'}), 400

    data = request.get_json() or {}
    targets = data.get('targets') or []
    dry_run = data.get('dry_run', True)
    if isinstance(dry_run, str):
        dry_run = dry_run.lower() not in ('0', 'false', 'no')

    if not targets:
        return jsonify({'error': 'No push targets provided'}), 400
    if len(targets) > 20:
        return jsonify({'error': 'Maximum 20 devices per push'}), 400

    gen = p.generated.to_dict() if hasattr(p.generated, 'to_dict') else {}
    # generated may be object with attributes
    router_cfg = gen.get('router_config') or getattr(p.generated, 'router_config', '') or ''
    switch_cfg = gen.get('switch_config') or getattr(p.generated, 'switch_config', '') or ''

    try:
        result = push_configs(
            targets=targets,
            router_config=router_cfg,
            switch_config=switch_cfg,
            dry_run=bool(dry_run),
            allow_simulate=True,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'Push failed: {e}'}), 500

