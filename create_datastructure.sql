-- 1. 코드 테이블 및 마스터 (기초 데이터)
CREATE TABLE countries (
    country_code CHAR(2) PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    region VARCHAR(50)
);
COMMENT ON TABLE countries IS '국가 코드 정보';
COMMENT ON COLUMN countries.country_code IS 'ISO-2 국가 코드';
COMMENT ON COLUMN countries.name_ko IS '국가명(한글)';

CREATE TABLE industries (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(100) NOT NULL,
    name_ko VARCHAR(100) NOT NULL,
    parent_id INTEGER REFERENCES industries(id),
    level INTEGER DEFAULT 1
);
COMMENT ON TABLE industries IS '산업 분류 (계층 구조)';
COMMENT ON COLUMN industries.parent_id IS '상위 산업 ID (Self-reference)';

CREATE TABLE deal_types (
    code VARCHAR(20) PRIMARY KEY,
    name_ko VARCHAR(50) NOT NULL,
    category VARCHAR(20) -- Funding, M&A, Exit
);
COMMENT ON COLUMN deal_types.category IS '딜 대분류 (투자, M&A, 엑시트 등)';

CREATE TABLE role_types (
    code VARCHAR(20) PRIMARY KEY,
    name_ko VARCHAR(50) NOT NULL,
    seniority_level INTEGER
);

-- 2. 핵심 엔티티
CREATE TABLE companies (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(200) NOT NULL,
    name_ko VARCHAR(200),
    ticker VARCHAR(20), -- 추가된 컬럼
    parent_company_id INTEGER REFERENCES companies(id),
    industry_id INTEGER REFERENCES industries(id),
    country_code CHAR(2) REFERENCES countries(country_code),
    founded_date DATE,
    is_public BOOLEAN DEFAULT FALSE,
    description_ko TEXT
);
COMMENT ON TABLE companies IS '기업 마스터 (계층 구조 포함)';
COMMENT ON COLUMN companies.ticker IS '주식 종목 코드 (상장사인 경우)';
COMMENT ON COLUMN companies.parent_company_id IS '모기업 ID (지배구조)';

CREATE TABLE persons (
    id SERIAL PRIMARY KEY,
    full_name_en VARCHAR(100) NOT NULL,
    full_name_ko VARCHAR(100),
    nationality_code CHAR(2) REFERENCES countries(country_code),
    birth_year INTEGER,
    linkedin_url VARCHAR(255)
);

CREATE TABLE investors (
    id SERIAL PRIMARY KEY,
    name_en VARCHAR(200) NOT NULL,
    name_ko VARCHAR(200),
    investor_type VARCHAR(50), -- VC, PE, CVC, Angel
    country_code CHAR(2) REFERENCES countries(country_code),
    aum_usd BIGINT
);

-- 3. 트랜잭션 및 관계 (다대다)
CREATE TABLE funding_rounds (
    id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(id),
    deal_type_code VARCHAR(20) REFERENCES deal_types(code),
    announced_date DATE NOT NULL,
    amount_usd BIGINT,
    pre_money_valuation_usd BIGINT
);

CREATE TABLE round_investors (
    round_id INTEGER REFERENCES funding_rounds(id),
    investor_id INTEGER REFERENCES investors(id),
    is_lead BOOLEAN DEFAULT FALSE,
    invested_amount_usd BIGINT,
    PRIMARY KEY (round_id, investor_id)
);
COMMENT ON TABLE round_investors IS '투자 라운드별 참여 투자자 (다대다)';

CREATE TABLE executive_tenures (
    id SERIAL PRIMARY KEY,
    person_id INTEGER REFERENCES persons(id),
    company_id INTEGER REFERENCES companies(id),
    role_code VARCHAR(20) REFERENCES role_types(code),
    start_date DATE,
    end_date DATE, -- NULL이면 현직
    is_founder BOOLEAN DEFAULT FALSE
);
COMMENT ON TABLE executive_tenures IS '인물별 기업 재직 이력 (다대다)';

CREATE TABLE ma_transactions (
    id SERIAL PRIMARY KEY,
    acquirer_id INTEGER REFERENCES companies(id),
    target_id INTEGER REFERENCES companies(id),
    deal_type_code VARCHAR(20) REFERENCES deal_types(code),
    announced_date DATE,
    deal_value_usd BIGINT,
    ownership_pct DECIMAL(5,2)
);
COMMENT ON TABLE ma_transactions IS 'M&A 거래 내역';
