import ipaddress

def generate_ipv4_plan(departments):
    """Generate IPv4 addressing plan for devices"""
    ipv4_plan = {}
    
    for dept in departments:
        network = ipaddress.ip_network(f'{dept.network}/{dept.prefix}', strict=False)
        hosts = list(network.hosts())
        
        if len(hosts) >= 10:  # Need at least 10 IPs for devices
            plan = {
                'gateway': str(hosts[0]),
                'router_interface': str(hosts[1]),
                'switch_management': str(hosts[2]),
                'pc_range_start': str(hosts[3]),
                'pc_range_end': str(hosts[-1]),
                'server_start': str(hosts[4]) if len(hosts) > 5 else None,
                'printer_start': str(hosts[5]) if len(hosts) > 6 else None,
            }
        else:
            plan = {
                'gateway': str(hosts[0]) if hosts else 'N/A',
                'router_interface': str(hosts[1]) if len(hosts) > 1 else 'N/A',
                'switch_management': str(hosts[2]) if len(hosts) > 2 else 'N/A',
                'pc_range_start': str(hosts[3]) if len(hosts) > 3 else 'N/A',
                'pc_range_end': str(hosts[-1]) if hosts else 'N/A',
                'server_start': None,
                'printer_start': None,
            }
        
        ipv4_plan[dept.name] = plan
    
    return ipv4_plan