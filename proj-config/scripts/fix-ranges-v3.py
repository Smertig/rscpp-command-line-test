import glob
import re
import os


def is_deprecated(path: str) -> bool:
    if os.path.basename(path) in ('tagged_tuple.hpp', "any.hpp"):
        return True

    with open(path) as f:
        text = f.read()

    return re.search('^RANGES_DEPRECATED_HEADER', text, re.MULTILINE) is not None


# Remove all deprecated headers
for path in glob.glob('include/range/**/*.hpp', recursive=True):
    if is_deprecated(path):
        os.remove(path)
        print(f'Removing deprecated {path}..')
