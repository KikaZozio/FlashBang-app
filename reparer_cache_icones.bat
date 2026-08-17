@echo off
echo ================================================================
echo   Reparation du cache d'icones Windows
echo ================================================================
echo.
echo Ferme bien Flash Bang et toutes les fenetres de l'explorateur
echo avant de continuer.
pause

echo.
echo Fermeture de l'explorateur Windows...
taskkill /f /im explorer.exe >nul 2>nul

echo Suppression des caches d'icones et de vignettes...
del /a /f /q "%localappdata%\IconCache.db" >nul 2>nul
del /a /f /q "%localappdata%\Microsoft\Windows\Explorer\iconcache_*.db" >nul 2>nul
del /a /f /q "%localappdata%\Microsoft\Windows\Explorer\thumbcache_*.db" >nul 2>nul

echo Redemarrage de l'explorateur Windows...
start explorer.exe

echo.
echo ================================================================
echo  Termine ! Les icones devraient maintenant etre a jour partout
echo  (raccourcis, barre des taches, explorateur...).
echo  Si ce n'est toujours pas bon, un redemarrage complet du PC
echo  juste apres avoir lance ce script devrait finir le travail.
echo ================================================================
pause
