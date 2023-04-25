import json
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from subprocess import Popen, PIPE

import common


def print_errors(title, errors):
    if errors:
        print(title + " errors:")
        for f, l, m in errors:
            print(json.dumps({"file" : f, "line" : l, "message" : m}))
                

def check_report(report_file, known_errors):
    issue_nodes = ET.parse(report_file).getroot().findall("Issues")[0]
    if len(issue_nodes) == 0:
        print("No compilation errors found")
        if known_errors:
            print("But {0} errors were expected".format(len(known_errors)))
            return "no compilation errors found, but {0} errors were expected".format(len(known_errors))
        else:
            return None
    else:
        errors = set([(issue.get("File"), issue.get("Line"), issue.get("Message")) for issue in issue_nodes.iter("Issue")])
        if known_errors:
            expected_errors = set([(issue["file"], issue["line"], issue["message"]) for issue in known_errors])
            unexpected_errors = errors.difference(expected_errors)
            missing_errors = expected_errors.difference(errors)
            print_errors("Unexpected", unexpected_errors)
            print_errors("Missing", missing_errors)
            if not unexpected_errors and not missing_errors:
                assert(len(expected_errors) == len(errors))
                print("{0} errors found as expected".format(len(errors)))
                return None
            else:
                return "expected and actual set of errors differ"
        else:
            print_errors("Unexpected", errors)
            return "unexpected {0} errors found".format(len(errors))


def run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props):
    args, report_file = common.inspect_code_run_arguments(project_dir, sln_file, project_to_check, msbuild_props)
    args.insert(0, env.inspect_code_path)
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


def check_project(project, project_dir, sln_file):
    project_to_check = project.get("project to check")
    msbuild_props = project.get("msbuild properties")
    report_file, output = run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props)
    expected_files_count = project.get("inspected files count")
    actual_files_count = common.inspected_files_count(output)
    if expected_files_count:
        if expected_files_count != actual_files_count:
            print("expected count of inspected files is {0}, but actual is {1}".format(expected_files_count, actual_files_count))
    else:
        print("count of inspected files is ", actual_files_count)
    return check_report(report_file, project.get("known errors"))


def process_project_with_cmake_generator(project, project_name, cmake_generator: str):
    project_dir, sln_file = common.prepare_project(project_name, project, cmake_generator)
    result = check_project(project, project_dir, sln_file)
    if result:
        return "(" + cmake_generator + ") " + result


def process_project(project_name, project):
    project = common.read_conf_if_needed(project)

    if "custom build tool" in project:
        project_dir, sln_file = common.prepare_project(project_name, project, None)
        return check_project(project, project_dir, sln_file)

    available_generators = common.get_compatible_generators(project)
    if not available_generators:
        return f'({project_name}) no available generators found'

    for generator in available_generators:
        result = process_project_with_cmake_generator(project, project_name, generator)
        if result:
            return result


args = common.argparser.parse_args()
env = common.load_env(args)


def main():
    summary = []
    start_time = time.time()

    project_names = args.project.split(',') if args.project else common.projects.keys()
    for project_name in project_names:
        print(f"processing project {project_name}...", flush=True)

        try:
            result = process_project(project_name, common.projects[project_name])
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
