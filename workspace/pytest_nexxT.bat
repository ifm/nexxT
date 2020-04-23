CALL scons -j8 .. || exit /b 1

REM set NEXXT_CEXT_PATH=%cd%\build\msvc_x86_64_nonopt\nexxT\src
set NEXXT_VARIANT=nonopt
pytest --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1

REM set NEXXT_CEXT_PATH=%cd%\build\msvc_x86_64_release\nexxT\src
set NEXXT_VARIANT=release
pytest --cov-append --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1

set NEXXT_DISABLE_CIMPL=1
pytest --cov-append --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1
