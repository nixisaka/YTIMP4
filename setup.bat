@echo off
cd /d "%~dp0"

echo Downloading FFmpeg and FFprobe from GitHub...
curl -L -o ffmpeg_temp.zip https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip

echo Extracting files (this might take a minute, please wait)...

powershell -command "Expand-Archive -Path 'ffmpeg_temp.zip' -DestinationPath '.' -Force"

echo Moving executables out of the bin folder...

move "ffmpeg-master-latest-win64-gpl\bin\ffmpeg.exe" "%~dp0"
move "ffmpeg-master-latest-win64-gpl\bin\ffprobe.exe" "%~dp0"

echo Cleaning up the leftover files...
del ffmpeg_temp.zip
rmdir /S /Q "ffmpeg-master-latest-win64-gpl"

echo.
echo Setup Complete! 
echo Please check your folder now - ffmpeg.exe and ffprobe.exe should be there.
pause
