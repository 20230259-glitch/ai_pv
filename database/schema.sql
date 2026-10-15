-- ============================================
-- AI MOCK INTERVIEW DATABASE
-- PostgreSQL
-- ============================================

-- 1. USERS
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 2. CANDIDATES
CREATE TABLE IF NOT EXISTS candidates (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    full_name VARCHAR(200),
    email VARCHAR(200),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 3. DOCUMENTS
-- Lưu CV và JD
CREATE TABLE IF NOT EXISTS documents (
    id SERIAL PRIMARY KEY,
    candidate_id INTEGER REFERENCES candidates(id) ON DELETE CASCADE,

    document_type VARCHAR(20) NOT NULL,
    -- CV hoặc JD

    file_name VARCHAR(255),

    raw_text TEXT,
    cleaned_text TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 4. INTERVIEW SESSIONS
CREATE TABLE IF NOT EXISTS interview_sessions (
    id SERIAL PRIMARY KEY,

    candidate_id INTEGER
        REFERENCES candidates(id) ON DELETE CASCADE,

    jd_id INTEGER
        REFERENCES documents(id) ON DELETE SET NULL,

    matching_score NUMERIC(5,2),

    question_source VARCHAR(50),

    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    completed_at TIMESTAMP
);


-- 5. QUESTIONS
CREATE TABLE IF NOT EXISTS questions (
    id SERIAL PRIMARY KEY,

    session_id INTEGER
        REFERENCES interview_sessions(id) ON DELETE CASCADE,

    question_text TEXT NOT NULL,

    criterion VARCHAR(100),

    question_order INTEGER
);


-- 6. ANSWERS
CREATE TABLE IF NOT EXISTS answers (
    id SERIAL PRIMARY KEY,

    session_id INTEGER
        REFERENCES interview_sessions(id) ON DELETE CASCADE,

    question_id INTEGER
        REFERENCES questions(id) ON DELETE CASCADE,

    answer_text TEXT,

    transcript TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 7. SCORES
CREATE TABLE IF NOT EXISTS scores (
    id SERIAL PRIMARY KEY,

    answer_id INTEGER
        REFERENCES answers(id) ON DELETE CASCADE,

    knowledge_score NUMERIC(5,2) DEFAULT 0,

    problem_solving_score NUMERIC(5,2) DEFAULT 0,

    jd_fit_score NUMERIC(5,2) DEFAULT 0,

    communication_score NUMERIC(5,2) DEFAULT 0,

    cultural_fit_score NUMERIC(5,2) DEFAULT 0,

    total_score NUMERIC(5,2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


-- 8. PROGRESS
CREATE TABLE IF NOT EXISTS progress (
    id SERIAL PRIMARY KEY,

    candidate_id INTEGER
        REFERENCES candidates(id) ON DELETE CASCADE,

    session_id INTEGER
        REFERENCES interview_sessions(id) ON DELETE CASCADE,

    criterion VARCHAR(100) NOT NULL,

    score NUMERIC(5,2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);