import os
from datetime import datetime

def generate_network_diagram(project_id, departments, project):
    """Generate network diagram"""
    try:
        import graphviz
        
        dot = graphviz.Digraph(comment='Network Topology', format='png')
        dot.attr(rankdir='TB', size='8.5,11')
        
        dot.attr(label=f'{project.company_name} - Network Topology', fontsize='16')
        
        # Add router
        dot.node('Router', 'Router', shape='router', color='blue', fontsize='12')
        
        # Add core switch
        dot.node('CoreSwitch', 'Core Switch', shape='box', color='green', fontsize='12')
        
        # Connect router to core switch
        dot.edge('Router', 'CoreSwitch', label='Trunk', fontsize='10')
        
        # Add departments
        for i, dept in enumerate(departments):
            cluster_name = f'cluster_{dept.name}'
            with dot.subgraph(name=cluster_name) as cluster:
                cluster.attr(label=dept.name, style='rounded', color='lightblue', fontsize='12')
                cluster.node(f'SW_{dept.name}', 'Switch', shape='box', fontsize='10')
                cluster.node(f'PC_{dept.name}', f'{dept.hosts} PCs', shape='box', fontsize='10')
                cluster.edge(f'SW_{dept.name}', f'PC_{dept.name}')
                
                dot.edge('CoreSwitch', f'SW_{dept.name}', label=f'VLAN {dept.vlan_id}', fontsize='10')
        
        # Render diagram
        os.makedirs('diagrams', exist_ok=True)
        file_path = f'diagrams/project_{project_id}_network'
        dot.render(file_path, view=False, cleanup=True)
        
        return f'{file_path}.png'
        
    except ImportError:
        return generate_simple_diagram(project_id, departments, project)
    except Exception as e:
        return generate_simple_diagram(project_id, departments, project)

def generate_simple_diagram(project_id, departments, project):
    """Generate simple text-based diagram as fallback"""
    diagram = []
    diagram.append('='*50)
    diagram.append(f'Network Topology - {project.company_name}')
    diagram.append('='*50)
    diagram.append('')
    diagram.append('         [Router]')
    diagram.append('            |')
    diagram.append('         [Core Switch]')
    diagram.append('         /    |    \\')
    
    for dept in departments:
        diagram.append(f'    [Switch_{dept.name}]  (VLAN {dept.vlan_id})')
        diagram.append(f'         |')
        diagram.append(f'    [{dept.hosts} PCs]')
        diagram.append('')
    
    diagram.append('='*50)
    diagram.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    diagram.append('='*50)
    
    os.makedirs('diagrams', exist_ok=True)
    file_path = f'diagrams/project_{project_id}_network.txt'
    with open(file_path, 'w') as f:
        f.write('\n'.join(diagram))
    
    return file_path

def generate_uml_diagrams(project_id, project):
    """Generate UML diagrams"""
    uml = []
    uml.append('='*50)
    uml.append('UML Use Case Diagram')
    uml.append('='*50)
    uml.append('')
    uml.append('+-------------------+')
    uml.append('|   Network Admin   |')
    uml.append('+-------------------+')
    uml.append('         |')
    uml.append('         v')
    uml.append('+-------------------+')
    uml.append('|  Create Network   |')
    uml.append('|     Design        |')
    uml.append('+-------------------+')
    uml.append('         |')
    uml.append('         v')
    uml.append('+-------------------+')
    uml.append('|  Configure        |')
    uml.append('|  Devices          |')
    uml.append('+-------------------+')
    uml.append('         |')
    uml.append('         v')
    uml.append('+-------------------+')
    uml.append('|  Validate         |')
    uml.append('|  Network          |')
    uml.append('+-------------------+')
    uml.append('         |')
    uml.append('         v')
    uml.append('+-------------------+')
    uml.append('|  Generate         |')
    uml.append('|  Reports          |')
    uml.append('+-------------------+')
    uml.append('')
    uml.append('='*50)
    uml.append('Activity Diagram: Network Design Process')
    uml.append('='*50)
    uml.append('[Start] --> [Input Requirements] --> [Validate Input]')
    uml.append('    |')
    uml.append('    v')
    uml.append('[Calculate VLSM] --> [Generate IPv4 Plan]')
    uml.append('    |')
    uml.append('    v')
    uml.append('[Generate Configs] --> [Validate Network]')
    uml.append('    |')
    uml.append('    v')
    uml.append('[Generate Reports] --> [End]')
    uml.append('')
    uml.append('='*50)
    uml.append(f'Generated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    uml.append('='*50)
    
    os.makedirs('diagrams', exist_ok=True)
    file_path = f'diagrams/project_{project_id}_uml.txt'
    with open(file_path, 'w') as f:
        f.write('\n'.join(uml))
    
    return file_path