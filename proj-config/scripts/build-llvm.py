import itertools
import pathlib
import re
import subprocess
import time

build_targets = []


def find_targets(file_path, regex: re.Pattern):
    with open(file_path) as f:
        return (m.group(1) for m in regex.finditer(f.read()))


dirs_to_search = [
    pathlib.Path('../clang'),
    pathlib.Path('../llvm/lib/Target/AArch64')
]

for path in itertools.chain(dir_path.rglob('CMakeLists.txt') for dir_path in dirs_to_search):
    new_targets = []
    new_targets.extend(find_targets(path, re.compile(r'add_public_tablegen_target\(([a-zA-Z0-9_]+)\)')))
    new_targets.extend(find_targets(path, re.compile(r'clang_tablegen\([^)]+TARGET ([a-zA-Z0-9_]+)', re.DOTALL)))
    if new_targets:
        print(f'Build targets for {path}: {new_targets}')
        build_targets += new_targets

print(f'>>> Found {len(build_targets)} target(s) to build: {build_targets}', flush=True)

for gen_target in build_targets:
    print(f'>>> Building target {gen_target}...', flush=True, end='')

    start_time = time.time()
    proc = subprocess.run(["cmake", "--build", ".", "--target", gen_target], stdout=subprocess.PIPE, text=True, stderr=subprocess.STDOUT)
    elapsed = time.time() - start_time

    print(f' built in {elapsed:.1f}s', flush=True, end='')
    if proc.returncode != 0:
        print(f' ; with error code {proc.returncode}')
        print('::group::Output')
        print(proc.stdout)
        print('::endgroup::', flush=True)
    else:
        print(flush=True)
