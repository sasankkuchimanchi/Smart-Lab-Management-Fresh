import os
import io
import datetime
from datetime import date, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, Response, abort
from werkzeug.middleware.proxy_fix import ProxyFix
import qrcode
import qrcode.image.svg

from database.db import get_db, close_db, init_db, query_db, execute_db, get_db_path, has_unresolved_computer_issues
from database.seed import seed_database

INVENTORY_CATEGORIES = ['Monitor', 'Keyboard', 'Mouse', 'Projector', 'Networking', 'Printer', 'UPS', 'Other']
MAINTENANCE_WORK_TYPES = ['Repair', 'Upgrade', 'Routine Check', 'Replacement', 'Cleaning']

def get_month_ranges():
    """Returns (this_month_str, last_month_str) in 'YYYY-MM' format."""
    today = date.today()
    this_month = today.strftime('%Y-%m')
    first_of_this_month = today.replace(day=1)
    last_month_end = first_of_this_month - timedelta(days=1)
    last_month = last_month_end.strftime('%Y-%m')
    return this_month, last_month

def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY='smart-lab-dev-secret-key-change-in-production',
        DATABASE=os.path.join(app.instance_path, 'smart_lab.sqlite3'),
    )

    if test_config:
        app.config.update(test_config)

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    # Enable proxy headers support for cloud platforms like Render
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    app.teardown_appcontext(close_db)

    @app.template_filter('format_date')
    def format_date(value):
        if not value:
            return 'N/A'
        if hasattr(value, 'strftime'):
            return value.strftime('%Y-%m-%d')
        return str(value)[:10]

    # Initialize and seed database if it doesn't exist
    db_file = os.path.join(app.instance_path, 'smart_lab.sqlite3')
    if not os.path.exists(db_file):
        with app.app_context():
            init_db()
            seed_database()

    # -------------------------------------------------------------
    # QR Code Generator Route (Pure SVG)
    # -------------------------------------------------------------
    @app.route('/qr/<string:item_type>/<int:item_id>')
    def generate_qr(item_type, item_id):
        """Generates an SVG QR code linking directly to the Student Fault Reporting Portal."""
        if item_type == 'computer':
            item = query_db("SELECT id, asset_id FROM computers WHERE id = ?", (item_id,), one=True)
            if not item:
                abort(404)
            # Direct link so any smartphone camera opens the student portal with this computer selected!
            qr_content = url_for('student_report', computer_id=item_id, _external=True)
        elif item_type == 'inventory':
            item = query_db("SELECT id, item_name FROM inventory WHERE id = ?", (item_id,), one=True)
            if not item:
                abort(404)
            # Direct link so any smartphone camera opens the student portal with this item selected!
            qr_content = url_for('student_report', inventory_id=item_id, _external=True)
        else:
            abort(400)

        factory = qrcode.image.svg.SvgImage
        img = qrcode.make(qr_content, image_factory=factory)
        buffer = io.BytesIO()
        img.save(buffer)
        buffer.seek(0)
        return Response(buffer.getvalue(), mimetype='image/svg+xml')

    # -------------------------------------------------------------
    # Root Route
    # -------------------------------------------------------------
    @app.route('/')
    def index():
        return redirect(url_for('dashboard'))

    # -------------------------------------------------------------
    # Dashboard View (Live SQLite Metrics & Recent Complaints)
    # -------------------------------------------------------------
    @app.route('/dashboard')
    def dashboard():
        comp_stats = query_db("""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN status = 'Working' THEN 1 ELSE 0 END), 0) as working,
                COALESCE(SUM(CASE WHEN status = 'Faulty' THEN 1 ELSE 0 END), 0) as faulty,
                COALESCE(SUM(CASE WHEN status = 'Under Maintenance' THEN 1 ELSE 0 END), 0) as under_maintenance
            FROM computers
        """, one=True)

        inv_stats = query_db("""
            SELECT
                COUNT(*) as total_items,
                COALESCE(SUM(quantity), 0) as total_quantity,
                COALESCE(SUM(CASE WHEN status = 'Available' THEN quantity ELSE 0 END), 0) as available_qty,
                COALESCE(SUM(CASE WHEN status = 'In-Use' THEN quantity ELSE 0 END), 0) as in_use_qty,
                COALESCE(SUM(CASE WHEN status = 'Damaged' THEN quantity ELSE 0 END), 0) as damaged_qty,
                COALESCE(SUM(CASE WHEN status = 'Under Maintenance' THEN quantity ELSE 0 END), 0) as maintenance_qty
            FROM inventory
        """, one=True)

        complaint_stats = query_db("""
            SELECT
                COUNT(*) as total,
                COALESCE(SUM(CASE WHEN status = 'Pending' THEN 1 ELSE 0 END), 0) as pending,
                COALESCE(SUM(CASE WHEN status = 'In Progress' THEN 1 ELSE 0 END), 0) as in_progress,
                COALESCE(SUM(CASE WHEN status IN ('Pending', 'In Progress') THEN 1 ELSE 0 END), 0) as open,
                COALESCE(SUM(CASE WHEN status = 'Resolved' THEN 1 ELSE 0 END), 0) as resolved
            FROM complaints
        """, one=True)

        recent_complaints = query_db("""
            SELECT
                c.id, c.title, c.description, c.target_type, c.priority, c.status,
                c.reporter_name, c.created_at,
                comp.id as computer_id, comp.asset_id as computer_asset_id, comp.lab_location as computer_lab,
                inv.id as inventory_id, inv.item_name as inventory_name, inv.serial_number as inventory_sn, inv.location as inventory_location
            FROM complaints c
            LEFT JOIN computers comp ON c.computer_id = comp.id
            LEFT JOIN inventory inv ON c.inventory_id = inv.id
            ORDER BY c.created_at DESC, c.id DESC
            LIMIT 6
        """)

        return render_template(
            'dashboard.html',
            comp_stats=comp_stats,
            inv_stats=inv_stats,
            complaint_stats=complaint_stats,
            recent_complaints=recent_complaints
        )

    # -------------------------------------------------------------
    # Module 1: Computer Management
    # -------------------------------------------------------------
    @app.route('/computers')
    def computers_list():
        search_query = request.args.get('q', '').strip()
        status_filter = request.args.get('status', '').strip()

        sql = "SELECT * FROM computers WHERE 1=1"
        params = []

        if search_query:
            sql += " AND (asset_id LIKE ? OR lab_location LIKE ? OR os LIKE ? OR processor LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term, term])

        if status_filter:
            sql += " AND status = ?"
            params.append(status_filter)

        sql += " ORDER BY asset_id ASC"
        computers = query_db(sql, params)

        return render_template(
            'computers/index.html',
            computers=computers,
            search_query=search_query,
            current_status=status_filter
        )

    @app.route('/computers/new', methods=['GET', 'POST'])
    def computers_new():
        if request.method == 'POST':
            asset_id = request.form.get('asset_id', '').strip()
            lab_location = request.form.get('lab_location', '').strip()
            status = request.form.get('status', 'Working').strip()
            ip_address = request.form.get('ip_address', '').strip() or None
            os_name = request.form.get('os', '').strip() or None
            processor = request.form.get('processor', '').strip() or None
            ram = request.form.get('ram', '').strip() or None
            storage = request.form.get('storage', '').strip() or None

            # Validation
            if not asset_id or not lab_location:
                flash("Asset ID and Lab Location are required fields.", "danger")
                return render_template('computers/form.html', is_edit=False, computer={})

            # Duplicate Asset ID check
            existing = query_db("SELECT id FROM computers WHERE asset_id = ?", (asset_id,), one=True)
            if existing:
                flash(f"Error: A computer with Asset ID '{asset_id}' already exists. Asset IDs must be unique.", "danger")
                return render_template('computers/form.html', is_edit=False, computer=request.form)

            execute_db("""
                INSERT INTO computers (asset_id, lab_location, status, ip_address, os, processor, ram, storage)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (asset_id, lab_location, status, ip_address, os_name, processor, ram, storage))

            flash(f"Computer '{asset_id}' registered successfully!", "success")
            return redirect(url_for('computers_list'))

        return render_template('computers/form.html', is_edit=False, computer={})

    @app.route('/computers/<int:id>')
    def computers_detail(id):
        computer = query_db("SELECT * FROM computers WHERE id = ?", (id,), one=True)
        if not computer:
            abort(404)

        linked_inventory = query_db("SELECT * FROM inventory WHERE computer_id = ? ORDER BY category, item_name", (id,))
        complaints = query_db("SELECT * FROM complaints WHERE computer_id = ? ORDER BY id DESC", (id,))
        maintenance_records = query_db("SELECT * FROM maintenance WHERE computer_id = ? ORDER BY maintenance_date DESC, id DESC", (id,))

        return render_template(
            'computers/detail.html',
            computer=computer,
            linked_inventory=linked_inventory,
            complaints=complaints,
            maintenance_records=maintenance_records
        )

    @app.route('/computers/<int:id>/edit', methods=['GET', 'POST'])
    def computers_edit(id):
        computer = query_db("SELECT * FROM computers WHERE id = ?", (id,), one=True)
        if not computer:
            abort(404)

        if request.method == 'POST':
            asset_id = request.form.get('asset_id', '').strip()
            lab_location = request.form.get('lab_location', '').strip()
            status = request.form.get('status', 'Working').strip()
            ip_address = request.form.get('ip_address', '').strip() or None
            os_name = request.form.get('os', '').strip() or None
            processor = request.form.get('processor', '').strip() or None
            ram = request.form.get('ram', '').strip() or None
            storage = request.form.get('storage', '').strip() or None

            if not asset_id or not lab_location:
                flash("Asset ID and Lab Location are required.", "danger")
                return render_template('computers/form.html', is_edit=True, computer=computer)

            # Check duplicate asset ID excluding current computer
            existing = query_db("SELECT id FROM computers WHERE asset_id = ? AND id != ?", (asset_id, id), one=True)
            if existing:
                flash(f"Error: Asset ID '{asset_id}' is already assigned to another computer.", "danger")
                return render_template('computers/form.html', is_edit=True, computer=computer)

            # SYSTEM INTEGRITY RULE: Do not allow marking computer as Working if it has active open complaints
            if status == 'Working':
                has_issues, reason = has_unresolved_computer_issues(id)
                if has_issues:
                    flash(f"Integrity Guard: Cannot set status to 'Working'. {reason}. Please resolve active complaints before marking operational.", "warning")
                    status = computer['status'] # Keep previous non-working status

            execute_db("""
                UPDATE computers
                SET asset_id = ?, lab_location = ?, status = ?, ip_address = ?, os = ?, processor = ?, ram = ?, storage = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (asset_id, lab_location, status, ip_address, os_name, processor, ram, storage, id))

            flash(f"Computer '{asset_id}' updated successfully.", "success")
            return redirect(url_for('computers_detail', id=id))

        return render_template('computers/form.html', is_edit=True, computer=computer)

    @app.route('/computers/<int:id>/delete', methods=['POST'])
    def computers_delete(id):
        computer = query_db("SELECT asset_id FROM computers WHERE id = ?", (id,), one=True)
        if not computer:
            abort(404)

        execute_db("DELETE FROM computers WHERE id = ?", (id,))
        flash(f"Computer '{computer['asset_id']}' was deleted.", "info")
        return redirect(url_for('computers_list'))

    # -------------------------------------------------------------
    # Module 2: Inventory Management
    # -------------------------------------------------------------
    @app.route('/inventory')
    def inventory_list():
        month_filter = request.args.get('month', 'all').strip()
        category_filter = request.args.get('category', '').strip()
        search_query = request.args.get('q', '').strip()

        this_month, last_month = get_month_ranges()

        # Fetch distinct months with records for dynamic filter pills
        month_rows = query_db("""
            SELECT DISTINCT strftime('%Y-%m', purchase_date) as ym
            FROM inventory
            WHERE purchase_date IS NOT NULL AND purchase_date != ''
            ORDER BY ym DESC
        """)
        available_months = [r['ym'] for r in month_rows if r['ym'] not in (this_month, last_month)]

        sql = """
            SELECT inv.*, c.asset_id as computer_asset_id
            FROM inventory inv
            LEFT JOIN computers c ON inv.computer_id = c.id
            WHERE 1=1
        """
        params = []

        # Month filtering logic
        if month_filter == 'this_month':
            sql += " AND strftime('%Y-%m', inv.purchase_date) = ?"
            params.append(this_month)
        elif month_filter == 'last_month':
            sql += " AND strftime('%Y-%m', inv.purchase_date) = ?"
            params.append(last_month)
        elif month_filter == 'no_date':
            sql += " AND (inv.purchase_date IS NULL OR inv.purchase_date = '')"
        elif month_filter != 'all' and month_filter:
            sql += " AND strftime('%Y-%m', inv.purchase_date) = ?"
            params.append(month_filter)

        if category_filter:
            sql += " AND inv.category = ?"
            params.append(category_filter)

        if search_query:
            sql += " AND (inv.item_name LIKE ? OR inv.serial_number LIKE ? OR inv.location LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term])

        sql += " ORDER BY inv.id DESC"
        items = query_db(sql, params)

        return render_template(
            'inventory/index.html',
            items=items,
            current_month=month_filter,
            current_category=category_filter,
            search_query=search_query,
            categories=INVENTORY_CATEGORIES,
            available_months=available_months
        )

    @app.route('/inventory/new', methods=['GET', 'POST'])
    def inventory_new():
        computers = query_db("SELECT id, asset_id, lab_location FROM computers ORDER BY asset_id")

        if request.method == 'POST':
            item_name = request.form.get('item_name', '').strip()
            category = request.form.get('category', '').strip()
            quantity = request.form.get('quantity', 1, type=int)
            serial_number = request.form.get('serial_number', '').strip() or None
            computer_id = request.form.get('computer_id', type=int) or None
            location = request.form.get('location', '').strip()
            status = request.form.get('status', 'Available').strip()
            purchase_date = request.form.get('purchase_date', '').strip() or None

            if not item_name or not category or not location:
                flash("Item name, category, and location are required.", "danger")
                return render_template('inventory/form.html', is_edit=False, item={}, computers=computers, categories=INVENTORY_CATEGORIES)

            if quantity < 0:
                flash("Quantity cannot be negative.", "danger")
                return render_template('inventory/form.html', is_edit=False, item=request.form, computers=computers, categories=INVENTORY_CATEGORIES)

            execute_db("""
                INSERT INTO inventory (item_name, category, quantity, serial_number, computer_id, location, status, purchase_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (item_name, category, quantity, serial_number, computer_id, location, status, purchase_date))

            flash(f"Inventory item '{item_name}' added successfully.", "success")
            return redirect(url_for('inventory_list'))

        return render_template('inventory/form.html', is_edit=False, item={}, computers=computers, categories=INVENTORY_CATEGORIES)

    @app.route('/inventory/<int:id>')
    def inventory_detail(id):
        item = query_db("""
            SELECT inv.*, c.asset_id as computer_asset_id
            FROM inventory inv
            LEFT JOIN computers c ON inv.computer_id = c.id
            WHERE inv.id = ?
        """, (id,), one=True)
        if not item:
            abort(404)

        complaints = query_db("SELECT * FROM complaints WHERE inventory_id = ? ORDER BY id DESC", (id,))
        maintenance_records = query_db("SELECT * FROM maintenance WHERE inventory_id = ? ORDER BY maintenance_date DESC, id DESC", (id,))

        return render_template(
            'inventory/detail.html',
            item=item,
            complaints=complaints,
            maintenance_records=maintenance_records
        )

    @app.route('/inventory/<int:id>/edit', methods=['GET', 'POST'])
    def inventory_edit(id):
        item = query_db("SELECT * FROM inventory WHERE id = ?", (id,), one=True)
        if not item:
            abort(404)

        computers = query_db("SELECT id, asset_id, lab_location FROM computers ORDER BY asset_id")

        if request.method == 'POST':
            item_name = request.form.get('item_name', '').strip()
            category = request.form.get('category', '').strip()
            quantity = request.form.get('quantity', 1, type=int)
            serial_number = request.form.get('serial_number', '').strip() or None
            computer_id = request.form.get('computer_id', type=int) or None
            location = request.form.get('location', '').strip()
            status = request.form.get('status', 'Available').strip()
            purchase_date = request.form.get('purchase_date', '').strip() or None

            if not item_name or not category or not location:
                flash("Item name, category, and location are required.", "danger")
                return render_template('inventory/form.html', is_edit=True, item=item, computers=computers, categories=INVENTORY_CATEGORIES)

            execute_db("""
                UPDATE inventory
                SET item_name = ?, category = ?, quantity = ?, serial_number = ?, computer_id = ?, location = ?, status = ?, purchase_date = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (item_name, category, quantity, serial_number, computer_id, location, status, purchase_date, id))

            flash(f"Item '{item_name}' updated successfully.", "success")
            return redirect(url_for('inventory_detail', id=id))

        return render_template('inventory/form.html', is_edit=True, item=item, computers=computers, categories=INVENTORY_CATEGORIES)

    @app.route('/inventory/<int:id>/delete', methods=['POST'])
    def inventory_delete(id):
        item = query_db("SELECT item_name FROM inventory WHERE id = ?", (id,), one=True)
        if not item:
            abort(404)

        execute_db("DELETE FROM inventory WHERE id = ?", (id,))
        flash(f"Inventory item '{item['item_name']}' removed.", "info")
        return redirect(url_for('inventory_list'))

    # -------------------------------------------------------------
    # Module 3: Student Issue-Reporting Portal
    # -------------------------------------------------------------
    @app.route('/student', methods=['GET', 'POST'])
    def student_report():
        computers = query_db("SELECT id, asset_id, lab_location, status FROM computers ORDER BY asset_id")
        inventory_items = query_db("SELECT id, item_name, category, serial_number, location FROM inventory ORDER BY item_name")

        if request.method == 'POST':
            target_type = request.form.get('target_type', 'computer').strip()
            computer_id = request.form.get('computer_id', type=int) or None
            inventory_id = request.form.get('inventory_id', type=int) or None
            title = request.form.get('title', '').strip()
            description = request.form.get('description', '').strip()
            priority = request.form.get('priority', 'Medium').strip()
            reporter_name = request.form.get('reporter_name', '').strip()
            reporter_contact = request.form.get('reporter_contact', '').strip() or None

            # 1. Basic text validation
            if not title or not description or not reporter_name:
                flash("Please fill in the Issue Title, Detailed Description, and your Name.", "danger")
                return render_template('student/report.html', computers=computers, inventory_items=inventory_items)

            # 2. Enforce selection of EXACTLY ONE computer OR inventory item
            if target_type == 'computer':
                inventory_id = None
                if not computer_id:
                    flash("Please select the computer system that has a problem.", "danger")
                    return render_template('student/report.html', computers=computers, inventory_items=inventory_items)
            elif target_type == 'inventory':
                computer_id = None
                if not inventory_id:
                    flash("Please select the peripheral or equipment that is faulty.", "danger")
                    return render_template('student/report.html', computers=computers, inventory_items=inventory_items)
            else:
                flash("Invalid asset type selection.", "danger")
                return render_template('student/report.html', computers=computers, inventory_items=inventory_items)

            # Insert complaint with status 'Pending'
            complaint_id, _ = execute_db("""
                INSERT INTO complaints (title, description, target_type, computer_id, inventory_id, reporter_name, reporter_contact, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Pending')
            """, (title, description, target_type, computer_id, inventory_id, reporter_name, reporter_contact, priority))

            # Automatically update the linked asset status to Faulty / Damaged
            if target_type == 'computer' and computer_id:
                # If computer was 'Working', mark as 'Faulty'
                execute_db("UPDATE computers SET status = 'Faulty', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Working'", (computer_id,))
            elif target_type == 'inventory' and inventory_id:
                execute_db("UPDATE inventory SET status = 'Damaged', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('Available', 'In-Use')", (inventory_id,))

            return redirect(url_for('student_confirmation', id=complaint_id))

        selected_computer_id = request.args.get('computer_id', type=int)
        selected_inventory_id = request.args.get('inventory_id', type=int)
        preselected_computer = None
        preselected_inventory = None

        if selected_computer_id:
            preselected_computer = query_db("SELECT * FROM computers WHERE id = ?", (selected_computer_id,), one=True)
        if selected_inventory_id:
            preselected_inventory = query_db("SELECT * FROM inventory WHERE id = ?", (selected_inventory_id,), one=True)

        return render_template(
            'student/report.html',
            computers=computers,
            inventory_items=inventory_items,
            selected_computer_id=selected_computer_id,
            selected_inventory_id=selected_inventory_id,
            preselected_computer=preselected_computer,
            preselected_inventory=preselected_inventory
        )

    @app.route('/student/confirmation/<int:id>')
    def student_confirmation(id):
        complaint = query_db("""
            SELECT c.*,
                   comp.asset_id as computer_asset_id, comp.lab_location as computer_lab,
                   inv.item_name as inventory_name, inv.serial_number as inventory_sn
            FROM complaints c
            LEFT JOIN computers comp ON c.computer_id = comp.id
            LEFT JOIN inventory inv ON c.inventory_id = inv.id
            WHERE c.id = ?
        """, (id,), one=True)
        if not complaint:
            abort(404)

        return render_template('student/confirmation.html', complaint=complaint)

    # -------------------------------------------------------------
    # Module 4: Complaint Management
    # -------------------------------------------------------------
    @app.route('/complaints')
    def complaints_list():
        status_filter = request.args.get('status', 'all').strip()
        search_query = request.args.get('q', '').strip()

        sql = """
            SELECT c.*,
                   comp.id as computer_id, comp.asset_id as computer_asset_id, comp.lab_location as computer_lab,
                   inv.id as inventory_id, inv.item_name as inventory_name, inv.serial_number as inventory_sn
            FROM complaints c
            LEFT JOIN computers comp ON c.computer_id = comp.id
            LEFT JOIN inventory inv ON c.inventory_id = inv.id
            WHERE 1=1
        """
        params = []

        if status_filter != 'all' and status_filter:
            sql += " AND c.status = ?"
            params.append(status_filter)

        if search_query:
            sql += " AND (c.title LIKE ? OR c.description LIKE ? OR c.reporter_name LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term])

        sql += " ORDER BY c.id DESC"
        complaints = query_db(sql, params)

        return render_template(
            'complaints/index.html',
            complaints=complaints,
            current_status=status_filter,
            search_query=search_query
        )

    @app.route('/complaints/<int:id>')
    def complaints_detail(id):
        complaint = query_db("""
            SELECT c.*,
                   comp.asset_id as computer_asset_id, comp.lab_location as computer_lab, comp.status as computer_status,
                   inv.item_name as inventory_name, inv.serial_number as inventory_sn, inv.category as inventory_category, inv.status as inventory_status
            FROM complaints c
            LEFT JOIN computers comp ON c.computer_id = comp.id
            LEFT JOIN inventory inv ON c.inventory_id = inv.id
            WHERE c.id = ?
        """, (id,), one=True)
        if not complaint:
            abort(404)

        return render_template('complaints/detail.html', complaint=complaint)

    @app.route('/complaints/<int:id>/status', methods=['POST'])
    def complaints_update_status(id):
        complaint = query_db("SELECT * FROM complaints WHERE id = ?", (id,), one=True)
        if not complaint:
            abort(404)

        new_status = request.form.get('status', complaint['status']).strip()
        resolution_notes = request.form.get('resolution_notes', '').strip() or None

        # Update the complaint status & resolution notes
        if new_status == 'Resolved':
            execute_db("""
                UPDATE complaints
                SET status = 'Resolved', resolution_notes = ?, resolved_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (resolution_notes, id))

            # SYSTEM INTEGRITY RULE:
            # Check if the linked asset can now be marked working!
            if complaint['target_type'] == 'computer' and complaint['computer_id']:
                comp_id = complaint['computer_id']
                # Check for other active tickets on this same computer
                other_tickets = query_db(
                    "SELECT id, title FROM complaints WHERE computer_id = ? AND status IN ('Pending', 'In Progress') AND id != ?",
                    (comp_id, id)
                )
                if other_tickets:
                    t_str = ", ".join([f"#{t['id']}" for t in other_tickets])
                    flash(f"Complaint #{id} marked as Resolved. However, this computer still has unresolved issue(s) ({t_str}) and remains non-operational.", "warning")
                else:
                    # All complaints on this computer are now resolved! Safely restore computer status to Working!
                    execute_db("UPDATE computers SET status = 'Working', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (comp_id,))
                    flash(f"Complaint #{id} resolved. All issues on Computer have cleared, so its status is now restored to Working!", "success")
            elif complaint['target_type'] == 'inventory' and complaint['inventory_id']:
                inv_id = complaint['inventory_id']
                other_inv_tickets = query_db(
                    "SELECT id FROM complaints WHERE inventory_id = ? AND status IN ('Pending', 'In Progress') AND id != ?",
                    (inv_id, id)
                )
                if not other_inv_tickets:
                    execute_db("UPDATE inventory SET status = 'In-Use', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Damaged'", (inv_id,))
                    flash(f"Complaint #{id} resolved. Peripheral restored to In-Use.", "success")
                else:
                    flash(f"Complaint #{id} resolved. Peripheral still has active complaints.", "warning")
        else:
            execute_db("""
                UPDATE complaints
                SET status = ?, resolution_notes = ?, resolved_at = NULL
                WHERE id = ?
            """, (new_status, resolution_notes, id))
            flash(f"Complaint #{id} status updated to {new_status}.", "info")

        return redirect(url_for('complaints_detail', id=id))

    # -------------------------------------------------------------
    # Module 5: Maintenance Management
    # -------------------------------------------------------------
    @app.route('/maintenance')
    def maintenance_list():
        month_filter = request.args.get('month', 'all').strip()
        work_type_filter = request.args.get('work_type', '').strip()
        search_query = request.args.get('q', '').strip()

        this_month, last_month = get_month_ranges()

        month_rows = query_db("""
            SELECT DISTINCT strftime('%Y-%m', maintenance_date) as ym
            FROM maintenance
            ORDER BY ym DESC
        """)
        available_months = [r['ym'] for r in month_rows if r['ym'] not in (this_month, last_month)]

        sql = """
            SELECT m.*,
                   c.title as complaint_title,
                   comp.asset_id as computer_asset_id, comp.lab_location as computer_lab,
                   inv.item_name as inventory_name, inv.serial_number as inventory_sn
            FROM maintenance m
            LEFT JOIN complaints c ON m.complaint_id = c.id
            LEFT JOIN computers comp ON m.computer_id = comp.id
            LEFT JOIN inventory inv ON m.inventory_id = inv.id
            WHERE 1=1
        """
        params = []

        if month_filter == 'this_month':
            sql += " AND strftime('%Y-%m', m.maintenance_date) = ?"
            params.append(this_month)
        elif month_filter == 'last_month':
            sql += " AND strftime('%Y-%m', m.maintenance_date) = ?"
            params.append(last_month)
        elif month_filter != 'all' and month_filter:
            sql += " AND strftime('%Y-%m', m.maintenance_date) = ?"
            params.append(month_filter)

        if work_type_filter:
            sql += " AND m.work_type = ?"
            params.append(work_type_filter)

        if search_query:
            sql += " AND (m.description LIKE ? OR m.performed_by LIKE ? OR comp.asset_id LIKE ? OR inv.item_name LIKE ?)"
            term = f"%{search_query}%"
            params.extend([term, term, term, term])

        sql += " ORDER BY m.maintenance_date DESC, m.id DESC"
        records = query_db(sql, params)

        return render_template(
            'maintenance/index.html',
            records=records,
            current_month=month_filter,
            current_type=work_type_filter,
            search_query=search_query,
            work_types=MAINTENANCE_WORK_TYPES,
            available_months=available_months
        )

    @app.route('/maintenance/new', methods=['GET', 'POST'])
    def maintenance_new():
        computers = query_db("SELECT id, asset_id, lab_location, status FROM computers ORDER BY asset_id")
        inventory_items = query_db("SELECT id, item_name, category, serial_number FROM inventory ORDER BY item_name")
        complaints = query_db("SELECT id, title, status FROM complaints WHERE status IN ('Pending', 'In Progress') ORDER BY id DESC")

        if request.method == 'POST':
            target_type = request.form.get('target_type', 'computer').strip()
            computer_id = request.form.get('computer_id', type=int) or None
            inventory_id = request.form.get('inventory_id', type=int) or None
            complaint_id = request.form.get('complaint_id', type=int) or None
            work_type = request.form.get('work_type', 'Repair').strip()
            description = request.form.get('description', '').strip()
            performed_by = request.form.get('performed_by', '').strip()
            cost = request.form.get('cost', 0.0, type=float)
            maintenance_date = request.form.get('maintenance_date', '').strip() or date.today().strftime('%Y-%m-%d')

            if not description or not performed_by:
                flash("Work description and Technician name are required.", "danger")
                return render_template('maintenance/form.html', is_edit=False, record={}, computers=computers, inventory_items=inventory_items, complaints=complaints, work_types=MAINTENANCE_WORK_TYPES, default_date=date.today().strftime('%Y-%m-%d'))

            if target_type == 'computer':
                inventory_id = None
                if not computer_id:
                    flash("Please select a computer for this maintenance entry.", "danger")
                    return render_template('maintenance/form.html', is_edit=False, record=request.form, computers=computers, inventory_items=inventory_items, complaints=complaints, work_types=MAINTENANCE_WORK_TYPES, default_date=date.today().strftime('%Y-%m-%d'))
            else:
                computer_id = None
                if not inventory_id:
                    flash("Please select an inventory item for this maintenance entry.", "danger")
                    return render_template('maintenance/form.html', is_edit=False, record=request.form, computers=computers, inventory_items=inventory_items, complaints=complaints, work_types=MAINTENANCE_WORK_TYPES, default_date=date.today().strftime('%Y-%m-%d'))

            # Insert maintenance record
            record_id, _ = execute_db("""
                INSERT INTO maintenance (target_type, computer_id, inventory_id, complaint_id, work_type, description, performed_by, cost, maintenance_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (target_type, computer_id, inventory_id, complaint_id, work_type, description, performed_by, cost, maintenance_date))

            # If service is on a computer and it was Faulty, update to Under Maintenance
            if target_type == 'computer' and computer_id:
                execute_db("UPDATE computers SET status = 'Under Maintenance', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'Faulty'", (computer_id,))

            flash("Maintenance record created successfully.", "success")
            return redirect(url_for('maintenance_list'))

        prefilled_complaint_id = request.args.get('complaint_id', type=int)
        prefilled_computer_id = None
        prefilled_inventory_id = None

        if prefilled_complaint_id:
            c = query_db("SELECT computer_id, inventory_id FROM complaints WHERE id = ?", (prefilled_complaint_id,), one=True)
            if c:
                prefilled_computer_id = c['computer_id']
                prefilled_inventory_id = c['inventory_id']

        return render_template(
            'maintenance/form.html',
            is_edit=False,
            record={},
            computers=computers,
            inventory_items=inventory_items,
            complaints=complaints,
            work_types=MAINTENANCE_WORK_TYPES,
            prefilled_complaint_id=prefilled_complaint_id,
            prefilled_computer_id=prefilled_computer_id,
            prefilled_inventory_id=prefilled_inventory_id,
            default_date=date.today().strftime('%Y-%m-%d')
        )

    @app.route('/maintenance/<int:id>')
    def maintenance_detail(id):
        record = query_db("""
            SELECT m.*,
                   c.title as complaint_title, c.status as complaint_status,
                   comp.asset_id as computer_asset_id, comp.lab_location as computer_lab,
                   inv.item_name as inventory_name, inv.serial_number as inventory_sn
            FROM maintenance m
            LEFT JOIN complaints c ON m.complaint_id = c.id
            LEFT JOIN computers comp ON m.computer_id = comp.id
            LEFT JOIN inventory inv ON m.inventory_id = inv.id
            WHERE m.id = ?
        """, (id,), one=True)
        if not record:
            abort(404)

        return render_template('maintenance/detail.html', record=record)

    @app.route('/maintenance/<int:id>/edit', methods=['GET', 'POST'])
    def maintenance_edit(id):
        record = query_db("SELECT * FROM maintenance WHERE id = ?", (id,), one=True)
        if not record:
            abort(404)

        computers = query_db("SELECT id, asset_id, lab_location, status FROM computers ORDER BY asset_id")
        inventory_items = query_db("SELECT id, item_name, category, serial_number FROM inventory ORDER BY item_name")
        complaints = query_db("SELECT id, title, status FROM complaints ORDER BY id DESC")

        if request.method == 'POST':
            target_type = request.form.get('target_type', 'computer').strip()
            computer_id = request.form.get('computer_id', type=int) or None
            inventory_id = request.form.get('inventory_id', type=int) or None
            complaint_id = request.form.get('complaint_id', type=int) or None
            work_type = request.form.get('work_type', 'Repair').strip()
            description = request.form.get('description', '').strip()
            performed_by = request.form.get('performed_by', '').strip()
            cost = request.form.get('cost', 0.0, type=float)
            maintenance_date = request.form.get('maintenance_date', '').strip() or record['maintenance_date']

            if not description or not performed_by:
                flash("Work description and technician name are required.", "danger")
                return render_template('maintenance/form.html', is_edit=True, record=record, computers=computers, inventory_items=inventory_items, complaints=complaints, work_types=MAINTENANCE_WORK_TYPES, default_date=record['maintenance_date'])

            if target_type == 'computer':
                inventory_id = None
            else:
                computer_id = None

            execute_db("""
                UPDATE maintenance
                SET target_type = ?, computer_id = ?, inventory_id = ?, complaint_id = ?, work_type = ?, description = ?, performed_by = ?, cost = ?, maintenance_date = ?
                WHERE id = ?
            """, (target_type, computer_id, inventory_id, complaint_id, work_type, description, performed_by, cost, maintenance_date, id))

            flash("Maintenance record updated successfully.", "success")
            return redirect(url_for('maintenance_detail', id=id))

        return render_template(
            'maintenance/form.html',
            is_edit=True,
            record=record,
            computers=computers,
            inventory_items=inventory_items,
            complaints=complaints,
            work_types=MAINTENANCE_WORK_TYPES,
            prefilled_complaint_id=None,
            prefilled_computer_id=None,
            prefilled_inventory_id=None,
            default_date=record['maintenance_date']
        )

    return app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5050))
    print(f"\n=======================================================")
    print(f"🚀 Smart Lab Management running at: http://127.0.0.1:{port}")
    print(f"=======================================================\n")
    app.run(debug=True, port=port)
