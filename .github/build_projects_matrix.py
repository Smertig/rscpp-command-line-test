import json
import os.path
import sys

assert len(sys.argv) == 3

with open(sys.argv[1]) as f:
    projects = json.load(f)

matrix = {"include": []}
for project_name, project_config in projects.items():
    if isinstance(project_config, str):
        assert project_config.endswith(".json")
        with open(os.path.join(sys.argv[2], project_config)) as f:
            project_config = json.load(f)

    cmake_gens = project_config.get("cmake generators")
    if cmake_gens == ["2017-x64"]:
        # TODO: support or upgrade?
        continue

    matrix["include"].append({"projects": project_name})

escaped_matrix = json.dumps(matrix)
print(f"matrix<<EOF\n{escaped_matrix}\nEOF")
