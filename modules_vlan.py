def generate_vlan_allocations(departments):
    """Generate VLAN allocations"""
    vlan_allocations = []
    
    for i, dept in enumerate(departments):
        vlan_allocations.append({
            'vlan_id': dept.vlan_id,
            'name': dept.name,
            'network': dept.network,
            'subnet_mask': dept.subnet_mask,
            'switch_ports': f'Gi0/{i+1}',
            'description': f'VLAN for {dept.name} department'
        })
    
    return vlan_allocations