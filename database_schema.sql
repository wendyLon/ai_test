-- MySQL schema for SEN training aggregation platform
-- Two main tables: sys_training_provider, sys_training

CREATE DATABASE IF NOT EXISTS sen_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE sen_platform;

-- Provider table
CREATE TABLE IF NOT EXISTS sys_training_provider (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  status TINYINT NOT NULL DEFAULT 1,
  name_zh_tw VARCHAR(150),
  name_zh_cn VARCHAR(150),
  name_en_us VARCHAR(150),
  intro_zh_cn TEXT,
  intro_en_us TEXT,
  intro_zh_tw TEXT,
  website_url VARCHAR(512),
  contact_phone VARCHAR(100),
  contact_email VARCHAR(255),
  provider_type_code VARCHAR(64),
  main_sen_type_code VARCHAR(128),
  logo VARCHAR(1024),
  recommend_count INT DEFAULT 0,
  sort SMALLINT DEFAULT 0,
  addtime INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()),
  updatetime INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()) ON UPDATE (UNIX_TIMESTAMP()),
  UNIQUE KEY ux_provider_website (website_url(255))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Training / Event table
CREATE TABLE IF NOT EXISTS sys_training (
  id BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
  provider_id BIGINT UNSIGNED,
  status TINYINT NOT NULL DEFAULT 1,
  title_zh_tw VARCHAR(255),
  title_zh_cn VARCHAR(255),
  title_en_us VARCHAR(255),
  description_zh_cn TEXT,
  description_zh_tw TEXT,
  description_en_us TEXT,
  summary_zh_cn VARCHAR(500),
  summary_zh_tw VARCHAR(500),
  summary_en_us VARCHAR(500),
  target_group VARCHAR(512),
  teaching_mode VARCHAR(64),
  fee_type VARCHAR(64),
  fee VARCHAR(255),
  fee_amount DECIMAL(12,2) DEFAULT NULL,
  currency VARCHAR(16) DEFAULT 'HKD',
  venue_name VARCHAR(1024),
  web_url VARCHAR(1024) NOT NULL,
  signup_url VARCHAR(1024),
  schedule_time VARCHAR(1024),
  end_time VARCHAR(64),
  sen_codes_json JSON,
  sen_types VARCHAR(1024),
  district_codes_json JSON,
  age_ranges_json JSON,
  audience_type VARCHAR(64),
  format_type VARCHAR(64),
  language_codes_json JSON,
  language_text VARCHAR(255),
  frequency VARCHAR(255),
  duration VARCHAR(100),
  quota VARCHAR(255),
  deadline VARCHAR(255),
  raw_html LONGTEXT,
  screenshot_path VARCHAR(1024),
  crawl_time INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()),
  addtime INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()),
  updatetime INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()) ON UPDATE (UNIX_TIMESTAMP()),
  UNIQUE KEY ux_training_weburl (web_url(768)),
  INDEX idx_provider (provider_id),
  INDEX idx_title (title_zh_cn(255)),
  CONSTRAINT fk_training_provider FOREIGN KEY (provider_id) REFERENCES sys_training_provider(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Deduplication index to support fingerprint lookups and fuzzy matching
CREATE TABLE IF NOT EXISTS dedup_index (
  fingerprint CHAR(64) PRIMARY KEY,
  provider_id BIGINT UNSIGNED,
  title_norm TEXT,
  date_norm VARCHAR(64),
  web_url VARCHAR(1024),
  record_id BIGINT UNSIGNED NULL,
  metadata JSON,
  last_seen INT UNSIGNED DEFAULT (UNIX_TIMESTAMP()),
  INDEX idx_provider_date (provider_id, date_norm(32))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
