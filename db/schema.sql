CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    domain TEXT,
    description TEXT,
    sector TEXT,
    sub_sector TEXT,
    hq_location TEXT,
    founded_year INTEGER,
    employee_count INTEGER,
    employee_growth_pct REAL,
    arr_millions REAL,
    revenue_growth_pct REAL,
    gross_margin_pct REAL,
    net_retention_pct REAL,
    total_raised_millions REAL,
    last_round_type TEXT,
    last_round_amount_millions REAL,
    last_round_date TEXT,
    last_valuation_millions REAL,
    key_investors TEXT,  -- JSON array
    pipeline_stage TEXT DEFAULT 'new',
    ai_summary TEXT,
    ai_memo TEXT,
    source TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    thesis_id INTEGER,
    team_score REAL,
    financial_score REAL,
    market_score REAL,
    product_score REAL,
    momentum_score REAL,
    composite_score REAL,
    tier TEXT,
    score_breakdown_json TEXT,
    scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    FOREIGN KEY (thesis_id) REFERENCES theses(id)
);

CREATE TABLE IF NOT EXISTS theses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    weight_team REAL DEFAULT 0.25,
    weight_financial REAL DEFAULT 0.25,
    weight_market REAL DEFAULT 0.20,
    weight_product REAL DEFAULT 0.15,
    weight_momentum REAL DEFAULT 0.15,
    criteria_json TEXT,  -- JSON: ARR range, growth thresholds, sectors, geos, round types
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    author TEXT DEFAULT 'analyst',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS company_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL,
    tag TEXT NOT NULL,
    FOREIGN KEY (company_id) REFERENCES companies(id),
    UNIQUE(company_id, tag)
);

CREATE TABLE IF NOT EXISTS news_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    title TEXT NOT NULL,
    url TEXT,
    source TEXT,
    published_date TEXT,
    summary TEXT,
    category TEXT,  -- funding, product, hiring, partnership
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);

CREATE TABLE IF NOT EXISTS activity_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER,
    action TEXT NOT NULL,  -- scored, stage_changed, note_added, memo_generated, imported
    details TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (company_id) REFERENCES companies(id)
);
