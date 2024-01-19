import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
import gdown

assert len(sys.argv) == 2, f"Usage: {sys.argv[0]} tool_version"

JB_TOOL_NAME = 'JetBrains.ReSharper.GlobalTools'
JB_TOOL_VERSION_RE = re.compile(r'JetBrains\.ReSharper\.GlobalTools\.(.*)\.nupkg')


def install_tool(tool_name: str, version: str = None, extra_args: list = None):
    args = [
        'dotnet',
        'tool',
        'update',
        '--global',
        tool_name
    ]

    if version is not None:
        args += ['--version', version]

    if extra_args is not None:
        args += extra_args

    return subprocess.check_call(args)


def retry_while_none(callback, tries: int, delay: int):
    for i in range(tries):
        result = callback()
        if result is not None:
            return result

        print(f"Attempt {i+1} failed, retrying in {delay} seconds.")
        time.sleep(delay)
        delay = delay * 2

    raise Exception(f"Cannot get result in {tries} attemps.")


tool_version = sys.argv[1]
if tool_version.startswith('gdrive:'):
    gdrive_id = tool_version.removeprefix('gdrive:')
    with tempfile.TemporaryDirectory() as package_dir:
        package_path = retry_while_none(
            lambda: gdown.download(id=gdrive_id, output=package_dir + os.sep),
            tries=3, delay=10
        )
        package_name = os.path.basename(package_path)

        m = JB_TOOL_VERSION_RE.match(package_name)
        if not m:
            raise Exception(f'invalid format of nupkg: \'{package_name}\'')

        tool_version = m.group(1)
        print(f'Parsed tool version: \'{tool_version}\'')

        install_tool(JB_TOOL_NAME, tool_version, ['--add-source', package_dir])
elif tool_version.startswith('https://uploads.jetbrains.com'):
    package_url = tool_version
    m = JB_TOOL_VERSION_RE.findall(package_url)
    if len(m) != 1:
        raise Exception(f'invalid format of nupkg url: \'{package_url}\'')

    tool_version = m[0]
    print(f'Parsed tool version: \'{tool_version}\'')
    package_name = f'{JB_TOOL_NAME}.{tool_version}.nupkg'

    with tempfile.TemporaryDirectory() as package_dir:
        urllib.request.urlretrieve(package_url, f'{package_dir}/{package_name}')
        install_tool(JB_TOOL_NAME, tool_version, ['--add-source', package_dir])
else:
    install_tool(JB_TOOL_NAME, tool_version)

github_output_path = os.getenv('GITHUB_OUTPUT')

if github_output_path is not None:
    user_profile = os.environ['USERPROFILE'].replace('\\', '/')
    tool_dir = f"{user_profile}/.dotnet/tools/.store/jetbrains.resharper.globaltools/{tool_version}/jetbrains.resharper.globaltools/{tool_version}/tools/netcoreapp3.1/any"
    print(f'Setting TOOL_DIR to {tool_dir}')

    with open(github_output_path, 'w') as f:
        f.write(f"TOOL_DIR={tool_dir}\n")

# Other tools:
install_tool('dotnet-trace')
