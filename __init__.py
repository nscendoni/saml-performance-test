"""
SAML Performance Test Tool
A command-line tool for SAML assertion performance testing
"""

__version__ = "1.0.0"

from .saml_builder import SAMLAssertionBuilder
from .user_generator import UserGenerator, SequentialUserGenerator, TestUser
from .performance_tester import SAMLPerformanceTester, TestResults, run_performance_test

__all__ = [
    "SAMLAssertionBuilder",
    "UserGenerator",
    "SequentialUserGenerator",
    "TestUser",
    "SAMLPerformanceTester",
    "TestResults",
    "run_performance_test",
]
