CALL scons .. || exit /b 1
set NEXT_CEXT_PATH=%cd%\build\msvc_x86_64_nonopt\nexxT\src
set NEXT_CPLUGIN_PATH=%cd%\build\msvc_x86_64_nonopt\nexxT\tests\src
pytest --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1

set NEXT_CEXT_PATH=%cd%\build\msvc_x86_64_release\nexxT\src
set NEXT_CPLUGIN_PATH=%cd%\build\msvc_x86_64_release\nexxT\tests\src
pytest --cov-append --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1

set NEXT_DISABLE_CIMPL=1
pytest --cov-append --cov=nexxT.core --cov=nexxT.interface --cov-report html ../nexxT/tests || exit /b 1
