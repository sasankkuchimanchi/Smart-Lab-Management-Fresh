-- SQLite schema for Smart Lab Management & Inventory System
PRAGMA foreign_keys = ON;

-- 1. Computers Table
CREATE TABLE IF NOT EXISTS computers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id TEXT UNIQUE NOT NULL,
    lab_location TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Working', 'Faulty', 'Under Maintenance')),
    ip_address TEXT,
    os TEXT,
    processor TEXT,
    ram TEXT,
    storage TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Inventory Items Table
CREATE TABLE IF NOT EXISTS inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name TEXT NOT NULL,
    category TEXT NOT NULL CHECK(category IN ('Monitor', 'Keyboard', 'Mouse', 'Projector', 'Networking', 'Printer', 'UPS', 'Other')),
    quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity >= 0),
    serial_number TEXT,
    computer_id INTEGER REFERENCES computers(id) ON DELETE SET NULL,
    location TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Available', 'In-Use', 'Damaged', 'Under Maintenance')),
    purchase_date DATE, -- YYYY-MM-DD or NULL
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Complaints Table (Student & Admin reported)
CREATE TABLE IF NOT EXISTS complaints (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('computer', 'inventory')),
    computer_id INTEGER REFERENCES computers(id) ON DELETE SET NULL,
    inventory_id INTEGER REFERENCES inventory(id) ON DELETE SET NULL,
    reporter_name TEXT NOT NULL,
    reporter_contact TEXT,
    priority TEXT NOT NULL CHECK(priority IN ('Low', 'Medium', 'High')),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK(status IN ('Pending', 'In Progress', 'Resolved')),
    resolution_notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

-- 4. Maintenance Records Table
CREATE TABLE IF NOT EXISTS maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL CHECK(target_type IN ('computer', 'inventory')),
    computer_id INTEGER REFERENCES computers(id) ON DELETE SET NULL,
    inventory_id INTEGER REFERENCES inventory(id) ON DELETE SET NULL,
    complaint_id INTEGER REFERENCES complaints(id) ON DELETE SET NULL,
    work_type TEXT NOT NULL CHECK(work_type IN ('Repair', 'Upgrade', 'Routine Check', 'Replacement', 'Cleaning')),
    description TEXT NOT NULL,
    performed_by TEXT NOT NULL,
    cost REAL NOT NULL DEFAULT 0.0 CHECK(cost >= 0),
    maintenance_date DATE NOT NULL, -- YYYY-MM-DD
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance and quick lookups
CREATE INDEX IF NOT EXISTS idx_computers_asset ON computers(asset_id);
CREATE INDEX IF NOT EXISTS idx_computers_status ON computers(status);
CREATE INDEX IF NOT EXISTS idx_inventory_status ON inventory(status);
CREATE INDEX IF NOT EXISTS idx_inventory_purchase ON inventory(purchase_date);
CREATE INDEX IF NOT EXISTS idx_complaints_status ON complaints(status);
CREATE INDEX IF NOT EXISTS idx_maintenance_date ON maintenance(maintenance_date);
