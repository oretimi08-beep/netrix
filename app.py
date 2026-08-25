from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os
import json
import csv
import io
from modules import validation, vlsm, ipv4, vlan, router, switch, diagrams, reports, packettracer

app = Flask(__name__)
app.config['SECRET_KEY'] = 'netrix-secret-key-2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///netrix.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    projects = db.relationship('Project', backref='user', lazy=True)

class Project(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_name = db.Column(db.String(100))
    base_network = db.Column(db.String(50))
    routing_protocol = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    departments = db.relationship('Department', backref='project', lazy=True, cascade='all, delete-orphan')
    configurations = db.relationship('Configuration', backref='project', lazy=True, cascade='all, delete-orphan')

class Department(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    hosts = db.Column(db.Integer, nullable=False)
    vlan_id = db.Column(db.Integer, nullable=False)
    network = db.Column(db.String(50))
    subnet_mask = db.Column(db.String(20))
    prefix = db.Column(db.Integer)
    broadcast = db.Column(db.String(50))
    host_range_start = db.Column(db.String(50))
    host_range_end = db.Column(db.String(50))
    gateway = db.Column(db.String(50))

class Configuration(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=False)
    device_type = db.Column(db.String(20))
    device_name = db.Column(db.String(50))
    config_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Create tables
with app.app_context():
    db.create_all()

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'danger')
            return redirect(url_for('register'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password)
        user = User(username=username, password=hashed_password, email=email)
        db.session.add(user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        
        flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'success')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    projects = Project.query.filter_by(user_id=session['user_id']).all()
    return render_template('dashboard.html', projects=projects)

@app.route('/project/new', methods=['GET', 'POST'])
def new_project():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        project_name = request.form['project_name']
        company_name = request.form['company_name']
        base_network = request.form['base_network']
        routing_protocol = request.form['routing_protocol']
        
        project = Project(
            name=project_name,
            user_id=session['user_id'],
            company_name=company_name,
            base_network=base_network,
            routing_protocol=routing_protocol
        )
        db.session.add(project)
        db.session.commit()
        
        flash('Project created successfully!', 'success')
        return redirect(url_for('edit_project', project_id=project.id))
    
    return render_template('new_project.html')

@app.route('/project/<int:project_id>')
def view_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    return render_template('project.html', project=project)

@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
def edit_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        # Handle department addition
        if 'add_department' in request.form:
            dept_name = request.form['dept_name']
            hosts = int(request.form['hosts'])
            vlan_id = int(request.form['vlan_id'])
            
            # Validation
            errors = validation.validate_department(dept_name, hosts, vlan_id, project)
            if errors:
                for error in errors:
                    flash(error, 'danger')
                return render_template('edit_project.html', project=project)
            
            department = Department(
                project_id=project.id,
                name=dept_name,
                hosts=hosts,
                vlan_id=vlan_id
            )
            db.session.add(department)
            db.session.commit()
            flash('Department added successfully!', 'success')
        
        # Handle department removal
        elif 'remove_department' in request.form:
            dept_id = int(request.form['dept_id'])
            department = Department.query.get_or_404(dept_id)
            db.session.delete(department)
            db.session.commit()
            flash('Department removed successfully!', 'success')
        
        # Handle processing
        elif 'process' in request.form:
            return redirect(url_for('process_project', project_id=project.id))
        
        return redirect(url_for('edit_project', project_id=project.id))
    
    return render_template('edit_project.html', project=project)

@app.route('/project/<int:project_id>/process')
def process_project(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    departments = Department.query.filter_by(project_id=project.id).all()
    
    if not departments:
        flash('Add departments first!', 'warning')
        return redirect(url_for('edit_project', project_id=project.id))
    
    # Validate all departments
    errors = validation.validate_all_departments(departments)
    if errors:
        for error in errors:
            flash(error, 'danger')
        return redirect(url_for('edit_project', project_id=project.id))
    
    try:
        # Process VLSM
        vlsm_results = vlsm.calculate_vlsm(departments, project.base_network)
        
        # Update departments with VLSM results
        for dept, result in zip(departments, vlsm_results):
            dept.network = result['network']
            dept.subnet_mask = result['subnet_mask']
            dept.prefix = result['prefix']
            dept.broadcast = result['broadcast']
            dept.host_range_start = result['host_range_start']
            dept.host_range_end = result['host_range_end']
            dept.gateway = result['gateway']
        
        db.session.commit()
        
        # Generate IPv4 plan
        ipv4_plan = ipv4.generate_ipv4_plan(departments)
        
        # Generate VLAN allocations
        vlan_allocations = vlan.generate_vlan_allocations(departments)
        
        # Generate router configuration
        router_config = router.generate_router_config(project, departments)
        save_configuration(project.id, 'router', 'Router1', router_config)
        
        # Generate switch configuration
        switch_config = switch.generate_switch_config(project, departments)
        save_configuration(project.id, 'switch', 'Switch1', switch_config)
        
        # Generate documentation
        doc = reports.generate_documentation(project, departments, ipv4_plan, vlan_allocations)
        reports.save_report(project.id, doc)
        
        # Generate diagrams
        diagrams.generate_network_diagram(project.id, departments, project)
        diagrams.generate_uml_diagrams(project.id, project)
        
        # Validate with Packet Tracer
        pt_result = packettracer.validate(project, departments)
        
        flash('Network design processed successfully!', 'success')
        return redirect(url_for('results', project_id=project.id))
        
    except Exception as e:
        flash(f'Error processing project: {str(e)}', 'danger')
        return redirect(url_for('edit_project', project_id=project.id))

def save_configuration(project_id, device_type, device_name, config_text):
    config = Configuration(
        project_id=project_id,
        device_type=device_type,
        device_name=device_name,
        config_text=config_text
    )
    db.session.add(config)
    db.session.commit()

@app.route('/project/<int:project_id>/results')
def results(project_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    departments = Department.query.filter_by(project_id=project.id).all()
    configurations = Configuration.query.filter_by(project_id=project.id).all()
    
    return render_template('results.html', project=project, departments=departments, configurations=configurations)

@app.route('/project/<int:project_id>/download/<file_type>')
def download_file(project_id, file_type):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    project = Project.query.get_or_404(project_id)
    if project.user_id != session['user_id']:
        flash('Access denied', 'danger')
        return redirect(url_for('dashboard'))
    
    # Create exports directory if it doesn't exist
    os.makedirs('exports', exist_ok=True)
    
    file_path = f'exports/project_{project_id}_{file_type}'
    
    if file_type == 'report':
        file_path += '.pdf'
        if not os.path.exists(file_path):
            flash('Report not generated yet', 'warning')
            return redirect(url_for('results', project_id=project.id))
        return send_file(file_path, as_attachment=True, download_name=f'{project.name}_Report.pdf')
    
    elif file_type == 'router_config':
        config = Configuration.query.filter_by(project_id=project.id, device_type='router').first()
        if not config:
            flash('Router configuration not found', 'warning')
            return redirect(url_for('results', project_id=project.id))
        return send_file(
            io.BytesIO(config.config_text.encode()),
            as_attachment=True,
            download_name=f'{project.name}_Router_Config.txt',
            mimetype='text/plain'
        )
    
    elif file_type == 'switch_config':
        config = Configuration.query.filter_by(project_id=project.id, device_type='switch').first()
        if not config:
            flash('Switch configuration not found', 'warning')
            return redirect(url_for('results', project_id=project.id))
        return send_file(
            io.BytesIO(config.config_text.encode()),
            as_attachment=True,
            download_name=f'{project.name}_Switch_Config.txt',
            mimetype='text/plain'
        )
    
    elif file_type == 'csv':
        departments = Department.query.filter_by(project_id=project.id).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['Department', 'VLAN', 'Network', 'Subnet Mask', 'Hosts', 'Broadcast', 'Gateway'])
        for dept in departments:
            writer.writerow([dept.name, dept.vlan_id, dept.network, dept.subnet_mask, dept.hosts, dept.broadcast, dept.gateway])
        output.seek(0)
        return send_file(
            io.BytesIO(output.getvalue().encode()),
            as_attachment=True,
            download_name=f'{project.name}_Address_Plan.csv',
            mimetype='text/csv'
        )
    
    elif file_type == 'diagram':
        file_path = f'diagrams/project_{project_id}_network.png'
        if not os.path.exists(file_path):
            flash('Diagram not generated yet', 'warning')
            return redirect(url_for('results', project_id=project.id))
        return send_file(file_path, as_attachment=True, download_name=f'{project.name}_Network_Diagram.png')
    
    elif file_type == 'uml':
        file_path = f'diagrams/project_{project_id}_uml.png'
        if not os.path.exists(file_path):
            flash('UML diagram not generated yet', 'warning')
            return redirect(url_for('results', project_id=project.id))
        return send_file(file_path, as_attachment=True, download_name=f'{project.name}_UML_Diagram.png')
    
    flash('Invalid download type', 'danger')
    return redirect(url_for('results', project_id=project.id))

@app.route('/api/validate', methods=['POST'])
def api_validate():
    data = request.json
    errors = []
    
    if 'departments' in data:
        for dept in data['departments']:
            if not dept.get('name'):
                errors.append('Department name is required')
            if not dept.get('hosts') or int(dept.get('hosts', 0)) < 1:
                errors.append(f'Invalid host count for {dept.get("name", "Unknown")}')
            if not dept.get('vlan_id') or int(dept.get('vlan_id', 0)) < 1 or int(dept.get('vlan_id', 0)) > 4094:
                errors.append(f'Invalid VLAN ID for {dept.get("name", "Unknown")}')
    
    return jsonify({'valid': len(errors) == 0, 'errors': errors})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)