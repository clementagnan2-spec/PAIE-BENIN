@echo off
REM =====================================================================
REM  Compile PaieBenin.exe avec PyInstaller (Windows)
REM  A executer depuis une invite de commandes, dans ce dossier.
REM =====================================================================

echo Installation des dependances...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Compilation en cours...
REM Si vous avez un fichier icon.ico dans ce dossier, ajoutez la ligne :
REM   --icon "icon.ico" ^
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "PaieBenin" ^
  main.py

echo.
echo Termine. L'executable se trouve dans le dossier "dist\PaieBenin.exe"
pause
