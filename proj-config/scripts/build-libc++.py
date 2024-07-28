import subprocess
import time


print('>>> Building...', flush=True, end='')

start_time = time.time()
proc = subprocess.run(["cmake", "--build", "."], stdout=subprocess.PIPE, text=True, stderr=subprocess.STDOUT)
elapsed = time.time() - start_time

print(f' built in {elapsed:.1f}s', flush=True, end='')
if proc.returncode != 0:
    print(f' ; with error code {proc.returncode}')
    print('::group::Output')
    print(proc.stdout)
    print('::endgroup::', flush=True)
else:
    print(flush=True)
