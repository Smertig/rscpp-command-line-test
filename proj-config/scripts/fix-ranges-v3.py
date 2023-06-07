import glob
import re
import os


def is_deprecated(path: str) -> bool:
    base_name = os.path.basename(path)
    if base_name in ('tagged_tuple.hpp', 'tagged_pair.hpp'):
        return True

    if base_name in ('iterator_range.hpp',):
        return False

    with open(path) as f:
        text = f.read()

    return re.search('^RANGES_DEPRECATED_HEADER', text, re.MULTILINE) is not None


# Remove all deprecated headers
for path in glob.glob('include/range/**/*.hpp', recursive=True):
    if is_deprecated(path):
        os.remove(path)
        print(f'Removing deprecated {path}..')
