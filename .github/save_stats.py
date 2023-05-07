import json
import os
import sys
import pathlib


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
                    cache_path = f'{repo_path}/{project_name}/{branch or "stable"}_{toolchain_name}.json'
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

    return 0


if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
