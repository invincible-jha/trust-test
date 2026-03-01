# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 MuVeraAI Corporation

"""
JUnit XML output for trust test results.

Converts trust test results into JUnit XML format compatible with CI systems
such as GitHub Actions, Jenkins, GitLab CI, and CircleCI.

JUnit XML is the de-facto standard for test result reporting in CI. Most CI
systems can natively display JUnit XML as a test summary with pass/fail counts,
failed test details, and timing information.

Example
-------
>>> reporter = TrustTestJUnitReporter(suite_name="governance-tests")
>>> reporter.add_test_case("test_trust_level", passed=True, duration_seconds=0.12)
>>> reporter.add_test_case("test_budget_limit", passed=False, message="Budget exceeded threshold")
>>> xml_str = reporter.to_xml()
>>> reporter.write("/tmp/trust-test-results.xml")
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

__all__ = ["TrustTestJUnitReporter", "JUnitTestCase"]


@dataclass
class JUnitTestCase:
    """A single JUnit XML test case record.

    Attributes:
        name:             Test case name (maps to ``<testcase name="...">``).
        classname:        Logical class or module path.
        passed:           True if the test case passed.
        duration_seconds: Wall clock duration of the test.
        message:          Failure message (populated when ``passed=False``).
        stderr:           Optional stderr output captured during the test.
        stdout:           Optional stdout output captured during the test.
        skipped:          True if the test was skipped rather than run.
        skip_reason:      Reason the test was skipped (only meaningful when ``skipped=True``).
    """

    name: str
    classname: str = "governance"
    passed: bool = True
    duration_seconds: float = 0.0
    message: str = ""
    stderr: str = ""
    stdout: str = ""
    skipped: bool = False
    skip_reason: str = ""


class TrustTestJUnitReporter:
    """Builds and serializes a JUnit XML report from trust test results.

    Compatible with:
    - GitHub Actions test summary (``--junit-xml`` flag in pytest or direct upload)
    - Jenkins JUnit plugin
    - GitLab CI test reports
    - CircleCI test metadata

    Parameters
    ----------
    suite_name:
        Name of the test suite (appears in ``<testsuite name="...">``).
    package:
        Optional package prefix for all test classnames.

    Example
    -------
    >>> reporter = TrustTestJUnitReporter(suite_name="AumOS Governance Tests")
    >>> reporter.add_test_case("test_basic_trust", passed=True, duration_seconds=0.08)
    >>> reporter.add_test_case(
    ...     "test_budget_depletion",
    ...     passed=False,
    ...     duration_seconds=0.23,
    ...     message="Budget not fully depleted after 10 expensive calls",
    ... )
    >>> reporter.write("results/junit-governance.xml")
    """

    def __init__(
        self,
        suite_name: str = "trust-test",
        package: str = "aumos.governance",
    ) -> None:
        self._suite_name = suite_name
        self._package = package
        self._test_cases: list[JUnitTestCase] = []
        self._started_at: datetime = datetime.now(timezone.utc)

    def add_test_case(
        self,
        name: str,
        passed: bool = True,
        duration_seconds: float = 0.0,
        message: str = "",
        classname: str | None = None,
        stderr: str = "",
        stdout: str = "",
        skipped: bool = False,
        skip_reason: str = "",
    ) -> None:
        """Record a single test case result.

        Parameters
        ----------
        name:
            Test case name.
        passed:
            True if the test passed.
        duration_seconds:
            How long the test took (in seconds).
        message:
            Error/failure message (only relevant when ``passed=False``).
        classname:
            Override the default classname for this test case.
        stderr:
            Captured standard error output.
        stdout:
            Captured standard output.
        skipped:
            True if the test was skipped.
        skip_reason:
            Reason the test was skipped.
        """
        self._test_cases.append(
            JUnitTestCase(
                name=name,
                classname=classname or self._package,
                passed=passed,
                duration_seconds=duration_seconds,
                message=message,
                stderr=stderr,
                stdout=stdout,
                skipped=skipped,
                skip_reason=skip_reason,
            )
        )

    def to_xml(self) -> str:
        """Serialize the accumulated test cases to a JUnit XML string.

        Returns
        -------
        str:
            A JUnit-compatible XML document string with a UTF-8 XML declaration.
        """
        total = len(self._test_cases)
        failures = sum(1 for tc in self._test_cases if not tc.passed and not tc.skipped)
        skipped = sum(1 for tc in self._test_cases if tc.skipped)
        total_time = sum(tc.duration_seconds for tc in self._test_cases)
        timestamp = self._started_at.strftime("%Y-%m-%dT%H:%M:%S")

        suite_elem = ET.Element("testsuite")
        suite_elem.set("name", self._suite_name)
        suite_elem.set("tests", str(total))
        suite_elem.set("failures", str(failures))
        suite_elem.set("errors", "0")
        suite_elem.set("skipped", str(skipped))
        suite_elem.set("time", f"{total_time:.6f}")
        suite_elem.set("timestamp", timestamp)

        for test_case in self._test_cases:
            tc_elem = ET.SubElement(suite_elem, "testcase")
            tc_elem.set("name", test_case.name)
            tc_elem.set("classname", test_case.classname)
            tc_elem.set("time", f"{test_case.duration_seconds:.6f}")

            if test_case.skipped:
                skip_elem = ET.SubElement(tc_elem, "skipped")
                if test_case.skip_reason:
                    skip_elem.set("message", test_case.skip_reason)
            elif not test_case.passed:
                failure_elem = ET.SubElement(tc_elem, "failure")
                failure_elem.set("message", test_case.message)
                failure_elem.set("type", "AssertionError")
                if test_case.message:
                    failure_elem.text = test_case.message

            if test_case.stdout:
                stdout_elem = ET.SubElement(tc_elem, "system-out")
                stdout_elem.text = test_case.stdout

            if test_case.stderr:
                stderr_elem = ET.SubElement(tc_elem, "system-err")
                stderr_elem.text = test_case.stderr

        # Wrap in <testsuites> for compatibility with all CI systems
        root = ET.Element("testsuites")
        root.append(suite_elem)

        ET.indent(root, space="  ")
        return '<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(
            root, encoding="unicode", xml_declaration=False
        )

    def write(self, path: str | Path) -> None:
        """Write the JUnit XML report to *path*.

        Creates parent directories if they do not exist.

        Parameters
        ----------
        path:
            File path to write the XML report to.
        """
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_xml(), encoding="utf-8")

    @property
    def total_tests(self) -> int:
        """Total number of test cases recorded."""
        return len(self._test_cases)

    @property
    def failed_tests(self) -> int:
        """Number of failed (non-skipped) test cases."""
        return sum(1 for tc in self._test_cases if not tc.passed and not tc.skipped)

    @property
    def passed_tests(self) -> int:
        """Number of passing test cases."""
        return sum(1 for tc in self._test_cases if tc.passed)
