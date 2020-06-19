#!/bin/sh
if test -z "$1"; then
  PYTEST=pytest
else
  PYTEST="$1"
fi
                      "$PYTEST"              --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov-report html ../nexxT/tests
NEXXT_VARIANT=nonopt  "$PYTEST" --cov-append --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov-report html ../nexxT/tests
NEXXT_DISABLE_CIMPL=1 "$PYTEST" --cov-append --cov=nexxT.core --cov=nexxT.interface --cov=nexxT.services --cov-report html ../nexxT/tests
