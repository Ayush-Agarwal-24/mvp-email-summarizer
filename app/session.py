from starlette.middleware.sessions import SessionMiddleware
from fastapi import FastAPI
from .config import APP_SECRET_KEY

def add_session(app: FastAPI):
    app.add_middleware(SessionMiddleware, secret_key=APP_SECRET_KEY, same_site="lax")
    return app
