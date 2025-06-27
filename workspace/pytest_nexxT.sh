#!/bin/sh
if test -z "$1"; then
  PYTEST=pytest
else
  PYTEST="$1"
fi

ADD_FLAGS="--forked -n auto"

# release variant
                      "$PYTEST" -m     "gui" $ADD_FLAGS              --cov=../nexxT/core --cov=../nexxT/interface --cov=../nexxT/services --cov=../nexxT/filters --cov-report html ../nexxT/tests
                      "$PYTEST" -m "not gui" $ADD_FLAGS --dist=loadfile --cov-append --cov=../nexxT/core --cov=../nexxT/interface --cov=../nexxT/services --cov=../nexxT/filters --cov-report html ../nexxT/tests
# other variants
NEXXT_VARIANT=nonopt  "$PYTEST" -m "not gui" $ADD_FLAGS --dist=loadfile --cov-append --cov=../nexxT/core --cov=../nexxT/interface --cov=../nexxT/services --cov=../nexxT/filters --cov-report html ../nexxT/tests
NEXXT_DISABLE_CIMPL=1 "$PYTEST" -m "not gui" $ADD_FLAGS --dist=loadfile --cov-append --cov=../nexxT/core --cov=../nexxT/interface --cov=../nexxT/services --cov=../nexxT/filters --cov-report html ../nexxT/tests

