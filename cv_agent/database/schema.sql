PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS vacancies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    area TEXT NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT NOT NULL,
    required_experience REAL NOT NULL DEFAULT 0,
    required_skills TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS processes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    vacancy_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'ANALYZED',
    total_candidates INTEGER NOT NULL DEFAULT 0,
    average_score REAL NOT NULL DEFAULT 0,
    FOREIGN KEY (vacancy_id) REFERENCES vacancies(id)
);

CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    process_id INTEGER NOT NULL,
    file_name TEXT NOT NULL,
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    career TEXT,
    experience_years REAL NOT NULL DEFAULT 0,
    skills TEXT NOT NULL,
    languages TEXT NOT NULL,
    certifications TEXT NOT NULL,
    projects TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    score REAL NOT NULL,
    similarity_score REAL NOT NULL,
    skill_score REAL NOT NULL,
    experience_score REAL NOT NULL,
    matched_skills TEXT NOT NULL,
    missing_skills TEXT NOT NULL,
    status TEXT NOT NULL,
    selected INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY (process_id) REFERENCES processes(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS email_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    sent_at TEXT NOT NULL,
    FOREIGN KEY (candidate_id) REFERENCES candidates(id) ON DELETE CASCADE
);
