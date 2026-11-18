# Smart Computer Lab Management and Inventory System

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/sasankkuchimanchi/Smart-Lab-Management-Fresh)

A complete, production-ready web application built from scratch with **Python Flask**, **SQLite**, and **Bootstrap 5.3**. Designed for college computer laboratories to track desktop systems, monitor hardware inventory, empower students to report faults, manage repairs, and maintain a verifiable maintenance history with dynamic vector QR code tags.

---

## 🎯 Technology Stack

- **Backend:** Python Flask 3.1
- **Database:** SQLite 3 (with foreign key enforcement enabled: `PRAGMA foreign_keys = ON;`)
- **Frontend:** HTML5, CSS3, Bootstrap 5.3, Bootstrap Icons 1.11, Vanilla JavaScript
- **Asset Identification:** Pure SVG vector QR codes (`qrcode` Python package)
- **Testing:** Python `unittest` test suite

---

## 📁 Project Structure

```
Smart-Lab-Management-Fresh/
│
├── app.py                      # Flask routes, business logic & controllers
├── requirements.txt            # Python dependencies (Flask, qrcode)
├── README.md                   # Setup guide, architecture & demo sequence
│
├── database/
│   ├── schema.sql              # Clean SQLite tables with foreign keys and checks
│   ├── db.py                   # Parameterized SQLite connection & query helpers
│   └── seed.py                 # Idempotent demo data seeder (safe to run repeatedly)
│
├── instance/
│   └── smart_lab.sqlite3       # Local SQLite database file
│
├── static/
│   └── css/
│       └── style.css           # Custom styling, badges, cards & responsive layout
│
├── templates/
│   ├── base.html               # Shared layout, navbar, flash alerts & footer
│   ├── dashboard.html          # Live metrics, stats cards, and recent complaints table
│   │
│   ├── computers/
│   │   ├── index.html          # Computer list with search & status filters
│   │   ├── form.html           # Add / Edit computer with uniqueness validation
│   │   └── detail.html         # Specs view, linked peripherals, QR tag, history
│   │
│   ├── inventory/
│   │   ├── index.html          # Inventory list with Month Filter pills & category search
│   │   ├── form.html           # Add / Edit peripheral with computer assignment
│   │   └── detail.html         # Item details, assigned PC, QR tag, repair logs
│   │
│   ├── student/
│   │   ├── report.html         # Public student issue reporting portal
│   │   └── confirmation.html   # Friendly confirmation with Return / Report Another buttons
│   │
│   ├── complaints/
│   │   ├── index.html          # Admin complaints triage table (Pending/In Progress/Resolved)
│   │   └── detail.html         # Ticket review, resolution notes & status updater
│   │
│   └── maintenance/
│       ├── index.html          # Maintenance logs with Month Filter pills & cost tracker
│       ├── form.html           # Add / Edit service records & complaint links
│       └── detail.html         # Service event detail view
│
└── tests/
    └── test_app.py             # 16 automated unit tests covering all features
```

---

## 🚀 Quick Setup & How to Run

### Step 1: Open Terminal in the project folder
```bash
cd /Users/ksasank/Documents/Smart-Lab-Management-Fresh
```

### Step 2: Activate the Virtual Environment
```bash
source venv/bin/activate
```
*(If setting up on another machine: run `python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`)*

### Step 3: Seed Sample Demo Data *(Optional - runs automatically if DB is empty)*
```bash
python database/seed.py
```
*(Use `python database/seed.py --force` whenever you want to reset the database back to clean presentation data).*

### Step 4: Start the Flask Application
```bash
python app.py
```

### Step 5: Open in Your Browser
Visit: **`http://127.0.0.1:5050`**

*(Note: Port 5050 is configured by default because macOS uses port 5000 for Apple AirPlay Receiver/AirTunes).*

---

## 🧪 Running Automated Tests

Run the automated test suite to verify all modules, integrity safeguards, and routes:
```bash
python tests/test_app.py
```
**Test Results:** `Ran 16 tests in 0.24s -> OK` (100% pass rate).

---

## 💡 Key Architectural Features & Business Logic

### 1. Live SQLite Aggregations (Dashboard)
- **Computer Health**: Live counts for Total, Working, Faulty, and Under Maintenance.
- **Hardware Stock**: Tracks total catalog items and sum of physical units categorized by status (`Available`, `In-Use`, `Damaged`, `Under Maintenance`).
- **Complaints Pipeline**: Computes `Active / Open Issues` as `Pending + In Progress`. When an issue is resolved, open count decreases and resolved count increases while preserving full ticket history.
- **Relational Joins**: `LEFT JOIN` on recent complaints clearly identifies the linked computer or peripheral.

### 2. Duplicate Asset ID Rejection (Computer Management)
- Checks `asset_id` uniqueness on creation and edit. Duplicate entries are rejected with informative error alerts.
- Detail page generates a clean, scalable vector SVG QR code tag (`/qr/computer/<id>`).

### 3. Month Filters (Inventory & Maintenance)
- Prominent filter pills for:
  - **All Months**
  - **This Month**
  - **Last Month**
  - **Dynamic Months with records** (e.g. `2026-10`)
  - **No Purchase Date** (for legacy lab items without purchase dates)

### 4. Student Issue-Reporting Portal
- Accessible without admin credentials at `/student`.
- Dynamic toggle requires selecting **exactly one** computer system OR one inventory peripheral.
- Automatically marks the affected computer as **Faulty** or peripheral as **Damaged**.
- Confirmation page displays ticket reference with **Return to Home** and **Report Another Issue** buttons.

### 5. System Integrity Rule (Asset Health Safeguard)
> *“Do not mark a computer as working if it still has other unresolved issues or active maintenance.”*
- When an admin marks a complaint as `Resolved`, the system inspects whether that specific computer has any other active tickets (`Pending` or `In Progress`).
- If other unresolved issues remain, the computer is **not** prematurely marked as working, and a warning alert notifies the technician.
- If all issues on that computer are cleared, its status is safely restored to `Working`.

---

## 🎬 5-Minute Presentation Demo Sequence (For College Exam / Demo)

1. **Dashboard Overview (`/dashboard`)**:
   - Point out live statistics for Computers (8 Total: 5 Working, 2 Faulty, 1 Maintenance).
   - Point out Inventory stock and Complaint Pipeline (3 Open, 2 Resolved).
   - Show recent complaints with linked asset tags and priority badges.

2. **Student Issue Portal (`/student`)**:
   - Click the green **Student Issue Portal** button in the top navbar.
   - Select **Computer System** $\rightarrow$ choose `PC-LAB1-02`.
   - Fill in: Title: *"Display cable glitch"*, Priority: *High*, Reporter: *Your Name*.
   - Click **Submit Issue Report**. Notice the confirmation screen with ticket reference #6.
   - Click **Return to Home** $\rightarrow$ Notice that open complaints dynamically increased from 3 to 4, and `PC-LAB1-02` now shows as Faulty!

3. **Computer Management & QR Tags (`/computers`)**:
   - Click **Computers** in the navbar.
   - Click `PC-LAB1-02` to open its detail page.
   - Show the dynamic vector SVG QR code. Explain that technicians or students scan this to view specs or report issues.
   - Attempt to add a new computer with duplicate asset ID `PC-LAB1-01` $\rightarrow$ show that the form safely catches the error and rejects the duplicate.

4. **Inventory Management & Month Filters (`/inventory`)**:
   - Click **Inventory** in the navbar.
   - Demonstrate the Month Filter pills: Click **This Month** $\rightarrow$ items purchased this month appear; Click **No Purchase Date** $\rightarrow$ displays legacy spare items.
   - Show how peripherals are assigned directly to computers (e.g., `Dell UltraSharp 24 Monitor` assigned to `PC-LAB1-01`).

5. **Resolving Complaints with Integrity Guard (`/complaints`)**:
   - Click **Complaints** in the navbar $\rightarrow$ open the newly created ticket #6.
   - Change status to **Resolved**, enter resolution notes: *"HDMI cable replaced"*, click **Update Status**.
   - Show that the ticket is archived into history, and `PC-LAB1-02` is safely restored to **Working**!

6. **Maintenance & Cost Tracking (`/maintenance`)**:
   - Click **Maintenance** in the navbar.
   - Show the expenditure summary (₹) and filter by service month or work type (e.g., *Repair*, *Upgrade*).
