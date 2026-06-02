@echo off
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting Semanalyzer...
echo Opening browser...
timeout /t 2 /nobreak
start http://localhost:8501
python -m streamlit run app.py
