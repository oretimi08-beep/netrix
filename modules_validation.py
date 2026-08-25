import ipaddress
from flask import flash

def validate_ip_address(ip_string):
    """Validate if string is a valid IP address"""
    try:
        ipaddress.ip_address(ip_string)
        return True
    except ValueError:
        return False

def validate_network(network_string):
    """Validate if string is a valid network"""
    try:
        ipaddress.ip_network(network_string, strict=False)
        return True
    except ValueError:
        return False

def validate_department(name, hosts, vlan_id, project):
    """Validate department input"""
    errors = []
    
    if not name or len(name.strip()) == 0:
        errors.append('Department name is required')
    elif len(name) > 50:
        errors.append('Department name too long (max 50 characters)')
    
    if hosts < 1 or hosts > 10000:
        errors.append('Host count must be between 1 and 10000')
    
    if vlan_id < 1 or vlan_id > 4094:
        errors.append('VLAN ID must be between 1 and 4094')
    
    return errors

def validate_all_departments(departments):
    """Validate all departments in a project"""
    errors = []
    names = set()
    vlans = set()
    
    for dept in departments:
        if dept.name in names:
            errors.append(f'Duplicate department name: {dept.name}')
        names.add(dept.name)
        
        if dept.vlan_id in vlans:
            errors.append(f'Duplicate VLAN ID: {dept.vlan_id}')
        vlans.add(dept.vlan_id)
        
        if dept.hosts < 1:
            errors.append(f'Invalid host count for {dept.name}')
    
    return errors