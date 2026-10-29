from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ai import generate_sdlc


app = FastAPI(
    title="AI Powered SDLC Assistant",
    description="AI-powered SDLC artifact generation system",
    version="2.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():

    return {
        "message": "AI Powered SDLC Assistant API is running",
        "version": "2.0"
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
def health():

    return {
        "status": "ok"
    }


# ============================================================
# COMPLETE SDLC PIPELINE
# ============================================================

@app.post("/generate")
async def generate(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return result

    except Exception as e:

        print("SDLC generation error:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# REQUIREMENT ANALYZER
# ============================================================

@app.post("/analyze")
async def analyze(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "requirement_analysis":
                result["requirement_analysis"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# USER STORY GENERATOR
# ============================================================

@app.post("/user-stories")
async def user_stories(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "user_stories":
                result["user_stories"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# UML GENERATOR
# ============================================================

@app.post("/uml")
async def uml(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "uml": result["uml"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# DATABASE DESIGNER
# ============================================================

@app.post("/database")
async def database(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "database": result["database"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# API DESIGNER
# ============================================================

@app.post("/apis")
async def apis(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "apis": result["apis"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# PROJECT STRUCTURE GENERATOR
# ============================================================

@app.post("/project-structure")
async def project_structure(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "project_structure":
                result["project_structure"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )


# ============================================================
# DOCUMENTATION GENERATOR
# ============================================================

@app.post("/documentation")
async def documentation(data: dict):

    requirements = data.get("requirements", "")

    if not requirements.strip():

        raise HTTPException(
            status_code=400,
            detail="Requirements cannot be empty."
        )

    try:

        result = await generate_sdlc(
            requirements
        )

        return {
            "documentation":
                result["documentation"]
        }

    except Exception as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )