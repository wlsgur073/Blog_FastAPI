from fastapi import APIRouter, Request, Depends, Form, status
from fastapi.responses import RedirectResponse
from fastapi.exceptions import HTTPException
from fastapi.templating import Jinja2Templates
from db.database import direct_get_conn, context_get_conn
from sqlalchemy import text, Connection
from sqlalchemy.exc import SQLAlchemyError
from schemas.blog_schema import Blog, BlogOutputData
from utils import util

#router object
router = APIRouter(prefix="/blogs", tags=["blogs"])
#create jinjia2 template engine
templates = Jinja2Templates(directory="templates")

@router.get("/")
async def get_all_blogs(req: Request): # async 쓸 필요는 없지만, 훗날 async 함수로 바뀔 수 있다는 걸 강조.
    conn = None
    try:
        conn = direct_get_conn()
        query = """
            SELECT id, title, author, content, image_loc, modified_dt FROM blog
                """
        result = conn.execute(text(query))
        
        all_blogs = [BlogOutputData(id = row.id
                        , title = row.title
                        , author = row.author
                        , content = util.truncate_text(row.content)
                        , image_loc = row.image_loc # db 값이 Null인 경우 파이썬에서 None으로 처리됨
                        , modified_dt = row.modified_dt)
                    for row in result]
        result.close()
        return templates.TemplateResponse(
            request = req,
            name = "index.html",
            context = {"all_blogs": all_blogs}
            )
    except SQLAlchemyError as e:
        print(e)
        raise e
    finally:
        if conn:
            conn.close()

@router.get("/show/{id}")
def get_blog_by_id(req: Request, id: int,
                   conn: Connection = Depends(context_get_conn)):
    try:
        query = f"""
                SELECT id, title, author, content, image_loc, modified_dt FROM blog
                WHERE id = :id
                """
        stmt = text(query)
        bind_stmt = stmt.bindparams(id=id)
        result = conn.execute(bind_stmt)
        
        # 만약에 결과가 없으면 에러 던지기
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Blog with id {id} not found.")
        
        row = result.fetchone()
        blog = BlogOutputData(id = row.id
                        , title = row.title
                        , author = row.author
                        , content = util.newline_to_br(row.content)
                        , image_loc = row.image_loc
                        , modified_dt = row.modified_dt)
        result.close()
        return templates.TemplateResponse(
            request = req,
            name = "show_blog.html",
            context = {"blog": blog}
            )
    except SQLAlchemyError as e:
        print(e)
        raise e

@router.get("/new")
def create_blog_ui(req: Request):
    return templates.TemplateResponse(
        request = req,
        name = "new_blog.html",
        context = {}
        )
    
@router.post("/new")
def create_blog(req: Request,
                title: str = Form(min_length=2, max_length=100),
                author: str = Form(max_length=100),
                content: str = Form(min_length=2, max_length=4000),
                conn: Connection = Depends(context_get_conn)):
    try:
        # sql은 문자열인 것을 표현해줘야 함.
        # bindparams를 사용하면 알아서 문자열 처리하기에 sql injection을 방지할 수 있음.
        query = f"""
                INSERT INTO blog (title, author, content, modified_dt)
                VALUES ('{title}', '{author}', '{content}', NOW())
                """
        conn.execute(text(query))
        conn.commit() # SQLAlchemy에서는 기본이 rollback이기 때문에 commit을 해줘야 함.
        
        return RedirectResponse(url="/blogs", status_code=status.HTTP_302_FOUND)
    except SQLAlchemyError as e:
        print(e)
        conn.rollback() # 안해도 conn.close하면 기본적으로 rollback이 됨.
        raise e
    
@router.get("/modify/{id}")
def update_blog_ui(req: Request, id: int, conn = Depends(context_get_conn)):
    try:
        query = f"""
                SELECT id, title, author, content FROM blog
                WHERE id = :id
                """
        stmt = text(query)
        bind_stmt = stmt.bindparams(id = id)
        result = conn.execute(bind_stmt)
        
        # TODO: exception 중복 코드 발생 -> 모듈화하기
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Blog with id {id} not found.")
        
        row = result.fetchone()
        # blog = BlogOutputData(
        #     id = id
        #     , title = row.title
        #     , author =row.author
        #     , content = row.content
        #     , modified_dt = None # dataclass를 쓸때는 Optional하지 않게 설정해서 검증 잘못되면 validation error가 발생.
        #     )
        return templates.TemplateResponse(
            request = req,
            name = "modify_blog.html",
            context = {"id": row.id
                       , "title": row.title
                       , "author": row.author
                       , "content": row.content
                       }
            )
    except SQLAlchemyError as e:
        print(e)
        raise e
    
@router.post("/modify/{id}")
def update_blog(req: Request, id: int
                , title: str = Form(min_length=2, max_length=100)
                , author: str = Form(max_length=100)
                , content: str = Form(min_length=2, max_length=4000)
                , conn: Connection = Depends(context_get_conn)):
    try:
        query = f"""
                UPDATE blog
                SET title = '{title}', author = '{author}', content = '{content}', modified_dt = NOW()
                WHERE id = :id
                """
        stmt = text(query)
        bind_stmt = stmt.bindparams(id = id)
        result = conn.execute(bind_stmt)
        
        # app의 www url encoded로 오면 쿼리 파라미터에 값을 오입력할수도 있음. 그래서 예외처리함.
        if result.rowcount == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail=f"Blog with id {id} not found.")
            
        conn.commit()
        
        return RedirectResponse(url=f"/blogs/show/{id}", status_code=status.HTTP_302_FOUND)
    except SQLAlchemyError as e:
        print(e)
        raise e