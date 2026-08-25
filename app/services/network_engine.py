
"""
NETRIX Network Engine
VLSM, IPv4/IPv6 planning, VLAN allocation, multi-device configs,
topology styles, design options (DHCP/NAT/ACL/HSRP/STP…), validation.
"""
from __future__ import annotations

import math
from typing import List, Dict, Any, Optional


CLASS_PRESETS = {
    'A': {'label': 'Class A (Private 10.0.0.0/8)', 'base': '10.0.0.0/16'},
    'B': {'label': 'Class B (Private 172.16.0.0/12)', 'base': '172.16.0.0/16'},
    'C': {'label': 'Class C (Private 192.168.0.0/16)', 'base': '192.168.10.0/24'},
    'custom': {'label': 'Custom CIDR', 'base': '192.168.10.0/24'},
}

TOPOLOGY_TYPES = {
    'hierarchical': 'Three-Tier Hierarchical (Core–Distribution–Access)',
    'star': 'Star (central core)',
    'hub-spoke': 'Hub-and-Spoke WAN',
    'mesh': 'Partial Mesh',
    'campus': 'Campus Collapsed Core',
    'wan': 'Enterprise WAN with Edge',
}


def ip_to_int(ip: str) -> int:
    parts = [int(x) for x in ip.split('.')]
    return (parts[0] << 24) | (parts[1] << 16) | (parts[2] << 8) | parts[3]


def int_to_ip(n: int) -> str:
    return f'{(n >> 24) & 0xff}.{(n >> 16) & 0xff}.{(n >> 8) & 0xff}.{n & 0xff}'


def prefix_to_mask(prefix: int) -> str:
    mask = (0xffffffff << (32 - prefix)) & 0xffffffff
    return int_to_ip(mask)


def prefix_to_wildcard(prefix: int) -> str:
    bits = 32 - prefix
    wildcard = (1 << bits) - 1 if bits > 0 else 0
    return int_to_ip(wildcard)


def required_bits(hosts: int) -> int:
    needed = max(hosts + 2, 2)
    return max(1, math.ceil(math.log2(needed)))


def suggest_base_for_class(network_class: str) -> str:
    return CLASS_PRESETS.get(network_class, CLASS_PRESETS['C'])['base']


def ipv6_ula_subnet(index: int, prefix_len: int = 64) -> Dict[str, str]:
    sid = index & 0xffff
    network = f'fd00:9e71:0:{sid:x}::'
    return {
        'network': f'{network}/{prefix_len}',
        'gateway': f'{network}1',
        'range': f'{network}1 – {network}ffff',
        'prefix': f'/{prefix_len}',
    }


def generate_network_data(
    base_network: str,
    departments: List[Dict[str, Any]],
    routing: str = 'OSPF',
    router_name: str = 'R1',
    switch_name: str = 'S1',
    devices: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not departments:
        raise ValueError('At least one department is required')

    devices = devices or {}
    design = devices.get('design') or {}
    ip_version = (design.get('ip_version') or 'ipv4').lower()
    network_class = (design.get('network_class') or 'C').upper()
    if network_class not in CLASS_PRESETS:
        network_class = 'C'
    topology_type = (design.get('topology_type') or 'hierarchical').lower()
    features = design.get('features') or {}

    if not base_network or not str(base_network).strip():
        base_network = suggest_base_for_class(network_class)
    if ip_version != 'ipv6' and '/' not in str(base_network):
        base_network = str(base_network) + '/24'

    routers = devices.get('routers') or [{'name': router_name or 'R1', 'role': 'edge', 'model': 'Cisco ISR'}]
    switches = devices.get('switches') or [{'name': switch_name or 'S1', 'role': 'access', 'model': 'Cisco Catalyst'}]
    internet = devices.get('internet') or {'enabled': True, 'name': 'Internet', 'wan_ip': 'Auto'}
    if not routers:
        routers = [{'name': router_name or 'R1', 'role': 'edge'}]
    if not switches:
        switches = [{'name': switch_name or 'S1', 'role': 'access'}]

    primary_router = routers[0].get('name') or 'R1'
    sorted_depts = sorted(departments, key=lambda d: int(d.get('hosts', 0) or 0), reverse=True)

    vlsm_data: List[Dict] = []
    vlan_data: List[Dict] = []
    ipv4_data: List[Dict] = []
    ipv6_data: List[Dict] = []
    cursor = 0

    if ip_version in ('ipv4', 'dual'):
        net_part, prefix_str = base_network.split('/')
        base_prefix = int(prefix_str)
        base_int = ip_to_int(net_part)
        cursor = base_int

        for dept in sorted_depts:
            name = dept.get('name') or 'Dept'
            hosts = max(1, int(dept.get('hosts') or 20))
            vlan_id = int(dept.get('vlan_id') or dept.get('vlan') or 0) or (10 + len(vlsm_data) * 10)
            bits = required_bits(hosts)
            prefix = max(base_prefix, 32 - bits)
            block = 1 << (32 - prefix)
            if cursor % block != 0:
                cursor = ((cursor // block) + 1) * block
            network = int_to_ip(cursor)
            mask = prefix_to_mask(prefix)
            gateway = int_to_ip(cursor + 1)
            first = int_to_ip(cursor + 1)
            last = int_to_ip(cursor + block - 2)
            usable = block - 2
            vlsm_data.append({
                'dept': name, 'network': f'{network}/{prefix}', 'prefix': f'/{prefix}',
                'mask': mask, 'range': f'{first} – {last}', 'usable': usable,
                'gateway': gateway, 'vlan_id': vlan_id,
            })
            vlan_data.append({'id': vlan_id, 'dept': name, 'network': f'{network}/{prefix}'})
            ipv4_data.append({
                'device': f'{primary_router} (VLAN {vlan_id})',
                'interface': f'G0/0.{vlan_id}',
                'ip': f'{gateway}/{prefix}',
            })
            cursor += block

        if internet.get('enabled'):
            if cursor % 4 != 0:
                cursor = ((cursor // 4) + 1) * 4
            ipv4_data.append({'device': f'{primary_router} WAN', 'interface': 'G0/1', 'ip': f'{int_to_ip(cursor + 1)}/30'})
            ipv4_data.append({'device': 'ISP / Internet PE', 'interface': 'link', 'ip': f'{int_to_ip(cursor + 2)}/30'})
            cursor += 4

        for i in range(len(routers) - 1):
            if cursor % 4 != 0:
                cursor = ((cursor // 4) + 1) * 4
            a, b = routers[i].get('name'), routers[i + 1].get('name')
            ipv4_data.append({'device': f'{a}–{b} link', 'interface': 'P2P', 'ip': f'{int_to_ip(cursor)}/30'})
            cursor += 4

    if ip_version in ('ipv6', 'dual'):
        for i, dept in enumerate(sorted_depts):
            name = dept.get('name') or 'Dept'
            vlan_id = int(dept.get('vlan_id') or dept.get('vlan') or 0) or (10 + i * 10)
            sub = ipv6_ula_subnet(0x100 + i)
            ipv6_data.append({
                'dept': name, 'vlan_id': vlan_id, 'network': sub['network'],
                'gateway': sub['gateway'], 'range': sub['range'], 'prefix': sub['prefix'],
            })
            if not any(v.get('id') == vlan_id for v in vlan_data):
                vlan_data.append({'id': vlan_id, 'dept': name, 'network': sub['network']})
            ipv4_data.append({
                'device': f'{primary_router} IPv6 VLAN {vlan_id}',
                'interface': f'G0/0.{vlan_id}',
                'ip': sub['gateway'] + sub['prefix'],
            })
        if internet.get('enabled'):
            wan6 = ipv6_ula_subnet(0x200)
            ipv6_data.append({
                'dept': 'WAN / Internet', 'vlan_id': 0, 'network': wan6['network'],
                'gateway': wan6['gateway'], 'range': wan6['range'], 'prefix': wan6['prefix'],
            })

    if ip_version == 'ipv6' and not vlsm_data:
        for row in ipv6_data:
            if row.get('vlan_id'):
                vlsm_data.append({
                    'dept': row['dept'], 'network': row['network'], 'prefix': row['prefix'],
                    'mask': 'N/A (IPv6)', 'range': row['range'], 'usable': '2^64 hosts',
                    'gateway': row['gateway'], 'vlan_id': row['vlan_id'],
                })

    feature_lines = _feature_config_snippets(features, vlsm_data)
    router_config = _build_router_configs(routers, vlsm_data, ipv6_data, routing, internet, features, ip_version, feature_lines)
    switch_config = _build_switch_configs(switches, vlan_data, features)
    topology_html = _build_topology_html(routers, switches, internet, vlsm_data, topology_type, ip_version, network_class)
    validation = _build_validation(vlsm_data, vlan_data, routers, switches, ip_version, features)
    summary = (
        f'IP={ip_version.upper()} · Class={network_class} · Topology={topology_type} · '
        f'Routing={routing} · Depts={len(departments)} · Routers={len(routers)} · Switches={len(switches)}'
    )
    return {
        'vlsm': vlsm_data, 'vlan': vlan_data, 'ipv4': ipv4_data, 'ipv6': ipv6_data,
        'router_config': router_config, 'switch_config': switch_config,
        'topology': topology_html, 'validation': validation, 'network_summary': summary,
        'design': {
            'ip_version': ip_version, 'network_class': network_class,
            'topology_type': topology_type, 'features': features, 'base_network': base_network,
        },
    }


def _feature_config_snippets(features: Dict, vlsm: List[Dict]) -> List[str]:
    lines = []
    if features.get('ntp'):
        lines += ['!', '! NTP', 'ntp server 1.pool.ntp.org', 'ntp server 2.pool.ntp.org']
    if features.get('syslog'):
        lines += ['!', '! Syslog', 'logging host 10.255.255.10', 'logging trap informational']
    if features.get('dns'):
        lines += ['!', '! DNS', 'ip name-server 1.1.1.1', 'ip name-server 8.8.8.8', 'ip domain-lookup']
    if features.get('dhcp') and vlsm:
        lines += ['!', '! DHCP pools']
        for v in vlsm[:8]:
            if 'N/A' in str(v.get('mask')):
                continue
            net = v['network'].split('/')[0]
            mask = v.get('mask') or '255.255.255.0'
            pool = (v['dept'] or 'POOL').replace(' ', '_')[:20]
            lines += [
                f'ip dhcp pool {pool}', f' network {net} {mask}',
                f' default-router {v.get("gateway", net)}', ' dns-server 1.1.1.1 8.8.8.8', ' exit',
            ]
    if features.get('nat'):
        lines += [
            '!', '! NAT overload',
            'interface GigabitEthernet0/1', ' ip nat outside', ' exit',
            'interface GigabitEthernet0/0', ' ip nat inside', ' exit',
            'access-list 1 permit any',
            'ip nat inside source list 1 interface GigabitEthernet0/1 overload',
        ]
    if features.get('acl'):
        lines += [
            '!', '! Baseline ACL',
            'ip access-list extended WAN_IN',
            ' permit tcp any any established',
            ' deny ip 10.0.0.0 0.255.255.255 any',
            ' deny ip 172.16.0.0 0.15.255.255 any',
            ' deny ip 192.168.0.0 0.0.255.255 any',
            ' permit ip any any', ' exit',
        ]
    if features.get('hsrp') and vlsm and 'N/A' not in str(vlsm[0].get('mask')):
        g = vlsm[0].get('gateway', '10.0.0.1')
        vid = vlsm[0].get('vlan_id', 10)
        lines += [
            '!', '! HSRP example',
            f'interface GigabitEthernet0/0.{vid}',
            f' encapsulation dot1Q {vid}',
            f' ip address {g} {vlsm[0].get("mask")}',
            ' standby 1 ip ' + g.rsplit('.', 1)[0] + '.254',
            ' standby 1 priority 110', ' standby 1 preempt', ' exit',
        ]
    if features.get('snmp'):
        lines += ['!', '! SNMP', 'snmp-server community netrix RO', 'snmp-server location NETRIX-LAB']
    if features.get('qos'):
        lines += [
            '!', '! QoS baseline',
            'class-map match-any VOICE', ' match dscp ef', ' exit',
            'policy-map EDGE-QOS', ' class VOICE', '  priority percent 20',
            ' class class-default', '  fair-queue', ' exit',
        ]
    return lines


def _routing_block(routing: str, vlsm: List[Dict], internet: Dict) -> List[str]:
    lines = ['!']
    r = (routing or 'OSPF').upper()
    if r == 'OSPF':
        lines += ['router ospf 1', ' router-id 1.1.1.1']
        for v in vlsm:
            if 'N/A' in str(v.get('mask')):
                continue
            net = v['network'].split('/')[0]
            try:
                pref = int(str(v.get('prefix', '/24')).replace('/', ''))
            except Exception:
                pref = 24
            lines.append(f' network {net} {prefix_to_wildcard(pref)} area 0')
        if internet.get('enabled'):
            lines.append(' default-information originate')
        lines.append(' exit')
    elif r == 'EIGRP':
        lines += ['router eigrp 100', ' no auto-summary']
        for v in vlsm:
            if 'N/A' in str(v.get('mask')):
                continue
            lines.append(f' network {v["network"].split("/")[0]} 0.0.0.255')
        lines.append(' exit')
    elif r == 'RIP':
        lines += ['router rip', ' version 2', ' no auto-summary']
        for v in vlsm:
            if 'N/A' in str(v.get('mask')):
                continue
            lines.append(f' network {v["network"].split("/")[0]}')
        lines.append(' exit')
    else:
        lines += ['ip route 0.0.0.0 0.0.0.0 GigabitEthernet0/1']
    return lines


def _build_router_configs(routers, vlsm, ipv6, routing, internet, features, ip_version, feature_lines):
    chunks = []
    for idx, r in enumerate(routers):
        name = r.get('name') or f'R{idx+1}'
        role = r.get('role') or 'edge'
        lines = [
            f'! --- Router: {name} ({role}) ---', f'hostname {name}', '!',
            'no ip domain-lookup', 'service password-encryption', '!',
            'enable secret cisco', '!',
            'line console 0', ' logging synchronous', ' password cisco', ' login', ' exit',
            'line vty 0 4', ' password cisco', ' login', ' transport input ssh', ' exit',
            '!', 'ip ssh version 2',
        ]
        if ip_version in ('ipv4', 'dual'):
            for v in vlsm:
                if 'N/A' in str(v.get('mask')):
                    continue
                vid = v.get('vlan_id', 10)
                lines += [
                    f'interface GigabitEthernet0/0.{vid}', f' encapsulation dot1Q {vid}',
                    f' ip address {v["gateway"]} {v["mask"]}', ' no shutdown', ' exit',
                ]
        if ip_version in ('ipv6', 'dual'):
            lines.append('ipv6 unicast-routing')
            for v6 in ipv6:
                if not v6.get('vlan_id'):
                    continue
                lines += [
                    f'interface GigabitEthernet0/0.{v6["vlan_id"]}',
                    f' encapsulation dot1Q {v6["vlan_id"]}',
                    f' ipv6 address {v6["gateway"]}/64', ' no shutdown', ' exit',
                ]
        if internet.get('enabled') and role in ('edge', 'wan', 'border'):
            lines += [
                'interface GigabitEthernet0/1', ' description WAN-to-Internet',
                ' ip address 203.0.113.1 255.255.255.252', ' no shutdown', ' exit',
                'ip route 0.0.0.0 0.0.0.0 GigabitEthernet0/1',
            ]
        lines += _routing_block(routing, vlsm, internet)
        if idx == 0:
            lines += feature_lines
        lines += ['!', 'end', '']
        chunks.append('\n'.join(lines))
    return '\n'.join(chunks)


def _build_switch_configs(switches, vlan_data, features):
    chunks = []
    stp = features.get('stp_mode') or 'rapid-pvst'
    for idx, s in enumerate(switches):
        name = s.get('name') or f'S{idx+1}'
        role = s.get('role') or 'access'
        lines = [
            f'! --- Switch: {name} ({role}) ---', f'hostname {name}', '!',
            'enable secret cisco', '!', f'spanning-tree mode {stp}',
            'spanning-tree portfast default' if role == 'access' else '! portfast on access ports only', '!',
        ]
        for v in vlan_data:
            lines += [f'vlan {v["id"]}', f' name {str(v["dept"]).replace(" ", "_")[:20]}', ' exit']
        if role in ('core', 'distribution'):
            lines += [
                'interface range GigabitEthernet1/0/1-4', ' description UPLINK-TRUNK',
                ' switchport mode trunk', ' switchport trunk allowed vlan all', ' no shutdown', ' exit',
            ]
            if features.get('etherchannel'):
                lines += [
                    'interface Port-channel1', ' description EtherChannel-Uplink',
                    ' switchport mode trunk', ' exit',
                    'interface range GigabitEthernet1/0/1-2', ' channel-group 1 mode active', ' exit',
                ]
        else:
            vid = vlan_data[0]['id'] if vlan_data else 10
            lines += [
                'interface range GigabitEthernet1/0/10-24', ' description ACCESS-PORTS',
                ' switchport mode access', f' switchport access vlan {vid}',
                ' spanning-tree portfast', ' no shutdown', ' exit',
                'interface GigabitEthernet1/0/1', ' description UPLINK',
                ' switchport mode trunk', ' no shutdown', ' exit',
            ]
        if features.get('wireless'):
            lines += ['!', f'! WLC note: map SSID NETRIX-CORP to VLAN {vlan_data[0]["id"] if vlan_data else 10}']
        lines += ['!', 'end', '']
        chunks.append('\n'.join(lines))
    return '\n'.join(chunks)


def _build_topology_html(routers, switches, internet, vlsm, topology_type, ip_version, network_class):
    depts = ''.join(
        '<div class="topo-node dept"><i class="fas fa-building"></i><span>%s<br><small>%s</small></span></div>'
        % (v.get('dept'), v.get('network')) for v in vlsm[:8]
    )
    r_html = ''.join(
        '<div class="topo-node router"><i class="fas fa-router"></i><span>%s<br><small>%s</small></span></div>'
        % (r.get('name'), r.get('role')) for r in routers
    )
    s_html = ''.join(
        '<div class="topo-node switch"><i class="fas fa-network-wired"></i><span>%s<br><small>%s</small></span></div>'
        % (s.get('name'), s.get('role')) for s in switches
    )
    inet = ''
    if internet.get('enabled'):
        inet = (
            '<div class="topo-node internet"><i class="fas fa-globe"></i><span>%s</span></div>'
            '<div class="topo-link"></div>' % (internet.get('name') or 'Internet')
        )
    title = TOPOLOGY_TYPES.get(topology_type, topology_type)
    style_css = (
        '.topo-node{background:#0f172a;color:#e2e8f0;border-radius:12px;padding:12px 16px;'
        'min-width:110px;text-align:center;border:1px solid #334155;}'
        '.topo-node i{display:block;font-size:22px;margin-bottom:6px;color:#60a5fa;}'
        '.topo-node.internet i{color:#34d399;}.topo-node.dept{background:#1e293b;}'
        '.topo-link{width:3px;height:18px;background:linear-gradient(#3b82f6,#8b5cf6);margin:0 auto;border-radius:2px;}'
    )
    return (
        '<div class="topology-wrap" style="padding:16px;">'
        '<div class="mb-3"><span class="chip">%s</span> '
        '<span class="chip green">%s</span> '
        '<span class="chip purple">Class %s</span></div>'
        '<div class="topology-canvas" style="display:flex;flex-direction:column;align-items:center;gap:12px;">'
        '%s'
        '<div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">%s</div>'
        '<div class="topo-link"></div>'
        '<div style="display:flex;gap:12px;flex-wrap:wrap;justify-content:center;">%s</div>'
        '<div class="topo-link"></div>'
        '<div style="display:flex;gap:10px;flex-wrap:wrap;justify-content:center;">%s</div>'
        '</div><style>%s</style></div>'
    ) % (title, ip_version.upper(), network_class, inet, r_html, s_html, depts, style_css)


def _build_validation(vlsm, vlan, routers, switches, ip_version, features):
    checks = []
    checks.append({'pass': len(vlsm) > 0, 'msg': 'Address plan entries: %d (%s)' % (len(vlsm), ip_version)})
    vids = [v.get('id') for v in vlan]
    checks.append({'pass': len(vids) == len(set(vids)), 'msg': 'VLAN IDs unique'})
    checks.append({'pass': len(routers) >= 1, 'msg': 'Routers in inventory: %d' % len(routers)})
    checks.append({'pass': len(switches) >= 1, 'msg': 'Switches in inventory: %d' % len(switches)})
    if features.get('dhcp'):
        checks.append({'pass': True, 'msg': 'DHCP pools included in router config'})
    if features.get('nat'):
        checks.append({'pass': True, 'msg': 'NAT overload template included'})
    if features.get('hsrp'):
        checks.append({'pass': True, 'msg': 'HSRP template included'})
    checks.append({'pass': True, 'msg': 'Configs generated for multi-device inventory'})
    return checks


def generate_packet_tracer_lab(project: Dict[str, Any], generated: Dict[str, Any]) -> str:
    name = project.get('project_name') or 'NETRIX Project'
    design = generated.get('design') or {}
    return '\n'.join([
        'NETRIX Packet Tracer Lab Guide — %s' % name,
        '=' * 60,
        'IP version: %s' % design.get('ip_version', 'ipv4'),
        'Network class: %s' % design.get('network_class', 'C'),
        'Topology: %s' % design.get('topology_type', 'hierarchical'),
        'Base network: %s' % project.get('base_network'),
        'Routing: %s' % project.get('routing_protocol'),
        '',
        '1. Place routers and switches per inventory.',
        '2. Connect according to selected topology style.',
        '3. Apply generated IOS configs per device.',
        '4. Verify VLANs, addressing, routing.',
        '5. Test inter-department connectivity.',
        '',
        'Packet Tracer: https://www.netacad.com/courses/packet-tracer',
        '',
        generated.get('network_summary') or '',
    ])
