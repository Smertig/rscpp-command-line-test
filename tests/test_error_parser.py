import unittest

from util.error_parser import parse_logs, AnalyzerError


class MyTestCase(unittest.TestCase):
    def test_something(self):
        self._test_one('samples/resharper-logs-1.err.log', [
            AnalyzerError(
                "JetBrains.ReSharper.Feature.Services.Cpp.Daemon.CppConversionErrorsAnalyzer",
                "Unable to cast object of type 'JetBrains.ReSharper.Psi.Cpp.Types.CppUnknownType' to type 'JetBrains.ReSharper.Psi.Cpp.Types.CppFunctionType'",
                "<example>\\<range.v3.comprehension_conversion>\\comprehension_conversion.cpp"
            ),
            AnalyzerError(
                "JetBrains.ReSharper.Feature.Services.Cpp.Daemon.CppDeprecatedAttributeAnalyzer",
                "Unable to cast object of type 'JetBrains.ReSharper.Psi.Cpp.Types.CppUnknownType' to type 'JetBrains.ReSharper.Psi.Cpp.Types.CppFunctionType'",
                "<example>\\<range.v3.comprehension_conversion>\\comprehension_conversion.cpp"
            ),
            AnalyzerError(
                "JetBrains.ReSharper.Feature.Services.Cpp.Daemon.CppExpressionErrorsAnalyzer",
                "Unable to cast object of type 'JetBrains.ReSharper.Psi.Cpp.Types.CppUnknownType' to type 'JetBrains.ReSharper.Psi.Cpp.Types.CppFunctionType'",
                "<example>\\<range.v3.comprehension_conversion>\\comprehension_conversion.cpp"
            ),
            AnalyzerError(
                "JetBrains.ReSharper.Feature.Services.Cpp.Daemon.CppBinaryExpressionAnalyzer",
                "Unable to cast object of type 'JetBrains.ReSharper.Psi.Cpp.Types.CppUnknownType' to type 'JetBrains.ReSharper.Psi.Cpp.Types.CppFunctionType'",
                "<example>\\<range.v3.comprehension_conversion>\\comprehension_conversion.cpp"
            ),
            AnalyzerError(
                "JetBrains.ReSharper.Feature.Services.Cpp.Daemon.CppOverloadingErrorsAnalyzer",
                "Unable to cast object of type 'JetBrains.ReSharper.Psi.Cpp.Types.CppUnknownType' to type 'JetBrains.ReSharper.Psi.Cpp.Types.CppFunctionType'",
                "<example>\\<range.v3.comprehension_conversion>\\comprehension_conversion.cpp"
            ),
        ])

    def _test_one(self, file_path, expected_errors):
        with open(file_path, encoding='cp1251') as f:
            log = f.read()

        errors = parse_logs(log)
        self.assertEqual(errors, expected_errors)


if __name__ == '__main__':
    unittest.main()
