import unittest
import os
import sys
import tempfile
from datetime import date, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app
from database.db import init_db, query_db, execute_db
from database.seed import seed_database

class SmartLabTestCase(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.test_db_path = tempfile.mkstemp(suffix='.sqlite3')
        self.app = create_app({
            'TESTING': True,
            'DATABASE': self.test_db_path,
            'WTF_CSRF_ENABLED': False
        })
        with self.app.app_context():
            init_db(self.app)
            seed_database(force=True)

        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        try:
            os.unlink(self.test_db_path)
        except OSError:
            pass

    # -------------------------------------------------------------
    # 1. Computer Management Tests
    # -------------------------------------------------------------
    def test_computers_list(self):
        res = self.client.get('/computers')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'PC-LAB1-01', res.data)
        self.assertIn(b'Computer Lab Systems', res.data)

    def test_computers_add_success(self):
        res = self.client.post('/computers/new', data={
            'asset_id': 'PC-TEST-99',
            'lab_location': 'Lab 104 - Testing Lab',
            'status': 'Working',
            'ip_address': '192.168.4.99',
            'os': 'Fedora 40',
            'processor': 'AMD Ryzen 5',
            'ram': '16 GB',
            'storage': '512 GB SSD'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'PC-TEST-99', res.data)
        self.assertIn(b'registered successfully', res.data)

    def test_computers_duplicate_asset_id_rejected(self):
        res = self.client.post('/computers/new', data={
            'asset_id': 'PC-LAB1-01',
            'lab_location': 'Duplicate Test Lab',
            'status': 'Working'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'already exists', res.data)

    def test_computers_detail_and_qr(self):
        with self.app.app_context():
            comp = query_db("SELECT id, asset_id FROM computers WHERE asset_id = 'PC-LAB1-01'", one=True)
            comp_id = comp['id']

        res = self.client.get(f'/computers/{comp_id}')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'PC-LAB1-01', res.data)
        self.assertIn(b'System Specifications', res.data)

        # Check QR code endpoint
        qr_res = self.client.get(f'/qr/computer/{comp_id}')
        self.assertEqual(qr_res.status_code, 200)
        self.assertTrue(qr_res.content_type.startswith('image/svg+xml'))
        self.assertIn(b'<svg', qr_res.data)

    def test_computers_edit(self):
        with self.app.app_context():
            comp = query_db("SELECT id FROM computers WHERE asset_id = 'PC-LAB1-01'", one=True)
            comp_id = comp['id']

        res = self.client.post(f'/computers/{comp_id}/edit', data={
            'asset_id': 'PC-LAB1-01',
            'lab_location': 'Lab 101 - Renamed Lab',
            'status': 'Working',
            'ip_address': '192.168.1.200',
            'os': 'Ubuntu 24.04 LTS',
            'processor': 'Intel Core i9',
            'ram': '32 GB',
            'storage': '2 TB NVMe'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Renamed Lab', res.data)
        self.assertIn(b'Intel Core i9', res.data)

    def test_computers_delete(self):
        with self.app.app_context():
            cid, _ = execute_db("INSERT INTO computers (asset_id, lab_location, status) VALUES ('PC-DEL-01', 'Lab Temp', 'Working')")
        
        del_res = self.client.post(f'/computers/{cid}/delete', follow_redirects=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertIn(b'was deleted', del_res.data)

    # -------------------------------------------------------------
    # 2. Inventory Management Tests
    # -------------------------------------------------------------
    def test_inventory_list_and_filters(self):
        res = self.client.get('/inventory')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Dell UltraSharp 24 Monitor', res.data)
        
        # Test month filter: this_month
        res_this = self.client.get('/inventory?month=this_month')
        self.assertEqual(res_this.status_code, 200)
        self.assertIn(b'Dell UltraSharp 24 Monitor', res_this.data)

        # Test month filter: no_date
        res_nodate = self.client.get('/inventory?month=no_date')
        self.assertEqual(res_nodate.status_code, 200)
        self.assertIn(b'Legacy Serial DB9 Cable Pack', res_nodate.data)

    def test_inventory_add_and_detail(self):
        res = self.client.post('/inventory/new', data={
            'item_name': 'Raspberry Pi 4 Model B',
            'category': 'Other',
            'quantity': 3,
            'serial_number': 'SN-RPI4-771',
            'location': 'Lab 103 - IoT Lab',
            'status': 'Available',
            'purchase_date': date.today().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Raspberry Pi 4 Model B', res.data)

        with self.app.app_context():
            item = query_db("SELECT id FROM inventory WHERE serial_number = 'SN-RPI4-771'", one=True)
            item_id = item['id']

        # Check inventory QR code
        qr_res = self.client.get(f'/qr/inventory/{item_id}')
        self.assertEqual(qr_res.status_code, 200)
        self.assertTrue(qr_res.content_type.startswith('image/svg+xml'))

    # -------------------------------------------------------------
    # 3. Student Issue-Reporting Portal Tests
    # -------------------------------------------------------------
    def test_student_report_computer_success(self):
        with self.app.app_context():
            comp = query_db("SELECT id FROM computers LIMIT 1", one=True)
            comp_id = comp['id']

        res = self.client.post('/student', data={
            'target_type': 'computer',
            'computer_id': comp_id,
            'inventory_id': '',
            'title': 'Student Test: Mouse not clicking',
            'description': 'Left click button is not registering any response.',
            'priority': 'Medium',
            'reporter_name': 'Amit Kumar (B.Tech IT 1st Year)',
            'reporter_contact': 'amit.k@college.edu'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Issue Reported Successfully!', res.data)
        self.assertIn(b'Return to Home', res.data)
        self.assertIn(b'Report Another Issue', res.data)

        # Verify it appears in Admin complaints
        comp_res = self.client.get('/complaints')
        self.assertIn(b'Student Test: Mouse not clicking', comp_res.data)
        self.assertIn(b'Amit Kumar', comp_res.data)

    def test_student_report_inventory_success(self):
        with self.app.app_context():
            inv = query_db("SELECT id FROM inventory LIMIT 1", one=True)
            inv_id = inv['id']

        res = self.client.post('/student', data={
            'target_type': 'inventory',
            'computer_id': '',
            'inventory_id': inv_id,
            'title': 'Student Test: HDMI Projector Flickering',
            'description': 'HDMI input drops every 2 minutes during seminar.',
            'priority': 'High',
            'reporter_name': 'Priya Sen (Student)',
            'reporter_contact': 'priya@college.edu'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Issue Reported Successfully!', res.data)

    def test_student_report_validation_failure(self):
        res = self.client.post('/student', data={
            'target_type': 'computer',
            'computer_id': 1,
            'title': '',
            'description': '',
            'priority': 'Low',
            'reporter_name': ''
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Please fill in the Issue Title', res.data)

    # -------------------------------------------------------------
    # 4. Complaint Management & Asset Status Integrity Tests
    # -------------------------------------------------------------
    def test_complaint_status_resolution_and_integrity(self):
        with self.app.app_context():
            # Get the complaint on PC-LAB1-03
            c = query_db("SELECT id, computer_id FROM complaints WHERE title = 'Blue Screen of Death on Boot'", one=True)
            cid = c['id']
            comp_id = c['computer_id']

        # Resolve this complaint
        res = self.client.post(f'/complaints/{cid}/status', data={
            'status': 'Resolved',
            'resolution_notes': 'Replaced damaged NVMe SSD and restored clean Ubuntu image.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'resolved', res.data.lower())

        # Verify computer status was restored to 'Working' because it had no other open complaints
        comp_res = self.client.get(f'/computers/{comp_id}')
        self.assertIn(b'Working', comp_res.data)

    def test_computer_integrity_guard_multiple_complaints(self):
        with self.app.app_context():
            comp = query_db("SELECT id FROM computers LIMIT 1", one=True)
            cid = comp['id']
            execute_db("INSERT INTO complaints (title, description, target_type, computer_id, reporter_name, priority, status) VALUES ('Issue A', 'Desc A', 'computer', ?, 'Rep A', 'Medium', 'Pending')", (cid,))
            cid_b, _ = execute_db("INSERT INTO complaints (title, description, target_type, computer_id, reporter_name, priority, status) VALUES ('Issue B', 'Desc B', 'computer', ?, 'Rep B', 'High', 'Pending')", (cid,))
            execute_db("UPDATE computers SET status = 'Faulty' WHERE id = ?", (cid,))

        # Now resolve Issue B (Issue A is STILL pending!)
        res = self.client.post(f'/complaints/{cid_b}/status', data={
            'status': 'Resolved',
            'resolution_notes': 'Fixed issue B.'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'unresolved issue', res.data.lower())

        # Verify computer is NOT marked as Working because Issue A is still unresolved!
        comp_res = self.client.get(f'/computers/{cid}')
        self.assertNotIn(b'badge-working fs-6', comp_res.data)

    # -------------------------------------------------------------
    # 5. Maintenance Management Tests
    # -------------------------------------------------------------
    def test_maintenance_list_and_filters(self):
        res = self.client.get('/maintenance')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Lab Maintenance', res.data)
        self.assertIn(b'Repair', res.data)

    def test_maintenance_add_and_edit(self):
        with self.app.app_context():
            comp = query_db("SELECT id FROM computers LIMIT 1", one=True)
            comp_id = comp['id']
            m = query_db("SELECT id FROM maintenance LIMIT 1", one=True)
            m_id = m['id']

        # Add maintenance record
        res = self.client.post('/maintenance/new', data={
            'target_type': 'computer',
            'computer_id': comp_id,
            'work_type': 'Upgrade',
            'description': 'RAM upgraded from 16GB to 32GB Kingston Fury.',
            'performed_by': 'Vikram Singh (Hardware Tech)',
            'cost': 4500.0,
            'maintenance_date': date.today().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Maintenance record created successfully', res.data)

        # Edit maintenance record
        edit_res = self.client.post(f'/maintenance/{m_id}/edit', data={
            'target_type': 'computer',
            'computer_id': comp_id,
            'work_type': 'Repair',
            'description': 'Updated repair notes: SMPS replaced with Corsair CV550.',
            'performed_by': 'Vikram Singh (Hardware Tech)',
            'cost': 1500.0,
            'maintenance_date': date.today().strftime('%Y-%m-%d')
        }, follow_redirects=True)
        self.assertEqual(edit_res.status_code, 200)
        self.assertIn(b'Corsair CV550', edit_res.data)

    # -------------------------------------------------------------
    # 6. Dashboard Metrics Calculation Verification
    # -------------------------------------------------------------
    def test_dashboard_metrics(self):
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Lab Operations Dashboard', res.data)
        self.assertIn(b'Computer Lab Health', res.data)
        self.assertIn(b'Hardware & Peripheral Stock', res.data)
        self.assertIn(b'Fault Complaints Status', res.data)
        self.assertIn(b'Recent Complaints & Fault Logs', res.data)

if __name__ == '__main__':
    unittest.main()
