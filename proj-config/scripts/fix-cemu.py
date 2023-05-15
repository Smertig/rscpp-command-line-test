import utils

utils.insert_after('dependencies/ih264d/common/x86/ih264_platform_macros.h',
                   b'#include <immintrin.h>',
                   b'\r\n#include <Windows.h>\r\n#include <intrin.h>')
