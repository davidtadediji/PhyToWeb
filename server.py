from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
from router import router
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from logger import configured_logger

import os

# Load environment variables from .env file
load_dotenv()

app_name = os.getenv("APP_NAME")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configured_logger.info(f"Starting {app_name} Service...")
    try:
        yield
    finally:
        configured_logger.info(f"Shutting down {app_name} Service...")


app = FastAPI(
    title=f"{app_name} Service",
    lifespan=lifespan,  # Define the lifespan context manager
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    configured_logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
    )


# Define a root route
@app.get("/", response_class=JSONResponse)
async def root():
    return {"detail": f"Welcome to the Root of the {app_name} Service!"}

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,  # No cookies needed
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(router)



if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8002, reload=True)
