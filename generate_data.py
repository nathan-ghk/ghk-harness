import random
from datetime import datetime, timedelta
from faker import Faker
# from sqlalchemy import create_all, create_engine, text
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# 설정
DB_URL = "postgresql://ghk:ghk42@localhost:5432/ghk_poc_db"
fake_en = Faker('en_US')
fake_ko = Faker('ko_KR')
engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)
session = Session()


def run_data_generation():
    print("🚀 데이터 생성을 시작합니다...")

    # 1. 기초 코드 데이터 (Countries, Deal Types, Role Types)
    print("1/7 기초 코드 데이터 삽입 중...")
    countries = [('KR', 'South Korea', '대한민국', 'Asia'), ('US', 'USA', '미국', 'Americas'), ('JP', 'Japan', '일본', 'Asia')]
    for c in countries:
        session.execute(text("INSERT INTO countries VALUES (:c, :ne, :nk, :r) ON CONFLICT DO NOTHING"), {"c":c[0], "ne":c[1], "nk":c[2], "r":c[3]})

    deals = [('SEED','시드','Funding'), ('SERIES_A','시리즈A','Funding'), ('IPO','상장','Exit'), ('ACQUISITION','인수','M&A')]
    for d in deals:
        session.execute(text("INSERT INTO deal_types VALUES (:c, :n, :cat) ON CONFLICT DO NOTHING"), {"c":d[0], "n":d[1], "cat":d[2]})

    roles = [('CEO','대표이사',1), ('CTO','기술총괄',2), ('CFO','재무총괄',2)]
    for r in roles:
        session.execute(text("INSERT INTO role_types VALUES (:c, :n, :s) ON CONFLICT DO NOTHING"), {"c":r[0], "n":r[1], "s":r[2]})

    # 2. Industries (계층형)
    print("2/7 산업 분류 생성 중...")
    ind_ids = []
    for i in range(5):
        res = session.execute(text("INSERT INTO industries (name_en, name_ko, level) VALUES (:ne, :nk, 1) RETURNING id"),
                              {"ne": fake_en.job(), "nk": fake_ko.job()})
        ind_ids.append(res.fetchone()[0])

    # 3. Companies (Ticker 포함)
    print("3/7 기업 데이터(100개) 생성 중...")
    comp_ids = []
    for i in range(100):
        is_pub = random.random() < 0.3
        ticker = fake_en.lexify(text='????').upper() if is_pub else None
        res = session.execute(text("""
            INSERT INTO companies (name_en, name_ko, ticker, industry_id, country_code, is_public)
            VALUES (:ne, :nk, :t, :i, :c, :ip) RETURNING id
        """), {
            "ne": fake_en.company(), "nk": fake_ko.company(), "t": ticker,
            "i": random.choice(ind_ids), "c": random.choice(['KR','US','JP']), "ip": is_pub
        })
        comp_ids.append(res.fetchone()[0])

    # 4. Persons & Investors
    print("4/7 인물 및 투자사 데이터 생성 중...")
    person_ids = []
    for _ in range(50):
        res = session.execute(text("INSERT INTO persons (full_name_en, full_name_ko, nationality_code) VALUES (:ne, :nk, 'KR') RETURNING id"),
                              {"ne": fake_en.name(), "nk": fake_ko.name()})
        person_ids.append(res.fetchone()[0])

    inv_ids = []
    for _ in range(20):
        res = session.execute(text("INSERT INTO investors (name_en, name_ko, investor_type, country_code) VALUES (:ne, :nk, 'VC', 'US') RETURNING id"),
                              {"ne": fake_en.company() + " Capital", "nk": fake_ko.company() + " 투자"})
        inv_ids.append(res.fetchone()[0])

    # 5. Funding Rounds & Round Investors
    print("5/7 투자 라운드 데이터 생성 중...")
    for _ in range(150):
        c_id = random.choice(comp_ids)
        res = session.execute(text("""
            INSERT INTO funding_rounds (company_id, deal_type_code, announced_date, amount_usd)
            VALUES (:c, :d, :a, :am) RETURNING id
        """), {
            "c": c_id, "d": random.choice(['SEED','SERIES_A']),
            "a": fake_en.date_between(start_date='-3y'), "am": random.randint(1000000, 10000000)
        })
        r_id = res.fetchone()[0]
        # 투자자 매핑
        session.execute(text("INSERT INTO round_investors (round_id, investor_id, is_lead) VALUES (:r, :i, true)"),
                        {"r": r_id, "i": random.choice(inv_ids)})

    # 6. Executive Tenures (재직 이력)
    print("6/7 경영진 재직 이력 생성 중...")
    for p_id in person_ids:
        session.execute(text("""
            INSERT INTO executive_tenures (person_id, company_id, role_code, start_date)
            VALUES (:p, :c, :r, :s)
        """), {
            "p": p_id, "c": random.choice(comp_ids),
            "r": random.choice(['CEO','CTO','CFO']), "s": '2020-01-01'
        })

    # 7. M&A Transactions
    print("7/7 M&A 거래 데이터 생성 중...")
    for _ in range(30):
        session.execute(text("""
            INSERT INTO ma_transactions (acquirer_id, target_id, deal_type_code, deal_value_usd)
            VALUES (:a, :t, 'ACQUISITION', :v)
        """), {
            "a": random.choice(comp_ids), "t": random.choice(comp_ids),
            "v": random.randint(50000000, 500000000)
        })

    session.commit()
    print("✅ 모든 데이터 생성이 완료되었습니다!")

if __name__ == "__main__":
    try:
        run_data_generation()
    except Exception as e:
        session.rollback()
        print(f"❌ 오류 발생: {e}")
    finally:
        session.close()