import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.logging_config import configure_logging
from app.config import get_settings
from app.integration.mcp_exceptions import MCPIntegrationError


settings = get_settings()

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Jira GitHub MCP Integration API")
app.add_middleware(CORSMiddleware,
                   allow_origins=settings.cors_origins,
                   allow_methods=["GET", "POST"],
                   allow_headers=["Content-Type"])

@app.exception_handler(StarletteHTTPException)
def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(
        request: Request,
        exc: RequestValidationError
):
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": "Validation error",
            "details": jsonable_encoder(exc.errors()),
        },
    )


@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
        },
    )

app.include_router(router)
logger.info("FastAPI application initialized")

@app.exception_handler(MCPIntegrationError)
async def mcp_exception_handler(
        request: Request,
        exc: MCPIntegrationError,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": str(exc),
        },
    )