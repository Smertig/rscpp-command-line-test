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

assert len(sys.argv) == 3, f"{sys.argv[0]} projects.json proj-config-dir"

_, projects_path, projects_dir = sys.argv

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

    cmake_gens = project_config.get("required toolchain", [DEFAULT_GENERATOR])
    for cmake_gen in cmake_gens:
        conf = {
            "projects": project_name,
            "cmake_gen": cmake_gen
        }

        gen_conf = GENERATOR_TO_CONFIG.get(cmake_gen)
        if gen_conf is None:
            continue

        assert gen_conf, f"unknown cmake_generator: {cmake_gen}"
        conf.update(gen_conf)

        matrix["include"].append(conf)

escaped_matrix = json.dumps(matrix)
print(f"matrix<<EOF\n{escaped_matrix}\nEOF")
