import ipaddress

def calculate_vlsm(departments, base_network):
    """Calculate VLSM subnet allocation"""
    # Sort departments by host count (largest first)
    sorted_depts = sorted(departments, key=lambda x: x.hosts, reverse=True)
    
    # Parse base network
    base = ipaddress.ip_network(base_network)
    current_network = base.network_address
    
    results = []
    
    for dept in sorted_depts:
        # Calculate required subnet size
        required_hosts = dept.hosts + 2  # +2 for network and broadcast
        prefix = 32 - (required_hosts - 1).bit_length()
        if prefix < 1:
            prefix = 1
        
        # Find next available subnet
        subnet = ipaddress.ip_network(f'{current_network}/{prefix}', strict=False)
        
        # Check if subnet fits in base network
        while not subnet.subnet_of(base):
            prefix += 1
            subnet = ipaddress.ip_network(f'{current_network}/{prefix}', strict=False)
        
        # Get subnet info
        network_addr = str(subnet.network_address)
        subnet_mask = str(subnet.netmask)
        broadcast = str(subnet.broadcast_address)
        
        # Calculate host range
        hosts = list(subnet.hosts())
        if hosts:
            host_range_start = str(hosts[0])
            host_range_end = str(hosts[-1])
            gateway = str(hosts[0])  # First usable IP as gateway
        else:
            host_range_start = 'N/A'
            host_range_end = 'N/A'
            gateway = 'N/A'
        
        results.append({
            'department': dept.name,
            'network': network_addr,
            'subnet_mask': subnet_mask,
            'prefix': prefix,
            'broadcast': broadcast,
            'host_range_start': host_range_start,
            'host_range_end': host_range_end,
            'gateway': gateway,
            'hosts_required': dept.hosts,
            'hosts_available': subnet.num_addresses - 2
        })
        
        # Move to next network
        current_network = subnet.broadcast_address + 1
    
    return results