@echo off
echo ========================================================
echo   Starting JanAdhikar FastAPI Backend on port 8000
echo ========================================================
py -m uvicorn api.index:app --reload --port 8000
pause

