from flask import Flask, request, jsonify, render_template, redirect, url_for, make_response
import mysql.connector
from mysql.connector import Error
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import logging
import schedule
import time
import threading
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("application.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

db_config = {
    'host': '10.110.3.102',
    'user': 'root',
    'password': 'Passw0rd123',
    'database': 'esp32_data'
}

EMAIL_SENDER = 'soltanimayssa3@gmail.com'
EMAIL_PASSWORD = 'drfq qfyo rgus bpjv'
SMTP_SERVER = 'smtp.gmail.com'
SMTP_PORT = 587

def init_db():
    try:
        logger.info("Initializing database connection")
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                role ENUM('operator', 'admin') DEFAULT 'operator'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                event_type VARCHAR(50) NOT NULL,
                machine VARCHAR(50) NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                duration FLOAT DEFAULT NULL,
                start_comment VARCHAR(255) DEFAULT NULL,
                end_comment VARCHAR(255) DEFAULT NULL,
                start_user_id VARCHAR(50) DEFAULT NULL,
                end_user_id VARCHAR(50) DEFAULT NULL,
                status ENUM('active', 'canceled') DEFAULT 'active',
                cancel_reason VARCHAR(255) DEFAULT NULL,
                reaction_time FLOAT DEFAULT NULL,
                maintenance_arrival_user_id VARCHAR(50) DEFAULT NULL,
                user_id VARCHAR(50) DEFAULT NULL,
                reason VARCHAR(255) DEFAULT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS raspberry_machines (
                ip_address VARCHAR(15) PRIMARY KEY,
                machine_name VARCHAR(50) NOT NULL,
                preventive_maintenance_date DATE DEFAULT NULL,
                comment VARCHAR(255) DEFAULT NULL,
                status VARCHAR(50) DEFAULT 'working'
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preventive_maintenance (
                id INT AUTO_INCREMENT PRIMARY KEY,
                machine_name VARCHAR(50) NOT NULL,
                maintenance_date DATE NOT NULL,
                status ENUM('scheduled', 'notified_d2', 'notified_d1', 'due', 'overdue', 'completed', 'canceled') DEFAULT 'scheduled',
                last_notification DATETIME DEFAULT NULL,
                power_cut_sent BOOLEAN DEFAULT FALSE,
                FOREIGN KEY (machine_name) REFERENCES raspberry_machines(machine_name)
            )
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO users (username, password, role) VALUES
            ('admin', 'admin123', 'admin'),
            ('operator', 'operator123', 'operator')
        """)
        
        cursor.execute("""
            INSERT IGNORE INTO raspberry_machines (ip_address, machine_name, status) VALUES
            ('10.110.21.34', 'Machine5', 'working'),
            ('10.110.23.135', 'Machine1', 'working'),
            ('192.168.1.101', 'Machine2', 'working')
        """)
        
        connection.commit()
        logger.info("Database initialized successfully")
    except Error as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def is_valid_machine(machine_name, client_ip=None):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT machine_name FROM raspberry_machines WHERE machine_name = %s", (machine_name,))
        result = cursor.fetchone()
        return True if result else False
    except Error as e:
        logger.error(f"Error validating machine: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def update_raspberry_status(machine_name, status):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "UPDATE raspberry_machines SET status = %s WHERE machine_name = %s",
            (status, machine_name)
        )
        connection.commit()
        logger.info(f"Status updated for {machine_name} to {status}")
        return True
    except Error as e:
        logger.error(f"Error updating status for {machine_name}: {e}")
        return False
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def ping_single_machine(ip_address, machine_name):
    try:
        url = f"http://{ip_address}:8000/status"
        response = requests.get(url, timeout=3)
        if response.status_code == 200:
            status = response.json().get("status", "working")
            logger.info(f"Raspberry Pi {machine_name} at {ip_address} status: {status}")
            update_raspberry_status(machine_name, status)
        else:
            logger.warning(f"Raspberry Pi {machine_name} at {ip_address} failed: {response.status_code}")
            update_raspberry_status(machine_name, "offline")
    except Exception as e:
        logger.error(f"Error pinging {machine_name} at {ip_address}: {e}")
        update_raspberry_status(machine_name, "offline")

def ping_raspberry():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT ip_address, machine_name FROM raspberry_machines")
        machines = cursor.fetchall()
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            future_to_machine = {
                executor.submit(ping_single_machine, ip_address, machine_name): (ip_address, machine_name)
                for ip_address, machine_name in machines
            }
            for future in as_completed(future_to_machine):
                ip_address, machine_name = future_to_machine[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing ping for {machine_name} at {ip_address}: {e}")
                    update_raspberry_status(machine_name, "offline")
    except Error as e:
        logger.error(f"Database error pinging Raspberry Pis: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def save_to_db(event_type, machine, duration=None, start_comment=None, end_comment=None, client_ip=None, start_user_id=None, end_user_id=None, cancel_reason=None, reaction_time=None, maintenance_arrival_user_id=None, user_id=None, reason=None):
    if not is_valid_machine(machine, client_ip):
        logger.warning(f"Invalid machine: {machine} from IP: {client_ip}")
        return False
    
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        
        if event_type in ["downtime", "breakdown", "material_changes", "emergency", "break"]:
            cursor.execute(
                "INSERT INTO event_logs (event_type, machine, start_comment, start_user_id, user_id, reason) VALUES (%s, %s, %s, %s, %s, %s)",
                (event_type, machine, start_comment if start_comment else "", start_user_id, user_id, reason)
            )
            update_raspberry_status(machine, event_type)
        elif event_type == "maintenance_arrival":
            cursor.execute(
                "SELECT id FROM event_logs WHERE event_type IN ('breakdown', 'material_changes') AND machine = %s AND duration IS NULL ORDER BY timestamp DESC LIMIT 1",
                (machine,)
            )
            original_event = cursor.fetchone()
            if original_event:
                event_id = original_event[0]
                cursor.execute(
                    "UPDATE event_logs SET reaction_time = %s, maintenance_arrival_user_id = %s WHERE id = %s",
                    (reaction_time, maintenance_arrival_user_id, event_id)
                )
        elif event_type.startswith("reset_"):
            original_event_type = event_type.replace("reset_", "")
            cursor.execute(
                "SELECT id FROM event_logs WHERE event_type = %s AND machine = %s AND duration IS NULL ORDER BY timestamp DESC LIMIT 1",
                (original_event_type, machine)
            )
            original_event = cursor.fetchone()
            if original_event:
                event_id = original_event[0]
                cursor.execute(
                    "UPDATE event_logs SET duration = %s, end_user_id = %s, end_comment = %s WHERE id = %s",
                    (duration, end_user_id, end_comment, event_id)
                )
                update_raspberry_status(machine, "working")
        elif event_type.startswith("cancel_"):
            original_event_type = event_type.replace("cancel_", "")
            cursor.execute(
                "SELECT id FROM event_logs WHERE event_type = %s AND machine = %s AND duration IS NULL ORDER BY timestamp DESC LIMIT 1",
                (original_event_type, machine)
            )
            original_event = cursor.fetchone()
            if original_event:
                event_id = original_event[0]
                cursor.execute(
                    "UPDATE event_logs SET duration = %s, status = 'canceled', cancel_reason = %s WHERE id = %s",
                    (duration, cancel_reason, event_id)
                )
                update_raspberry_status(machine, "working")
        
        connection.commit()
        logger.info(f"Event {event_type} saved for {machine}")
        return True
    except Error as e:
        logger.error(f"Database save error: {e}")
        if connection:
            connection.rollback()
        return False
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def verify_user(username, password):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT role FROM users WHERE username = %s AND password = %s", (username, password))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        logger.error(f"User verification error: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def get_machine_name(ip_address):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT machine_name FROM raspberry_machines WHERE ip_address = %s", (ip_address,))
        result = cursor.fetchone()
        return result[0] if result else None
    except Error as e:
        logger.error(f"Error getting machine name: {e}")
        return None
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def send_email(recipient, subject, body):
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent to {recipient}: {subject}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

def send_power_cut_signal(machine_name, ip_address):
    try:
        url = f"http://{ip_address}:8000/power_cut"
        data = {"machine_name": machine_name}
        response = requests.post(url, json=data, timeout=5)
        if response.status_code == 200:
            logger.info(f"Power cut signal sent to {machine_name} at {ip_address}")
            return True
        else:
            logger.warning(f"Failed power cut signal to {machine_name}: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error sending power cut signal to {machine_name} at {ip_address}: {e}")
        return False
def check_preventive_maintenance():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("""
            SELECT pm.id, pm.machine_name, pm.maintenance_date, pm.status, pm.last_notification, pm.power_cut_sent, rm.ip_address
            FROM preventive_maintenance pm
            JOIN raspberry_machines rm ON pm.machine_name = rm.machine_name
            WHERE pm.status NOT IN ('completed', 'canceled')
        """)
        schedules = cursor.fetchall()
        today = datetime.now().date()
        
        for schedule in schedules:
            pm_id, machine_name, maintenance_date, status, last_notification, power_cut_sent, ip_address = schedule
            days_until = (maintenance_date - today).days
            last_notification_date = last_notification.date() if last_notification else None
            
            if days_until == 2 and status == 'scheduled' and (not last_notification_date or last_notification_date != today):
                send_email(
                    "admin@example.com",
                    f"Maintenance Reminder: {machine_name}",
                    f"Preventive maintenance for {machine_name} in 2 days on {maintenance_date}."
                )
                cursor.execute(
                    "UPDATE preventive_maintenance SET status = 'notified_d2', last_notification = %s WHERE id = %s",
                    (datetime.now(), pm_id)
                )
            
            elif days_until == 1 and status in ('scheduled', 'notified_d2') and (not last_notification_date or last_notification_date != today):
                send_email(
                    "admin@example.com",
                    f"Maintenance Reminder: {machine_name}",
                    f"Preventive maintenance for {machine_name} tomorrow on {maintenance_date}."
                )
                cursor.execute(
                    "UPDATE preventive_maintenance SET status = 'notified_d1', last_notification = %s WHERE id = %s",
                    (datetime.now(), pm_id)
                )
            
            elif days_until == 0 and status in ('scheduled', 'notified_d2', 'notified_d1') and (not last_notification_date or last_notification_date != today):
                send_email(
                    "admin@example.com",
                    f"Maintenance Due: {machine_name}",
                    f"Preventive maintenance for {machine_name} due today on {maintenance_date}."
                )
                cursor.execute(
                    "UPDATE preventive_maintenance SET status = 'due', last_notification = %s WHERE id = %s",
                    (datetime.now(), pm_id)
                )
            
            elif days_until == -1 and status == 'due' and not power_cut_sent:
                if send_power_cut_signal(machine_name, ip_address):
                    send_email(
                        "admin@example.com",
                        f"Maintenance Overdue: {machine_name}",
                        f"Maintenance for {machine_name} was due on {maintenance_date}. Power cut executed."
                    )
                    cursor.execute(
                        "UPDATE preventive_maintenance SET status = 'overdue', power_cut_sent = TRUE, last_notification = %s WHERE id = %s",
                        (datetime.now(), pm_id)
                    )
        
        connection.commit()
    except Error as e:
        logger.error(f"Error checking maintenance: {e}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = verify_user(username, password)
        if role:
            resp = make_response(redirect(url_for('dashboard' if role == 'operator' else 'admin_dashboard')))
            resp.set_cookie('username', username)
            resp.set_cookie('role', role)
            return resp
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html')

@app.route('/admin')
def admin_dashboard():
    username = request.cookies.get('username')
    role = request.cookies.get('role')
    if not username or role != 'admin':
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/analytics')
def analytics_dashboard():
    username = request.cookies.get('username')
    role = request.cookies.get('role')
    if not username or role != 'admin':
        return redirect(url_for('login'))
    return render_template('analytics_dashboard.html')

@app.route('/maintenance')
def maintenance_management():
    username = request.cookies.get('username')
    role = request.cookies.get('role')
    if not username or role != 'admin':
        return redirect(url_for('login'))
    return render_template('preventive_maintenance.html')

@app.route('/logout')
def logout():
    resp = make_response(redirect(url_for('login')))
    resp.delete_cookie('username')
    resp.delete_cookie('role')
    resp.delete_cookie('machine_name')
    return resp

@app.route('/')
def dashboard():
    username = request.cookies.get('username')
    role = request.cookies.get('role')
    if not username or not role:
        return redirect(url_for('login'))
    return render_template('admin_dashboard.html')

@app.route('/set_machine', methods=['POST'])
def set_machine():
    machine_name = request.form.get('machine_name')
    if not machine_name:
        return redirect(url_for('dashboard'))
    resp = make_response(redirect(url_for('dashboard')))
    resp.set_cookie('machine_name', machine_name)
    return resp

@app.route('/api/test_connectivity', methods=['POST'])
def test_connectivity():
    data = request.get_json() or {}
    return jsonify({"status": "success", "received": data}), 200

@app.route('/api/trigger_power_cut/<machine_name>', methods=['GET'])
def execute_power_cut(machine_name):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True, dictionary=True)
        cursor.execute("SELECT ip_address FROM raspberry_machines WHERE machine_name = %s", (machine_name,))
        result = cursor.fetchone()
        if not result:
            return jsonify({"error": "Machine not found"}), 404
        
        ip_address = result['ip_address']
        if send_power_cut_signal(machine_name, ip_address):
            return jsonify({"status": "success", "message": "Power cut executed"}), 200
        return jsonify({"error": "Failed to send power cut signal"}), 500
    except Error as e:
        logger.error(f"Error sending power cut: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/api/<event_type>/<machine_name>', methods=['POST'])
def handle_event(event_type, machine_name):
    client_ip = request.remote_addr
    data = request.get_json() or {}
    duration = data.get('duration')
    start_comment = data.get('start_comment')
    end_comment = data.get('end_comment')
    start_user_id = data.get('start_user_id')
    end_user_id = data.get('end_user_id')
    cancel_reason = data.get('cancel_reason')
    reaction_time = data.get('reaction_time')
    maintenance_arrival_user_id = data.get('maintenance_arrival_user_id')
    user_id = data.get('user_id')
    reason = data.get('reason')

    if not is_valid_machine(machine_name, client_ip):
        return jsonify({"error": "Unrecognized machine"}), 403

    try:
        if save_to_db(event_type, machine_name, duration, start_comment, end_comment, client_ip, start_user_id, end_user_id, cancel_reason, reaction_time, maintenance_arrival_user_id, user_id, reason):
            send_email("admin@example.com", f"{event_type.capitalize()} Notification: {machine_name}", 
                       f"Event: {event_type}\nMachine: {machine_name}\nStart User: {start_user_id or 'N/A'}\nEnd User: {end_user_id or 'N/A'}\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            return jsonify({
                "status": "success",
                "event": event_type,
                "machine": machine_name,
                "duration": duration,
                "start_comment": start_comment,
                "end_comment": end_comment,
                "start_user_id": start_user_id,
                "end_user_id": end_user_id,
                "cancel_reason": cancel_reason,
                "reaction_time": reaction_time,
                "maintenance_arrival_user_id": maintenance_arrival_user_id,
                "user_id": user_id,
                "reason": reason
            }), 200
        return jsonify({"error": "Failed to process event"}), 500
    except Exception as e:
        logger.error(f"Error processing {event_type} for {machine_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/get_machine_name', methods=['POST'])
def get_machine_name_endpoint():
    data = request.get_json() or {}
    ip_address = data.get('ip_address')
    if not ip_address:
        return jsonify({"error": "IP address required"}), 400
    machine_name = get_machine_name(ip_address)
    if machine_name:
        return jsonify({"machine_name": machine_name}), 200
    return jsonify({"error": "Machine not found"}), 404

@app.route('/api/downtime_history', methods=['GET'])
def get_downtime_history():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT id, machine, timestamp, duration, start_comment, end_comment, start_user_id, end_user_id, status, cancel_reason FROM event_logs WHERE event_type = 'downtime' ORDER BY timestamp DESC")
        downtimes = cursor.fetchall()
        downtime_list = [
            {
                "id": d[0], "machine": d[1], "timestamp": str(d[2]), "duration": d[3],
                "start_comment": d[4], "end_comment": d[5], "start_user_id": d[6],
                "end_user_id": d[7], "status": d[8], "cancel_reason": d[9]
            } for d in downtimes
        ]
        return jsonify({"downtimes": downtime_list})
    except Error as e:
        logger.error(f"Error retrieving downtime history: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/api/all_machines', methods=['GET'])
def get_all_machines():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True, dictionary=True)
        cursor.execute("SELECT * FROM raspberry_machines ORDER BY machine_name")
        machines = cursor.fetchall()
        machine_list = [
            {
                "ip_address": m["ip_address"],
                "machine_name": m["machine_name"],
                "preventive_maintenance_date": str(m["preventive_maintenance_date"]) if m["preventive_maintenance_date"] else None,
                "comment": m["comment"],
                "status": m["status"]
            } for m in machines
        ]
        return jsonify({"machines": machine_list})
    except Error as e:
        logger.error(f"Error retrieving all machines: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/api/intervention_history', methods=['GET'])
def get_intervention_history():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT id, event_type, machine, timestamp, duration, start_comment, end_comment, start_user_id, end_user_id, status, cancel_reason, reaction_time, maintenance_arrival_user_id FROM event_logs WHERE event_type IN ('breakdown', 'material_changes', 'emergency') ORDER BY timestamp DESC")
        interventions = cursor.fetchall()
        intervention_list = [
            {
                "id": i[0], "event_type": i[1], "machine": i[2], "timestamp": str(i[3]),
                "duration": i[4], "start_comment": i[5], "end_comment": i[6],
                "start_user_id": i[7], "end_user_id": i[8], "status": i[9],
                "cancel_reason": i[10], "reaction_time": i[11],
                "maintenance_arrival_user_id": i[12]
            } for i in interventions
        ]
        return jsonify({"interventions": intervention_list})
    except Error as e:
        logger.error(f"Error retrieving intervention history: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/recent_events', methods=['GET'])
def get_recent_events():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("""
            SELECT id, event_type, machine, timestamp, duration, start_user_id, end_user_id, 
                   start_comment, end_comment, cancel_reason, status, reaction_time, 
                   maintenance_arrival_user_id, user_id, reason
            FROM event_logs
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        events = cursor.fetchall()
        event_list = [
            {
                "id": e[0],
                "event_type": e[1],
                "machine": e[2],
                "timestamp": str(e[3]),
                "duration": e[4],
                "start_user_id": e[5],
                "end_user_id": e[6],
                "start_comment": e[7],
                "end_comment": e[8],
                "cancel_reason": e[9],
                "status": e[10],
                "reaction_time": e[11],
                "maintenance_arrival_user_id": e[12],
                "user_id": e[13],
                "reason": e[14]
            } for e in events
        ]
        return jsonify({"events": event_list})
    except Error as e:
        logger.error(f"Error retrieving recent events: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/manage_machines')
def manage_machines():
    username = request.cookies.get('username')
    role = request.cookies.get('role')
    if not username or role != 'admin':
        return redirect(url_for('login'))
    return render_template('manage_machines.html')

@app.route('/api/add_machine', methods=['POST'])
def add_machine():
    data = request.get_json() or {}
    ip_address = data.get('ip_address')
    machine_name = data.get('machine_name')
    
    if not ip_address or not machine_name:
        return jsonify({"error": "IP address and machine name are required"}), 400
    
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "INSERT INTO raspberry_machines (ip_address, machine_name, status) VALUES (%s, %s, 'working')",
            (ip_address, machine_name)
        )
        connection.commit()
        logger.info(f"Machine {machine_name} with IP {ip_address} added successfully")
        return jsonify({"status": "success", "message": "Machine added"}), 200
    except Error as e:
        logger.error(f"Error adding machine: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/update_machine', methods=['PUT'])
def update_machine():
    data = request.get_json() or {}
    ip_address = data.get('ip_address')
    machine_name = data.get('machine_name')
    ip_address_original = data.get('ip_address_original')
    
    if not ip_address or not machine_name or not ip_address_original:
        return jsonify({"error": "IP address, machine name, and original IP address are required"}), 400
    
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "UPDATE raspberry_machines SET ip_address = %s, machine_name = %s WHERE ip_address = %s",
            (ip_address, machine_name, ip_address_original)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Machine not found"}), 404
        connection.commit()
        logger.info(f"Machine {machine_name} with IP {ip_address} updated successfully")
        return jsonify({"status": "success", "message": "Machine updated"}), 200
    except Error as e:
        logger.error(f"Error updating machine: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/delete_machine/<ip_address>', methods=['DELETE'])
def delete_machine(ip_address):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("DELETE FROM raspberry_machines WHERE ip_address = %s", (ip_address,))
        if cursor.rowcount == 0:
            return jsonify({"error": "Machine not found"}), 404
        connection.commit()
        logger.info(f"Machine with IP {ip_address} deleted successfully")
        return jsonify({"status": "success", "message": "Machine deleted"}), 200
    except Error as e:
        logger.error(f"Error deleting machine: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/api/all_events', methods=['GET'])
def get_all_events():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("""
            SELECT *
            FROM event_logs
            ORDER BY timestamp DESC
        """)
        events = cursor.fetchall()
        event_list = [
            {
                "id": e[0],
                "event_type": e[1],
                "timestamp": str(e[2]),
                "duration": e[3],
                "machine": e[4],
                "start_user_id": e[5],
                "end_user_id": e[6],
                "start_comment": e[7],
                "end_comment": e[8],
                "cancel_reason": e[9],
                "status": e[10],
                "reaction_time": e[11],
                "maintenance_arrival_user_id": e[12],
                "breakdown": e[13],
                "user_id": e[14],
                "reason": e[15]
            } for e in events
        ]
        return jsonify({"events": event_list})
    except Error as e:
        logger.error(f"Error retrieving recent events: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
@app.route('/api/realtime_indicators', methods=['GET'])
def get_realtime_indicators():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT COUNT(*) FROM event_logs")
        total_events = cursor.fetchone()[0]
        cursor.execute("SELECT event_type, COUNT(*) FROM event_logs GROUP BY event_type")
        events_by_type = dict(cursor.fetchall())
        cursor.execute("SELECT event_type, machine, timestamp FROM event_logs ORDER BY timestamp DESC LIMIT 1")
        last_event = cursor.fetchone()
        last_event_data = {"event_type": last_event[0], "machine": last_event[1], "timestamp": str(last_event[2])} if last_event else None
        return jsonify({"total_events": total_events, "events_by_type": events_by_type, "last_event": last_event_data})
    except Error as e:
        logger.error(f"Error retrieving indicators: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/preventive_maintenance', methods=['GET'])
def get_preventive_maintenance():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT id, machine_name, maintenance_date, status, power_cut_sent FROM preventive_maintenance ORDER BY maintenance_date ASC")
        schedules = cursor.fetchall()
        schedule_list = [
            {
                "id": s[0], "machine_name": s[1], "maintenance_date": str(s[2]),
                "status": s[3], "power_cut_sent": s[4]
            } for s in schedules
        ]
        return jsonify({"schedules": schedule_list})
    except Error as e:
        logger.error(f"Error retrieving maintenance schedules: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/available_machines', methods=['GET'])
def get_available_machines():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("SELECT machine_name, status FROM raspberry_machines ORDER BY machine_name")
        machines = cursor.fetchall()
        machine_list = [{"machine_name": m[0], "status": m[1]} for m in machines]
        return jsonify({"machines": machine_list})
    except Error as e:
        logger.error(f"Error retrieving machines: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/add_maintenance', methods=['POST'])
def add_maintenance():
    data = request.get_json() or {}
    machine_name = data.get('machine_name')
    maintenance_date = data.get('maintenance_date')
    if not machine_name or not maintenance_date:
        return jsonify({"error": "Machine name and date required"}), 400
    if not is_valid_machine(machine_name):
        return jsonify({"error": "Invalid machine name"}), 400
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "INSERT INTO preventive_maintenance (machine_name, maintenance_date, status) VALUES (%s, %s, 'scheduled')",
            (machine_name, maintenance_date)
        )
        connection.commit()
        return jsonify({"status": "success", "message": "Maintenance scheduled"}), 200
    except Error as e:
        logger.error(f"Error adding maintenance: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/update_maintenance/<int:schedule_id>', methods=['PUT'])
def update_maintenance(schedule_id):
    data = request.get_json() or {}
    machine_name = data.get('machine_name')
    maintenance_date = data.get('maintenance_date')
    if not machine_name or not maintenance_date:
        return jsonify({"error": "Machine name and date required"}), 400
    if not is_valid_machine(machine_name):
        return jsonify({"error": "Invalid machine name"}), 400
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "UPDATE preventive_maintenance SET machine_name = %s, maintenance_date = %s, status = 'scheduled', last_notification = NULL, power_cut_sent = FALSE WHERE id = %s",
            (machine_name, maintenance_date, schedule_id)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Schedule not found"}), 404
        connection.commit()
        return jsonify({"status": "success", "message": "Maintenance updated"}), 200
    except Error as e:
        logger.error(f"Error updating maintenance: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/complete_maintenance/<int:schedule_id>', methods=['PUT'])
def complete_maintenance(schedule_id):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "UPDATE preventive_maintenance SET status = 'completed', last_notification = %s, power_cut_sent = FALSE WHERE id = %s",
            (datetime.now(), schedule_id)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Schedule not found"}), 404
        connection.commit()
        return jsonify({"status": "success", "message": "Maintenance completed"}), 200
    except Error as e:
        logger.error(f"Error completing maintenance: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/cancel_maintenance/<int:schedule_id>', methods=['PUT'])
def cancel_maintenance(schedule_id):
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute(
            "UPDATE preventive_maintenance SET status = 'canceled', last_notification = %s, power_cut_sent = FALSE WHERE id = %s",
            (datetime.now(), schedule_id)
        )
        if cursor.rowcount == 0:
            return jsonify({"error": "Schedule not found"}), 404
        connection.commit()
        return jsonify({"status": "success", "message": "Maintenance canceled"}), 200
    except Error as e:
        logger.error(f"Error canceling maintenance: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/downtime_alert', methods=['POST'])
def downtime_alert():
    data = request.get_json() or {}
    machine_name = data.get('machine_name')
    client_ip = request.remote_addr
    if not machine_name:
        return jsonify({"error": "Machine name required"}), 400
    if not is_valid_machine(machine_name, client_ip):
        return jsonify({"error": "Unrecognized machine"}), 403
    try:
        save_to_db("downtime", machine_name, client_ip=client_ip, start_user_id="system", start_comment="Automatic downtime alert")
        send_email(
            "admin@example.com",
            f"Downtime Alert: {machine_name}",
            f"Downtime on {machine_name} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}."
        )
        return jsonify({"status": "success", "message": "Downtime alert processed"}), 200
    except Exception as e:
        logger.error(f"Error processing downtime alert for {machine_name}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/active_events', methods=['GET'])
def get_active_events():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True)
        cursor.execute("""
            SELECT id, event_type, machine, timestamp, start_user_id, status
            FROM event_logs
            WHERE duration IS NULL AND status = 'active'
            ORDER BY timestamp DESC
        """)
        events = cursor.fetchall()
        event_list = [
            {
                "id": e[0],
                "event_type": e[1],
                "machine": e[2],
                "timestamp": str(e[3]),
                "start_user_id": e[4],
                "status": e[5]
            } for e in events
        ]
        return jsonify({"events": event_list})
    except Error as e:
        logger.error(f"Error retrieving active events: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    try:
        connection = mysql.connector.connect(**db_config)
        cursor = connection.cursor(buffered=True, dictionary=True)
        cursor.execute("SELECT machine, COUNT(*) as event_count FROM event_logs GROUP BY machine ORDER BY event_count DESC")
        events_per_machine = cursor.fetchall()
        cursor.execute("SELECT event_type, COUNT(*) as event_count FROM event_logs GROUP BY event_type ORDER BY event_count DESC")
        events_by_type = cursor.fetchall()
        cursor.execute("SELECT machine, SUM(duration) as total_downtime FROM event_logs WHERE event_type IN ('downtime', 'emergency') AND duration IS NOT NULL AND status = 'active' GROUP BY machine")
        total_downtime_per_machine = cursor.fetchall()
        cursor.execute("SELECT machine, COUNT(*) as downtime_count FROM event_logs WHERE event_type = 'downtime' GROUP BY machine ORDER BY downtime_count DESC")
        downtime_per_machine = cursor.fetchall()
        cursor.execute("SELECT machine, COUNT(*) as canceled_count FROM event_logs WHERE status = 'canceled' GROUP BY machine ORDER BY canceled_count DESC")
        canceled_events = cursor.fetchall()
        cursor.execute("SELECT machine, AVG(duration) as avg_duration FROM event_logs WHERE event_type = 'downtime' AND duration IS NOT NULL AND status = 'active' GROUP BY machine ORDER BY avg_duration DESC")
        avg_downtime_duration = cursor.fetchall()
        cursor.execute("SELECT event_type, machine, timestamp, duration FROM event_logs WHERE event_type IN ('downtime', 'emergency') AND status = 'active' ORDER BY timestamp")
        failure_events = cursor.fetchall()

        kpis = {"availability_rate": 0.0, "failure_rate": 0.0, "mttr": 0.0, "mtbf": 0.0}
        if failure_events:
            first_event_time = failure_events[0]["timestamp"]
            last_event_time = failure_events[-1]["timestamp"]
            total_time_seconds = (last_event_time - first_event_time).total_seconds()
            num_failures = len(failure_events)
            total_downtime_seconds = sum(event["duration"] for event in failure_events if event["duration"] is not None)
            operational_time_seconds = total_time_seconds - total_downtime_seconds if total_time_seconds > total_downtime_seconds else 0
            kpis["availability_rate"] = (operational_time_seconds / total_time_seconds * 100) if total_time_seconds > 0 else 0.0
            operational_time_hours = operational_time_seconds / 3600
            kpis["failure_rate"] = (num_failures / operational_time_hours) if operational_time_hours > 0 else 0.0
            kpis["mttr"] = (total_downtime_seconds / num_failures) if num_failures > 0 else 0.0
            kpis["mtbf"] = (operational_time_seconds / num_failures) if num_failures > 0 else 0.0

        analytics_data = {
            "events_per_machine": events_per_machine,
            "events_by_type": events_by_type,
            "total_downtime_per_machine": [{"machine": d["machine"], "total_downtime": round(float(d["total_downtime"]) / 3600, 2)} for d in total_downtime_per_machine],
            "downtime_per_machine": downtime_per_machine,
            "canceled_events": canceled_events,
            "avg_downtime_duration": [{"machine": d["machine"], "avg_duration": round(float(d["avg_duration"]), 2)} for d in avg_downtime_duration],
            "kpis": {
                "availability_rate": round(kpis["availability_rate"], 2),
                "failure_rate": round(kpis["failure_rate"], 4),
                "mttr": round(kpis["mttr"], 2),
                "mtbf": round(kpis["mtbf"] / 3600, 2)
            }
        }
        return jsonify(analytics_data)
    except Error as e:
        logger.error(f"Error retrieving analytics: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()

def run_scheduler():
    schedule.every(2).seconds.do(ping_raspberry)
    schedule.every().day.at("00:01").do(check_preventive_maintenance)
    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    init_db()
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    app.run(debug=True, host='0.0.0.0', port=1250)