import os
from dotenv import load_dotenv
load_dotenv(override=True)
# 1. 환경 변수 설정 
# os.environ["OPENAI_API_KEY"] = "your-api-key-here"


openai_api_key = os.getenv('OPENAI_API_KEY')

if openai_api_key:
    print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
else:
    print("OpenAI API Key not set - please head to the troubleshooting guide in the setup folder")

import ssl
import certifi
# ignore system environment variables and use certifi
os.environ['SSL_CERT_FILE'] = certifi.where()

# ommit certificate verification while using ssl context
try : 
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

import chainlit as cl
from langchain_openai import ChatOpenAI
# from langchain.chains import create_sql_query_chain
from langchain_classic.chains.sql_database.query import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from schema import AgentResponse, InvestmentDetail
from database import get_db_connection


import asyncio
import sys

try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(asyncio.new_event_loop())

def patch_anyio():
   from anyio.lowlevel import RunVar
   from anyio._core._eventloop import threadlocals
   try:
       if not hasattr(threadlocals, "current_async_backend"):
           threadlocals.current_async_backend = "asyncio"
   except Exception:
       pass
patch_anyio()



@cl.on_chat_start
async def start():
    try:
        # DB 연결 및 LLM 초기화
        db = get_db_connection()
        llm = ChatOpenAI(model="gpt-4", temperature=0) # 분석 정밀도를 위해 0 설정
        
        # SQL 생성 체인과 실행 도구 설정
        execute_query = QuerySQLDataBaseTool(db=db)
        write_query = create_sql_query_chain(llm, db)
        
        # 세션 저장
        cl.user_session.set("db", db)
        cl.user_session.set("llm", llm)
        cl.user_session.set("write_query", write_query)
        cl.user_session.set("execute_query", execute_query)

        await cl.Message(content="🚀 비즈너리님, 1만 건의 데이터를 품은 에이전트가 가동되었습니다. 질문을 입력해주세요!").send()
    except Exception as e:
        await cl.Message(content=f"❌ 연결 실패: {e}\n도커가 켜져 있는지 확인해주세요!").send()

@cl.on_message
async def main(message: cl.Message):
    write_query = cl.user_session.get("write_query")
    execute_query = cl.user_session.get("execute_query")
    db = cl.user_session.get("db")
    llm = cl.user_session.get("llm")

    # --- Node 1 & 2: SQL 생성 및 자기 수정(Reflection) ---
    async with cl.Step(name="SQL 생성 및 검증") as step:
        retry_count = 0
        max_retries = 3
        query = await write_query.ainvoke({"question": message.content})
        
        # 하이픈이나 불필요한 태그 제거 (LLM 클리닝)
        query = query.strip().replace("```sql", "").replace("```", "")
        
        while retry_count < max_retries:
            try:
                # 쿼리 실행 시도
                data = db.run(query)
                step.output = f"✅ 실행된 SQL:\n{query}"
                break
            except Exception as e:
                retry_count += 1
                step.output = f"⚠️ {retry_count}차 수정 중... 에러: {e}"
                # 에러 기반 재작성 요청
                query_msg = f"이 SQL은 에러가 나: {query}\n에러내용: {e}\n다시 짜줘. SQL만 출력해."
                response = await llm.ainvoke(query_msg)
                query = response.content.strip().replace("```sql", "").replace("```", "")
        
        if retry_count == max_retries:
            await cl.Message(content="죄송합니다. 쿼리 수정에 실패했습니다.").send()
            return

    # --- Node 3 & 4: 결과 요약 및 Pydantic 파싱 ---
    async with cl.Step(name="데이터 분석 및 인사이트") as step:
        prompt = f"질문: {message.content}\n데이터: {data}\n위 데이터를 바탕으로 분석해줘."
        # 실제 구현시에는 PydanticOutputParser를 사용하면 더욱 좋습니다.
        analysis = await llm.ainvoke(prompt)
        step.output = analysis.content

    await cl.Message(content=f"💡 분석이 완료되었습니다!\n\n{analysis.content}").send()
