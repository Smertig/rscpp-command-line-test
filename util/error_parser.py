import re
from dataclasses import dataclass
from typing import List


@dataclass
class AnalyzerError:
    analyzer: str
    message: str
    file_path: str


LEFT_MARK = '“'.encode('utf8').decode('cp1251')
RIGHT_MARK = '”'.encode('utf8').decode('cp1251')
RUNTIME_ERROR_REGEX = re.compile(fr"""Analyzer '(.*)' threw the following exception: (.*)\.

--- EXCEPTION .*
Message = .*
ExceptionPath = .*
ClassName = .*
Data.File = (.*)""", flags=re.MULTILINE)


def parse_logs(logs: str) -> List[AnalyzerError]:
    errors: List[AnalyzerError] = []
    for m in RUNTIME_ERROR_REGEX.finditer(logs):
        analyzer, message, file_path = m.groups()
        errors.append(AnalyzerError(analyzer, strip_quotes(message), strip_quotes(file_path)))

    return errors


def strip_quotes(text: str) -> str:
    return text.lstrip(LEFT_MARK).rstrip(RIGHT_MARK)
