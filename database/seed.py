import os
import sys
import datetime
from datetime import date, timedelta

# Ensure parent directory is in path for module imports
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from database.db import init_db, get_db_path
import sqlite3

def seed_database(force=False):
    """
    Populates realistic demo data for computers, inventory, complaints, and maintenance.
    Safe to run repeatedly; if data exists and force is False, it will not duplicate entries.
    """
    init_db()
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    cursor = conn.cursor()

    # Check if computers table already has demo data
    cursor.execute("SELECT COUNT(*) FROM computers")
    computer_count = cursor.fetchone()[0]

    if computer_count > 0 and not force:
        print(f"Database already contains {computer_count} computers. Skipping seed (use force=True to re-seed).")
        conn.close()
        return

    if force:
        print("Force flag detected. Clearing existing data...")
        cursor.execute("DELETE FROM maintenance")
        cursor.execute("DELETE FROM complaints")
        cursor.execute("DELETE FROM inventory")
        cursor.execute("DELETE FROM computers")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('computers', 'inventory', 'complaints', 'maintenance')")
        except sqlite3.OperationalError:
            pass
        conn.commit()

    print("Seeding computers...")
    computers_data = [
        # (asset_id, lab_location, status, ip_address, os, processor, ram, storage)
        ("PC-LAB1-01", "Lab 101 - Programming Lab", "Working", "192.168.1.101", "Ubuntu 22.04 LTS", "Intel Core i5-12400 (6 Cores)", "16 GB DDR4", "512 GB NVMe SSD"),
        ("PC-LAB1-02", "Lab 101 - Programming Lab", "Working", "192.168.1.102", "Ubuntu 22.04 LTS", "Intel Core i5-12400 (6 Cores)", "16 GB DDR4", "512 GB NVMe SSD"),
        ("PC-LAB1-03", "Lab 101 - Programming Lab", "Faulty", "192.168.1.103", "Ubuntu 22.04 LTS", "Intel Core i5-12400 (6 Cores)", "16 GB DDR4", "512 GB NVMe SSD"),
        ("PC-LAB1-04", "Lab 101 - Programming Lab", "Under Maintenance", "192.168.1.104", "Windows 11 Pro", "Intel Core i7-11700 (8 Cores)", "32 GB DDR4", "1 TB NVMe SSD"),
        ("PC-LAB2-01", "Lab 102 - Network & AI Lab", "Working", "192.168.2.101", "Ubuntu 24.04 LTS", "AMD Ryzen 7 5700G (8 Cores)", "32 GB DDR4", "1 TB NVMe SSD"),
        ("PC-LAB2-02", "Lab 102 - Network & AI Lab", "Working", "192.168.2.102", "Ubuntu 24.04 LTS", "AMD Ryzen 7 5700G (8 Cores)", "32 GB DDR4", "1 TB NVMe SSD"),
        ("PC-LAB2-03", "Lab 102 - Network & AI Lab", "Faulty", "192.168.2.103", "Windows 11 Pro", "Intel Core i5-11400 (6 Cores)", "16 GB DDR4", "512 GB SSD"),
        ("PC-LAB3-01", "Lab 103 - IoT & Hardware Lab", "Working", "192.168.3.101", "Debian 12", "Intel Core i3-12100 (4 Cores)", "8 GB DDR4", "256 GB SSD"),
    ]

    computer_id_map = {}
    for c in computers_data:
        cursor.execute(
            """INSERT INTO computers (asset_id, lab_location, status, ip_address, os, processor, ram, storage)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            c
        )
        computer_id_map[c[0]] = cursor.lastrowid

    # Reference dates dynamically so month filters (This month, Last month, older) always work cleanly
    today = date.today()
    # First day of this month
    first_of_this_month = today.replace(day=1)
    # First day of last month
    last_month_end = first_of_this_month - timedelta(days=1)
    first_of_last_month = last_month_end.replace(day=1)
    # Two months ago
    two_months_ago = (first_of_last_month - timedelta(days=1)).replace(day=15)

    this_month_date = today.strftime("%Y-%m-%d")
    last_month_date = (first_of_last_month + timedelta(days=10)).strftime("%Y-%m-%d")
    older_date = two_months_ago.strftime("%Y-%m-%d")

    print("Seeding inventory items...")
    inventory_data = [
        # (item_name, category, quantity, serial_number, computer_id, location, status, purchase_date)
        ("Dell UltraSharp 24 Monitor", "Monitor", 1, "SN-MON-9081", computer_id_map["PC-LAB1-01"], "Lab 101 - Programming Lab", "In-Use", this_month_date),
        ("Dell UltraSharp 24 Monitor", "Monitor", 1, "SN-MON-9082", computer_id_map["PC-LAB1-02"], "Lab 101 - Programming Lab", "In-Use", this_month_date),
        ("Dell UltraSharp 24 Monitor", "Monitor", 1, "SN-MON-9083", computer_id_map["PC-LAB1-03"], "Lab 101 - Programming Lab", "Damaged", last_month_date),
        ("Logitech K120 USB Keyboard", "Keyboard", 1, "SN-KB-1102", computer_id_map["PC-LAB1-01"], "Lab 101 - Programming Lab", "In-Use", this_month_date),
        ("Logitech B100 Optical Mouse", "Mouse", 1, "SN-MS-3310", computer_id_map["PC-LAB1-01"], "Lab 101 - Programming Lab", "In-Use", this_month_date),
        ("Logitech K120 USB Keyboard (Spare)", "Keyboard", 5, "SN-KB-SPARE-BATCH1", None, "Lab 101 Storage Rack", "Available", last_month_date),
        ("Logitech B100 Mouse (Spare)", "Mouse", 8, "SN-MS-SPARE-BATCH1", None, "Lab 101 Storage Rack", "Available", older_date),
        ("Cisco Catalyst 24-Port Gigabit Switch", "Networking", 1, "SN-CS-2960-91", None, "Lab 102 Server Rack", "In-Use", older_date),
        ("Epson EB-X49 HDMI Projector", "Projector", 1, "SN-EP-88210", None, "Lab 101 Ceiling", "In-Use", last_month_date),
        ("HP LaserJet Pro MFP 4104dw", "Printer", 1, "SN-HP-4104-A", None, "Lab 102 Tech Desk", "Under Maintenance", this_month_date),
        ("Legacy Serial DB9 Cable Pack", "Other", 4, None, None, "Lab 103 Cabinet B", "Available", None), # No purchase date
        ("APC Smart-UPS 1500VA", "UPS", 1, "SN-APC-1500-X", None, "Lab 102 Server Rack", "In-Use", None), # No purchase date
    ]

    inventory_id_map = {}
    for idx, item in enumerate(inventory_data):
        cursor.execute(
            """INSERT INTO inventory (item_name, category, quantity, serial_number, computer_id, location, status, purchase_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            item
        )
        inventory_id_map[idx + 1] = cursor.lastrowid

    print("Seeding complaints...")
    complaints_data = [
        # (title, description, target_type, computer_id, inventory_id, reporter_name, reporter_contact, priority, status, resolution_notes, resolved_at)
        (
            "Blue Screen of Death on Boot",
            "System fails to start Ubuntu, throwing kernel panic and disk read error on sector 0x44.",
            "computer",
            computer_id_map["PC-LAB1-03"],
            None,
            "Aarav Sharma (B.Tech IT Year 1)",
            "aarav.s@college.edu",
            "High",
            "Pending",
            None,
            None
        ),
        (
            "Display flicker and horizontal lines",
            "Monitor flickers intermittently whenever brightness exceeds 60%.",
            "inventory",
            None,
            inventory_id_map[3], # Damaged Dell Monitor
            "Neha Gupta (B.Tech CSE Year 2)",
            "neha.g@college.edu",
            "Medium",
            "In Progress",
            "Assigned to Lab Assistant for cable test.",
            None
        ),
        (
            "Power supply tripping after 10 mins",
            "The desktop turns off automatically after running simulations.",
            "computer",
            computer_id_map["PC-LAB1-04"],
            None,
            "Rohan Verma (Faculty In-Charge)",
            "rohan.v@college.edu",
            "High",
            "In Progress",
            "Hardware diagnostic in progress; SMPS replacement ordered.",
            None
        ),
        (
            "OS Update boot loop resolved",
            "System was stuck on Grub boot menu after kernel update.",
            "computer",
            computer_id_map["PC-LAB1-01"],
            None,
            "Kavya Patel (Student)",
            "kavya.p@college.edu",
            "Low",
            "Resolved",
            "Reconfigured Grub bootloader from live USB. System working normally.",
            this_month_date + " 10:30:00"
        ),
        (
            "Stuck Spacebar key on keyboard",
            "Spacebar key requires heavy pressure to register input.",
            "inventory",
            None,
            inventory_id_map[4], # Keyboard
            "Tanvi Mehta (Student)",
            "tanvi@college.edu",
            "Low",
            "Resolved",
            "Keycap removed and switch cleaned with isopropyl alcohol. Fully responsive.",
            last_month_date + " 14:15:00"
        )
    ]

    complaint_ids = []
    for comp in complaints_data:
        cursor.execute(
            """INSERT INTO complaints (title, description, target_type, computer_id, inventory_id, reporter_name, reporter_contact, priority, status, resolution_notes, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            comp
        )
        complaint_ids.append(cursor.lastrowid)

    print("Seeding maintenance records...")
    maintenance_data = [
        # (target_type, computer_id, inventory_id, complaint_id, work_type, description, performed by, cost, maintenance_date)
        (
            "computer",
            computer_id_map["PC-LAB1-04"],
            None,
            complaint_ids[2], # Link to power supply issue
            "Repair",
            "Disassembled cabinet, checked Corsair 550W power supply, detected capacitor bulge.",
            "Vikram Singh (Hardware Tech)",
            1200.0,
            this_month_date
        ),
        (
            "inventory",
            None,
            inventory_id_map[9], # Projector
            None,
            "Cleaning",
            "Routine optical lens cleaning, air filter replacement, lamp hour counter reset.",
            "Vikram Singh (Hardware Tech)",
            450.0,
            last_month_date
        ),
        (
            "computer",
            computer_id_map["PC-LAB1-01"],
            None,
            complaint_ids[3], # Link to boot loop complaint
            "Routine Check",
            "Bootloader recovery, kernel cleanup, and RAM diagnostic pass.",
            "K. Sasank (Lab Admin)",
            0.0,
            older_date
        )
    ]

    for m in maintenance_data:
        cursor.execute(
            """INSERT INTO maintenance (target_type, computer_id, inventory_id, complaint_id, work_type, description, performed_by, cost, maintenance_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            m
        )

    conn.commit()
    conn.close()
    print("Demo database seeded successfully!")

if __name__ == '__main__':
    force_run = '--force' in sys.argv
    seed_database(force=force_run)
