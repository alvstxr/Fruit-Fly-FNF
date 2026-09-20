@echo off
cd /d "%~dp0"
set OPENBLAS_NUM_THREADS=1
set MKL_NUM_THREADS=1
set OMP_NUM_THREADS=1
set NUMEXPR_NUM_THREADS=1
set OPENBLAS_VERBOSE=0
set LOG=%TEMP%\fly_fnf_spawn_bat.txt
> "%LOG%" echo %DATE% %TIME%
>> "%LOG%" echo dir=%CD%
where pyw >> "%LOG%" 2>&1
where pythonw >> "%LOG%" 2>&1
if exist "%SystemRoot%\pyw.exe" (
  "%SystemRoot%\pyw.exe" -3 "%~dp0fly_bridge.py"
  if not errorlevel 1 goto :eof
)
pyw -3 "%~dp0fly_bridge.py"
if not errorlevel 1 goto :eof
pythonw "%~dp0fly_bridge.py"
if not errorlevel 1 goto :eof
py -3 -m pip install --user numpy opencv-python >> "%LOG%" 2>&1
python -m pip install --user numpy opencv-python >> "%LOG%" 2>&1
if exist "%SystemRoot%\py.exe" (
  "%SystemRoot%\py.exe" -3 "%~dp0fly_bridge.py"
  if not errorlevel 1 goto :eof
)
py -3 "%~dp0fly_bridge.py"
if not errorlevel 1 goto :eof
python "%~dp0fly_bridge.py"
>> "%LOG%" echo launch failed
