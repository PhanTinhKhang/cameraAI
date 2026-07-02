@echo off
echo Building Camera AI Flutter App to APK...
set PUB_CACHE=D:\pub_cache
cd flutter_app
call flutter build apk --release
echo.
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Build failed! Please check the output above.
    pause
    exit /b %ERRORLEVEL%
)

echo Build complete!
echo Copying APK to root directory...
copy build\app\outputs\flutter-apk\app-release.apk ..\CameraAI_Volunteer.apk
cd ..
echo.
echo =======================================================
echo SUCCESS! The APK file "CameraAI_Volunteer.apk" is ready
echo You can now drag and drop it into BlueStacks to install.
echo =======================================================
pause
