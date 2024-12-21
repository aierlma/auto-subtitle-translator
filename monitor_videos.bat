@echo off
cd /d "~\project\auto-subtitle-translator"
call conda activate whisper-webui

if not exist "D:\Downloads\processed" mkdir "D:\Downloads\processed"
if not exist "cli.py" goto end

:loop
for /r "D:\Downloads" %%i in (*.mp4) do call :process_file "%%i"
timeout /t 10 /nobreak > nul
goto loop

:process_file
setlocal enabledelayedexpansion
set "fullpath=%~1"
set "filepath=%~dp1"
set "filename=%~nx1"
set "basename=%~n1"

echo "!filepath!" | find "\processed\" >nul && goto :eof

rem 检查文件名是否包含"-C"
echo "!filename!" | find "-C" >nul && (
    echo Moving !filename! to processed folder - contains "-C"
    move "!fullpath!" "D:\Downloads\processed\"
    goto :eof
)

rem 检查是否存在对应的字幕文件
if exist "!filepath!!basename!.srt" (
    echo Moving !filename! to processed folder - .srt exists
    move "!fullpath!" "D:\Downloads\processed\"
    move "!filepath!!basename!.srt" "D:\Downloads\processed\"
    goto :eof
)

if exist "!filepath!!basename!.ass" (
    echo Moving !filename! to processed folder - .ass exists
    move "!fullpath!" "D:\Downloads\processed\"
    move "!filepath!!basename!.ass" "D:\Downloads\processed\"
    goto :eof
)

rem 检查是否包含"115chrome"
echo "!filename!" | find "115chrome" >nul && (
    echo Skipping !filename! - contains "115chrome"
    goto :eof
)

echo Processing: !filename!
python cli.py "!fullpath!" http://127.0.0.1:8080
if errorlevel 1 (
    echo Failed to process !filename!
    goto :eof
)

echo Successfully processed !filename!
set "srtpath=~\project\auto-subtitle-translator\project\cache\!filename!.wav-subs-merged.zh.srt"

if not exist "!srtpath!" (
    echo Warning: Generated subtitle file not found at !srtpath!
    goto :eof
)

move "!srtpath!" "!filepath!!basename!.srt"
if not exist "!filepath!!basename!.srt" (
    echo Error: Failed to move subtitle file to video directory
    goto :eof
)

move "!fullpath!" "D:\Downloads\processed\"
move "!filepath!!basename!.srt" "D:\Downloads\processed\"
echo Successfully moved video and subtitle to processed folder

endlocal
goto :eof

:end
call conda deactivate
