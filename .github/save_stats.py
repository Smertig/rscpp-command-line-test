import json
import os
import subprocess
import sys
import pathlib
import time


def main() -> int:
    assert len(sys.argv) == 3, f"{sys.argv[0]} reports_dir repo_path"
    _, reports_dir, repo_path = sys.argv

    for report_path in pathlib.Path(reports_dir).glob('*-report/report.json'):
        with open(report_path) as f_report:
            report = json.load(f_report)
            for project_name, toolchains in report.items():
                branch = None
                if ':' in project_name:
                    project_name, branch = project_name.split(':', 1)

                for toolchain_name, project_report in toolchains.items():
                    # FIXME: improve me
                    if toolchain_name == 'ERROR':
                        continue

                    cache_path = f'{repo_path}/reports/{project_name}/{branch or "stable"}_{toolchain_name}.json'
                    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

                    # load existing cache
                    cache = {'v1': []}
                    if os.path.exists(cache_path):
                        with open(cache_path) as f_cache:
                            cache = json.load(f_cache)

                    # update
                    cache['v1'].append(project_report)

                    # dump cache
                    with open(cache_path, 'w') as f_cache:
                        json.dump(cache, f_cache, indent=4)

    all_reports = {}
    all_reports_dir = pathlib.Path(repo_path) / 'reports'
    for project_dir in all_reports_dir.iterdir():
        if not project_dir.is_dir():
            continue

        all_reports[project_dir.name] = list(path.name for path in project_dir.glob('*.json'))

    repo_url = subprocess.run(['git', 'config', '--get', 'remote.origin.url'], text=True, stdout=subprocess.PIPE, cwd=repo_path).stdout.strip()
    last_update = time.time()

    with open(all_reports_dir / 'all.json', 'w') as f:
        json.dump({
            'last_update': last_update,
            'repo_url': repo_url,
            'reports': all_reports
        }, f, indent=4)

    return 0


if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
