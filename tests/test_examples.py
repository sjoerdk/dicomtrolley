"""Tests the scripts in /examples for basic errors"""
from examples.go_shopping import go_shopping


def test_go_shopping():
    # make sure no actual http requests are made
    # set up env and mock server responses
    go_shopping()
