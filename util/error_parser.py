import re
from dataclasses import dataclass
from typing import List


@dataclass
class AnalyzerError:
    analyzer: str
    message: str
    file_path: str


RUNTIME_ERROR_REGEX = re.compile(r"""Analyzer '(.*)' threw the following exception: (.*)\.

--- EXCEPTION .*
Message = “.*”
ExceptionPath = .*
ClassName = .*
Data.File = (.*)""", flags=re.MULTILINE)


def parse_logs(logs: str) -> List[AnalyzerError]:
    errors: List[AnalyzerError] = []
    for m in RUNTIME_ERROR_REGEX.finditer(logs):
        analyzer, message, file_path = m.groups()
        errors.append(AnalyzerError(analyzer, message, file_path))

    return errors
