import json
import os.path
import sys

DEFAULT_GENERATOR = "2019-x64"

GENERATOR_TO_CONFIG = {
    "2013-x64": None,
    "2017-x64": None,
    "2019-x64": {
        "os": "windows-2019",
        "VsInstallRoot": r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise",
        "VCTargetsPath": r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\MSBuild\Microsoft\VC\v160\\",
    },
    "2022-x64": {
        "os": "windows-2022",
    }
}

GENERATOR_TO_CONFIG["clang-cl-2019-x64"] = GENERATOR_TO_CONFIG["2019-x64"]


def is_slow_project(project_name: str):
    # TODO: extract average build time from stats
    return project_name in ('ITK', 'rocksdb', 'OpenCV', 'yuzu', 'minetest', 'Cemu', 'LLVM', 'tdlib')


assert len(sys.argv) == 6, f"{sys.argv[0]} projects.json proj-config-dir mode github_event github_run_all"

_, projects_path, projects_dir, mode, github_event, github_run_all = sys.argv

assert mode in ('correctness-fixed', 'correctness-latest'), f"unknown mode: {mode}"
IS_CORRECTNESS_FIXED = mode == 'correctness-fixed'
IS_CORRECTNESS_LATEST = mode == 'correctness-latest'
IS_SCHEDULED = github_event == 'schedule'
IS_RUN_ALL = github_run_all == 'true'

# Run slow projects only on schedule
RUN_SLOW_PROJECTS = IS_SCHEDULED or IS_RUN_ALL

with open(projects_path) as f:
    projects = json.load(f)

matrix = {"include": []}
for project_name, project_config in projects.items():
    if isinstance(project_config, str):
        assert project_config.endswith(".json")
        with open(os.path.join(projects_dir, project_config)) as f:
            project_config = json.load(f)

    if project_config.get("disabled", False):
        continue

    if not RUN_SLOW_PROJECTS and is_slow_project(project_name):
        continue

    cmake_gens = project_config.get("required toolchain", [DEFAULT_GENERATOR])
    for cmake_gen in cmake_gens:
        conf = {
            "project": project_name,
            "cmake_gen": cmake_gen
        }

        gen_conf = GENERATOR_TO_CONFIG.get(cmake_gen)
        if gen_conf is None:
            continue

        conf.update(gen_conf)

        cmake_root = project_config['sources'].get('root')
        if cmake_root:
            conf['rscpp_work_dir'] = f'{cmake_root}/build-{cmake_gen}'
        elif 'path to .sln' in project_config.get('custom build tool', {}):
            conf['rscpp_work_dir'] = ''
        else:
            conf['rscpp_work_dir'] = f'build-{cmake_gen}'

        if IS_CORRECTNESS_LATEST:
            latest_branches = project_config.get("latest")
            if not latest_branches:
                continue

            for latest_branch in latest_branches.keys():
                matrix["include"].append(conf | {"branch": latest_branch})
        elif IS_CORRECTNESS_FIXED:
            stable_branch = project_config.get("stable")
            if not stable_branch:
                continue

            matrix["include"].append(conf)

escaped_matrix = json.dumps(matrix)
print(f"matrix<<EOF\n{escaped_matrix}\nEOF")
