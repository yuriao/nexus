-- Nexus: MySQL initialization
-- Creates databases and full schema for all services

-- ─── Databases ────────────────────────────────────────────────────────────────
CREATE DATABASE IF NOT EXISTS nexus_auth CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS nexus_core CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON nexus_auth.* TO 'nexus'@'%';
GRANT ALL PRIVILEGES ON nexus_core.* TO 'nexus'@'%';
FLUSH PRIVILEGES;

-- ─── nexus_auth schema ────────────────────────────────────────────────────────
USE nexus_auth;

CREATE TABLE IF NOT EXISTS accounts_user (
    id          BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    password    VARCHAR(128)    NOT NULL,
    last_login  DATETIME(6)     NULL,
    is_superuser TINYINT(1)     NOT NULL DEFAULT 0,
    username    VARCHAR(150)    NOT NULL UNIQUE,
    first_name  VARCHAR(150)    NOT NULL DEFAULT '',
    last_name   VARCHAR(150)    NOT NULL DEFAULT '',
    email       VARCHAR(254)    NOT NULL UNIQUE,
    is_staff    TINYINT(1)      NOT NULL DEFAULT 0,
    is_active   TINYINT(1)      NOT NULL DEFAULT 1,
    date_joined DATETIME(6)     NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_email (email),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS accounts_apikey (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id      BIGINT UNSIGNED NOT NULL,
    key_hash     VARCHAR(64)     NOT NULL UNIQUE,
    name         VARCHAR(100)    NOT NULL,
    scopes       JSON            NOT NULL,
    created_at   DATETIME(6)     NOT NULL,
    last_used_at DATETIME(6)     NULL,
    is_active    TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    CONSTRAINT fk_apikey_user FOREIGN KEY (user_id) REFERENCES accounts_user (id) ON DELETE CASCADE,
    INDEX idx_key_hash (key_hash),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ─── nexus_core schema ────────────────────────────────────────────────────────
USE nexus_core;

CREATE TABLE IF NOT EXISTS companies_company (
    id                    BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    name                  VARCHAR(255)    NOT NULL,
    domain                VARCHAR(255)    NOT NULL UNIQUE,
    sector                VARCHAR(100)    NOT NULL DEFAULT '',
    country               VARCHAR(100)    NOT NULL DEFAULT '',
    description           TEXT            NULL,
    employee_count        INT             NULL,
    founded_year          SMALLINT        NULL,
    last_crawled_at       DATETIME(6)     NULL,
    crawl_frequency_hours INT             NOT NULL DEFAULT 24,
    created_at            DATETIME(6)     NOT NULL,
    updated_at            DATETIME(6)     NOT NULL,
    PRIMARY KEY (id),
    INDEX idx_domain (domain),
    INDEX idx_sector (sector),
    INDEX idx_last_crawled (last_crawled_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS companies_datapoint (
    id               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    company_id       BIGINT UNSIGNED NOT NULL,
    source_type      VARCHAR(50)     NOT NULL COMMENT 'news|jobs|crunchbase|linkedin|custom',
    source_url       TEXT            NOT NULL,
    raw_text         LONGTEXT        NOT NULL,
    structured_json  JSON            NULL,
    extracted_at     DATETIME(6)     NOT NULL,
    confidence_score DECIMAL(4,3)    NOT NULL DEFAULT 1.000,
    PRIMARY KEY (id),
    CONSTRAINT fk_dp_company FOREIGN KEY (company_id) REFERENCES companies_company (id) ON DELETE CASCADE,
    INDEX idx_company_source (company_id, source_type),
    INDEX idx_extracted_at (extracted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS companies_watchlist (
    id         BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id    BIGINT UNSIGNED NOT NULL COMMENT 'references auth service user',
    company_id BIGINT UNSIGNED NOT NULL,
    created_at DATETIME(6)     NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_wl_company FOREIGN KEY (company_id) REFERENCES companies_company (id) ON DELETE CASCADE,
    UNIQUE KEY uq_user_company (user_id, company_id),
    INDEX idx_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS companies_alert (
    id                VARCHAR(36)  NOT NULL COMMENT 'UUID',
    user_id           BIGINT UNSIGNED NOT NULL,
    company_id        BIGINT UNSIGNED NOT NULL,
    trigger_condition JSON         NOT NULL COMMENT '{type, threshold, field}',
    last_triggered_at DATETIME(6)  NULL,
    delivery_channel  VARCHAR(50)  NOT NULL DEFAULT 'email' COMMENT 'email|webhook|slack',
    is_active         TINYINT(1)   NOT NULL DEFAULT 1,
    created_at        DATETIME(6)  NOT NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_alert_company FOREIGN KEY (company_id) REFERENCES companies_company (id) ON DELETE CASCADE,
    INDEX idx_alert_user (user_id),
    INDEX idx_alert_company (company_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reports_researchreport (
    id               VARCHAR(36)  NOT NULL COMMENT 'UUID',
    company_id       BIGINT UNSIGNED NOT NULL,
    version          INT          NOT NULL DEFAULT 1,
    status           VARCHAR(20)  NOT NULL DEFAULT 'pending' COMMENT 'pending|running|completed|failed',
    summary          TEXT         NULL,
    opportunities    JSON         NULL,
    risks            JSON         NULL,
    predictions      JSON         NULL,
    confidence_score DECIMAL(4,3) NULL,
    error_message    TEXT         NULL,
    created_at       DATETIME(6)  NOT NULL,
    completed_at     DATETIME(6)  NULL,
    PRIMARY KEY (id),
    CONSTRAINT fk_report_company FOREIGN KEY (company_id) REFERENCES companies_company (id) ON DELETE CASCADE,
    INDEX idx_report_company (company_id),
    INDEX idx_report_status (status),
    INDEX idx_report_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS reports_reportsection (
    id           BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    report_id    VARCHAR(36)     NOT NULL,
    section_type VARCHAR(50)     NOT NULL COMMENT 'executive_summary|key_findings|opportunities|risks|predictions',
    content      LONGTEXT        NOT NULL,
    sort_order   INT             NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT fk_section_report FOREIGN KEY (report_id) REFERENCES reports_researchreport (id) ON DELETE CASCADE,
    INDEX idx_section_report (report_id),
    INDEX idx_section_order (report_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
