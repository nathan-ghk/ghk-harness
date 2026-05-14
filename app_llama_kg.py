import os
import re
# 1. 환경 변수 설정 
# os.environ["OPENAI_API_KEY"] = "your-api-key-here"
import chainlit as cl
from langchain_ollama import ChatOllama
# from langchain_openai import ChatOpenAI
# from langchain.chains import create_sql_query_chain
from langchain_classic.chains.sql_database.query import create_sql_query_chain
from langchain_community.tools.sql_database.tool import QuerySQLDataBaseTool
from schema import AgentResponse, InvestmentDetail
from database import get_db_connection
import asyncio
import sys
from langchain.chains import OntotextGraphDBQAChain 

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


def load_prompt(file_path):
    """ 외부 .md 파일로부터 프롬프트 로드 """
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    else:
        return "당신은 SQL 전문가 입니다. 질문에 맞는 SQL만 출력하세요."

SQL_PROMPT = load_prompt("data_query_prompt.md")

def extract_sql(text):
    """ 텍스트에서 SQL 쿼리를 추출 """
    sql_match = re.search(r"```sql\n*(.*?)\n*```", text, re.DOTALL)
    if sql_match:
        return sql_match.group(1).strip()
    code_match = re.search(r"```\n*(.*?)\n*```", text, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    if "SELECT" in text.upper():
        start_idx = text.upper().find("SELECT")
        end_idx = text.find(";", start_idx) 
        if end_idx != -1: 
            return text[start_idx:end_idx].strip()
        else:
            return text[start_idx:].strip()



@cl.on_chat_start
async def start():
    try:
        # DB 연결 및 LLM 초기화
        db = get_db_connection()
        # llm = ChatOpenAI(model="gpt-4", temperature=0, http_client=custom_http_client) # 분석 정밀도를 위해 0 설정
        llm = ChatOllama(model="llama3-manual", temperature=0, streaming = True) # 분석 정밀도를 위해 0 설정

        graph = OntotextGraphDBGraph(
            query_endpoint="http://localhost:7200/repositories/your-repo-id",
            local_file = r"C:\Projects\fin-kg\ontology\fk_triples_v02.ttl"
        )

        graph_chain = OntotextGraphDBQAChain.from_llm(llm, graph=graph)


        # SQL 생성 체인과 실행 도구 설정
        execute_query = QuerySQLDataBaseTool(db=db)
        write_query = create_sql_query_chain(llm, db)
        
        # 세션 저장
        cl.user_session.set("db", db)
        cl.user_session.set("graph_chain", graph_chain) 
        cl.user_session.set("llm", llm)
        cl.user_session.set("write_query", write_query)
        cl.user_session.set("execute_query", execute_query)

        await cl.Message(content="🚀 데이터 분석 에이전트가 가동되었습니다. 질문을 입력해주세요!").send()
    except Exception as e:
        await cl.Message(content=f"❌ 연결 실패: {e}\nPostgreSQL Ubuntu 도커가 켜져 있는지 확인해주세요!").send()

@cl.on_message
async def main(message: cl.Message):
    write_query = cl.user_session.get("write_query")
    execute_query = cl.user_session.get("execute_query")
    db = cl.user_session.get("db")
    llm = cl.user_session.get("llm")
    full_prompt = f"""{SQL_PROMPT}\n\n사용자 질문: {message.content}"""
    graph_chain = cl.user_session.get("graph_chain") # start에서 저장했다고 가정

    # --- Step 1: 라우팅 (질문 분류) ---
    async with cl.Step(name="질문 의도 분석") as step:
        router_res = await llm.ainvoke(ROUTER_PROMPT.format(question=message.content))
        route = router_res.content.strip().upper()
        step.output = f"결정된 경로: {route}"

    # --- Step 2: 경로별 실행 ---
    if "GRAPH" in route:
        # --- GraphDB(SPARQL) 경로 ---
        async with cl.Step(name="GraphDB 관계 분석") as step:
            cb = cl.AsyncLangchainCallbackHandler()
            # OntotextGraphDBQAChain 실행
            # Ollama의 경우 invoke를 비동기로 처리하기 위해 cl.make_async 사용
            res = await cl.make_async(graph_chain.invoke)(
                {"query": message.content},
                config={"callbacks": [cb]}
            )
            data = res["result"]
            step.output = f"GraphDB 분석 결과: {data}"
    else: 
        # --- Node 1 & 2: SQL 생성 및 자기 수정(Reflection) ---
        async with cl.Step(name="SQL 생성 및 검증") as step:
            retry_count = 0
            max_retries = 3
            raw_response = await llm.ainvoke(full_prompt)
            print(f"\n[DEBUG] 모델 최초 응답:\n{raw_response.content}\n")
            
            raw_content = raw_response.content if hasattr(raw_response, 'content') else str(raw_response)
            # 하이픈이나 불필요한 태그 제거 (LLM 클리닝)
            # query = query.strip().replace("```sql", "").replace("```", "")
            query = extract_sql(raw_content)
            if query:
                query = query.replace("%%", "%").replace("\\", "")
            else:
                await cl.Message(content="죄송합니다. 쿼리 생성에 실패했습니다.").send()
                return
            
            while retry_count < max_retries:
                print(f"\n[시도 {retry_count + 1}] 실행 쿼리:\n{query}")
                try:
                    # 쿼리 실행 시도
                    data = db.run(query)
                    step.output = f"✅ 실행된 SQL:\n{query}"
                    progress_msg = f"✅ 실행된 SQL:\n{query}"
                    await cl.Message(content=progress_msg).send()
                    print(f"[성공] 데이터 조회 완료.")
                    break
                except Exception as e:
                    retry_count += 1
                    error_msg = f"⚠️ {retry_count}차 수정 중... 에러: {e}"
                    step.output = f"⚠️ {retry_count}차 수정 중... 에러: {e}"
                    await cl.Message(content=error_msg).send()
                    print(f"[에러] {e}")
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
