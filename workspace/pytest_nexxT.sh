#!/bin/sh

pytest --cov=nexT.core --cov=nexT.interface --cov-report html ../nexxT/tests
NEXT_DISABLE_CIMPL=1 pytest --cov-append --cov=nexT.core --cov=nexT.interface --cov-report html ../nexT/tests

