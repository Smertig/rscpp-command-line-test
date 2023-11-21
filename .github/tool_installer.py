import os
import subprocess
import sys

assert len(sys.argv) == 2, f"Usage: {sys.argv[0]} tool_version"

tool_version = sys.argv[1]

subprocess.check_call([
    'dotnet',
    'tool',
    'update',
    '--global',
    'JetBrains.ReSharper.GlobalTools',
    '--version',
    tool_version,
])

github_output_path = os.getenv('GITHUB_OUTPUT')

if github_output_path is not None:
    user_profile = os.environ['USERPROFILE'].replace('\\', '/')
    tool_dir = f"{user_profile}/.dotnet/tools/.store/jetbrains.resharper.globaltools/{tool_version}/jetbrains.resharper.globaltools/{tool_version}/tools/netcoreapp3.1/any"
    print(f'Setting TOOL_DIR to {tool_dir}')

    with open(github_output_path, 'w') as f:
        f.write(f"TOOL_DIR={tool_dir}\n")
