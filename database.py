import os
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine

# DB 환경 설정 
DB_USER = "ghk" #"user"
DB_PASS = "ghk42" # "password"
DB_HOST = "localhost" # "172.26.229.112" # "localhost"
DB_PORT = "5432"
DB_NAME = "ghk_poc_db" # "mydatabase"

def get_db_connection():
    pg_uri = f"postgresql+psycopg2://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    engine = create_engine(pg_uri)
    # LangChain이 이해할 수 있는 SQLDatabase 객체로 반환
    return SQLDatabase(engine)
