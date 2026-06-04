@echo off
cd /d C:\Users\alsan\ALEXANDRE_DS_LOCAL\05_bac_a_sable\dashboard_energie_apsystems
call C:\Users\alsan\miniconda3\Scripts\activate.bat
call conda activate base
streamlit run app.py
pause
