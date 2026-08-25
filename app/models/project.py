from datetime import datetime
import json
from app import db


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    company_name = db.Column(db.String(150), nullable=False)
    project_name = db.Column(db.String(150), nullable=False)
    base_network = db.Column(db.String(50), nullable=False, default='192.168.10.0/24')
    routing_protocol = db.Column(db.String(20), default='OSPF')
    router_name = db.Column(db.String(50), default='R1')  # primary / legacy
    switch_name = db.Column(db.String(50), default='S1')  # primary / legacy
    devices_json = db.Column(db.Text, default='{}')  # {routers:[], switches:[], internet:{}}
    status = db.Column(db.String(30), default='Draft')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    departments = db.relationship(
        'Department', backref='project', lazy='dynamic',
        cascade='all, delete-orphan',
    )
    generated = db.relationship(
        'GeneratedData', backref='project', uselist=False,
        cascade='all, delete-orphan',
    )

    def get_devices(self):
        try:
            data = json.loads(self.devices_json or '{}')
        except Exception:
            data = {}
        routers = data.get('routers') or []
        switches = data.get('switches') or []
        internet = data.get('internet') or {'enabled': True, 'name': 'Internet', 'wan_ip': 'Auto'}
        if not routers:
            routers = [{'name': self.router_name or 'R1', 'role': 'edge', 'model': 'Cisco ISR'}]
        if not switches:
            switches = [{'name': self.switch_name or 'S1', 'role': 'access', 'model': 'Cisco Catalyst'}]
        return {'routers': routers, 'switches': switches, 'internet': internet}

    def set_devices(self, devices: dict):
        routers = devices.get('routers') or []
        switches = devices.get('switches') or []
        internet = devices.get('internet') or {'enabled': True, 'name': 'Internet', 'wan_ip': 'Auto'}
        if routers:
            self.router_name = routers[0].get('name') or 'R1'
        if switches:
            self.switch_name = switches[0].get('name') or 'S1'
        design = devices.get('design') or {}
        self.devices_json = json.dumps({
            'routers': routers,
            'switches': switches,
            'internet': internet,
            'design': design,
        })

    def to_dict(self, include_generated=False):
        devices = self.get_devices()
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'company_name': self.company_name,
            'project_name': self.project_name,
            'base_network': self.base_network,
            'routing_protocol': self.routing_protocol,
            'router_name': self.router_name,
            'switch_name': self.switch_name,
            'routers': devices['routers'],
            'switches': devices['switches'],
            'internet': devices['internet'],
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'departments': [d.to_dict() for d in self.departments],
        }
        if include_generated and self.generated:
            data['generated'] = self.generated.to_dict()
        return data

    def __repr__(self):
        return f'<Project {self.project_name}>'


class Department(db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    hosts = db.Column(db.Integer, nullable=False, default=20)
    vlan_id = db.Column(db.Integer, nullable=False, default=10)
    location = db.Column(db.String(100), default='HQ')
    gateway = db.Column(db.String(50), default='Auto')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'name': self.name,
            'hosts': self.hosts,
            'vlan_id': self.vlan_id,
            'location': self.location,
            'gateway': self.gateway,
        }

    def __repr__(self):
        return f'<Department {self.name}>'


class GeneratedData(db.Model):
    __tablename__ = 'generated_data'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), unique=True, nullable=False)
    vlsm_json = db.Column(db.Text, default='[]')
    ipv4_json = db.Column(db.Text, default='[]')
    ipv6_json = db.Column(db.Text, default='[]')
    design_json = db.Column(db.Text, default='{}')
    vlan_json = db.Column(db.Text, default='[]')
    router_config = db.Column(db.Text, default='')
    switch_config = db.Column(db.Text, default='')
    topology_html = db.Column(db.Text, default='')
    validation_json = db.Column(db.Text, default='[]')
    network_summary = db.Column(db.Text, default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_vlsm(self, data):
        self.vlsm_json = json.dumps(data)

    def get_vlsm(self):
        return json.loads(self.vlsm_json or '[]')

    def set_ipv4(self, data):
        self.ipv4_json = json.dumps(data)

    def get_ipv4(self):
        return json.loads(self.ipv4_json or '[]')

    def set_ipv6(self, data):
        self.ipv6_json = json.dumps(data or [])

    def get_ipv6(self):
        try:
            return json.loads(self.ipv6_json or '[]')
        except Exception:
            return []

    def set_design(self, data):
        self.design_json = json.dumps(data or {})

    def get_design(self):
        try:
            return json.loads(self.design_json or '{}')
        except Exception:
            return {}

    def set_vlan(self, data):
        self.vlan_json = json.dumps(data)

    def get_vlan(self):
        return json.loads(self.vlan_json or '[]')

    def set_validation(self, data):
        self.validation_json = json.dumps(data)

    def get_validation(self):
        return json.loads(self.validation_json or '[]')

    def to_dict(self):
        return {
            'vlsm': self.get_vlsm(),
            'ipv4': self.get_ipv4(),
            'ipv6': self.get_ipv6(),
            'design': self.get_design(),
            'vlan': self.get_vlan(),
            'router_config': self.router_config,
            'switch_config': self.switch_config,
            'topology': self.topology_html,
            'validation': self.get_validation(),
            'network_summary': self.network_summary,
        }
