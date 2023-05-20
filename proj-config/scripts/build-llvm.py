import pathlib
import re
import subprocess
import time

build_targets = []


def find_targets(file_path, regex: re.Pattern):
    with open(file_path) as f:
        return (m.group(1) for m in regex.finditer(f.read()))


for path in pathlib.Path('../clang').rglob('CMakeLists.txt'):
    build_targets.extend(find_targets(path, re.compile(r'add_public_tablegen_target\(([a-zA-Z_]+)\)')))
    build_targets.extend(find_targets(path, re.compile(r'clang_tablegen\([^)]+TARGET ([a-zA-Z_]+)', re.DOTALL)))


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
