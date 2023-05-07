import json
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from subprocess import Popen, PIPE
from typing import Optional

import common


def print_errors(title, errors):
    if errors:
        json_errors = ("  " + json.dumps({"file": f, "line": l, "message": m}) for f, l, m in sorted(errors))
        print(f"{title} errors:")
        print(",\n".join(json_errors))


def is_flaky(error: dict) -> bool:
    return error.get("flaky", False)


def check_report(report_file, known_errors):
    issue_nodes = ET.parse(report_file).getroot().findall("Issues")[0]
    if len(issue_nodes) == 0:
        print("No compilation errors found")
        known_stable_errors = [error for error in known_errors if is_flaky(error)]
        if known_stable_errors:
            print_errors("Expected", known_stable_errors)
            return f"no compilation errors found, but {len(known_stable_errors)} errors were expected"
        else:
            return None
    else:
        actual_errors = set((issue.get("File"), int(issue.get("Line", "0")), issue.get("Message")) for issue in issue_nodes.iter("Issue"))
        if known_errors:
            def get_id(error):
                return error["file"], int(error["line"]), error["message"]

            unexpected_errors = actual_errors - set(get_id(error) for error in known_errors)
            print_errors("Unexpected", unexpected_errors)

            missing_errors = set(get_id(error) for error in known_errors if not is_flaky(error)) - actual_errors
            print_errors("Missing", missing_errors)

            if not unexpected_errors and not missing_errors:
                print(f"{len(actual_errors)} errors found as expected")
                return None
            else:
                return "expected and actual set of errors differ"
        else:
            print_errors("Unexpected", actual_errors)
            return f"unexpected {len(actual_errors)} errors found"


def run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props, use_x64: bool):
    args, report_file = common.inspect_code_run_arguments(project_dir, sln_file, project_to_check, msbuild_props)
    args.insert(0, env.inspect_code_path_x64 if use_x64 else env.inspect_code_path_x86)
    print(subprocess.list2cmdline(args))
    process = Popen(args, stdout=PIPE, text=True, encoding='cp1251')
    start = time.time()
    out, err = process.communicate()
    exit_code = process.wait()
    end = time.time()
    if exit_code != 0:
        print("Error: exit code = " + str(exit_code))
    if err:
        print("Error:")
        print(err)
    print("Elapsed time: " + common.duration(start, end))
    return report_file, out


def check_project(project, project_dir, sln_file, branch: Optional[str]):
    project_to_check = project.get("project to check")
    msbuild_props = project.get("msbuild properties")
    use_x64 = project.get("use x64", False)
    report_file, output = run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props, use_x64)

    local_config = project["latest"][branch] if branch else project
    expected_files_count = local_config.get("inspected files count")
    actual_files_count = common.inspected_files_count(output)
    if expected_files_count:
        if expected_files_count != actual_files_count:
            print(f"expected count of inspected files is {expected_files_count}, but actual is {actual_files_count}")
    else:
        print(f"count of inspected files is {actual_files_count}")

    return check_report(report_file, local_config.get("known errors", []))


def process_project_with_cmake_generator(project, project_name, cmake_generator: str, branch: Optional[str]):
    project_dir, sln_file = common.prepare_project(project_name, project, cmake_generator, branch)
    result = check_project(project, project_dir, sln_file, branch)
    if result:
        return f"({cmake_generator}) {result}"


def process_project(project_name, project, branch: Optional[str]):
    project = common.read_conf_if_needed(project)

    available_toolchains = common.get_compatible_toolchains(project)
    if not available_toolchains:
        return f'({project_name}) no available toolchains found'

    if "custom build tool" in project:
        project_dir, sln_file = common.prepare_project(project_name, project, None, branch)
        return check_project(project, project_dir, sln_file, branch)

    for generator in available_toolchains:
        result = process_project_with_cmake_generator(project, project_name, generator, branch)
        if result:
            return result


args = common.argparser.parse_args()
env = common.load_env(args)


def main():
    summary = []
    start_time = time.time()

    for project_name, project_branch in common.parse_projects(args.project):
        print(f"processing project {project_name} (branch: {project_branch})...", flush=True)

        try:
            result = process_project(project_name, common.projects[project_name], project_branch)
        except Exception as e:
            print(traceback.format_exc())
            result = f"exception: {e}"

        if result:
            summary.append(project_name + ": " + result)

        print('-------------------------------------------------------', flush=True)

    print("Total time: " + common.duration(start_time, time.time()))
    if len(summary) == 0:
        print("Summary: OK")
        return 0
    else:
        print("Summary: Fail")
        for s in summary:
            print("    " + s)
        return 1


if __name__ == '__main__':
    ret = main()
    sys.exit(ret)
