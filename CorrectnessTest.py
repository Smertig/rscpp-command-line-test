import datetime
import json
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import git
from subprocess import Popen, PIPE
from typing import Optional, Tuple

import common


def print_errors(title, errors):
    if errors:
        json_errors = ("  " + json.dumps({"file": f, "line": l, "message": m}) for f, l, m in sorted(errors))
        print(f"{title} errors:")
        print(",\n".join(json_errors))


def is_flaky(error: dict) -> bool:
    return error.get("flaky", False)


def check_report(report_file, known_errors) -> Tuple[Optional[str], dict]:
    result: Optional[str] = None
    error_mismatch = False

    xml_doc = ET.parse(report_file)
    issue_nodes = xml_doc.getroot().findall("Issues")[0]
    if len(issue_nodes) == 0:
        print("No compilation errors found")
        known_stable_errors = [error for error in known_errors if is_flaky(error)]
        if known_stable_errors:
            print_errors("Expected", known_stable_errors)
            result = f"no compilation errors found, but {len(known_stable_errors)} errors were expected"
            error_mismatch = True
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
            else:
                result = "expected and actual set of errors differ"
                error_mismatch = True
        else:
            print_errors("Unexpected", actual_errors)
            result = f"unexpected {len(actual_errors)} errors found"
            error_mismatch = True

    return result, {
        'tool_version': xml_doc.getroot().attrib['ToolsVersion'],
        'error_mismatch': error_mismatch
    }


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


def check_project(project, project_dir, sln_file, branch: Optional[str]) -> Tuple[Optional[str], dict]:
    project_to_check = project.get("project to check")
    msbuild_props = project.get("msbuild properties")
    use_x64 = project.get("use x64", False)

    start_time = time.time()
    report_file, output = run_inspect_code(project_dir, sln_file, project_to_check, msbuild_props, use_x64)
    end_time = time.time()

    local_config = project["latest"][branch] if branch else project["stable"]
    expected_files_count = local_config.get("inspected files count")
    actual_files_count = common.inspected_files_count(output)
    if expected_files_count:
        if expected_files_count != actual_files_count:
            print(f"expected count of inspected files is {expected_files_count}, but actual is {actual_files_count}")
    else:
        print(f"count of inspected files is {actual_files_count}")

    result, report = check_report(report_file, local_config.get("known errors", []))
    report |= {
        'project': project_to_check,
        'timestamp': datetime.datetime.utcnow().timestamp(),
        'elapsed_time': end_time - start_time,
        'x64': use_x64,
        'actual_files_count': actual_files_count,
        'expected_files_count': expected_files_count,
    }
    return result, report


def process_project_with_cmake_generator(project, project_name, cmake_generator: str, branch: Optional[str]) -> Tuple[Optional[str], dict]:
    project_dir, sln_file = common.prepare_project(project_name, project, cmake_generator, branch)
    result, report = check_project(project, project_dir, sln_file, branch)
    if result:
        result = f"({cmake_generator}) {result}"
    return result, report


def process_project(project_name, project, branch: Optional[str]) -> Tuple[Optional[str], dict]:
    project = common.read_conf_if_needed(project)

    available_toolchains = common.get_compatible_toolchains(project)
    if not available_toolchains:
        return f'({project_name}) no available toolchains found', {}

    if "custom build tool" in project:
        project_dir, sln_file = common.prepare_project(project_name, project, None, branch)
        result, default_report = check_project(project, project_dir, sln_file, branch)
        toolchain_reports = {
            'default': default_report
        }
    else:
        result = None
        toolchain_reports = {}
        for generator in available_toolchains:
            local_result, local_report = process_project_with_cmake_generator(project, project_name, generator, branch)
            toolchain_reports[generator] = local_report
            if local_result:
                result = local_result
                break

    report = {'toolchains': toolchain_reports}

    try:
        with git.Repo(env.get_project_dir(project_name)) as repo:
            last_commit = repo.commit()
            report['repo'] = {
                'url': repo.remote().url,
                'ref': last_commit.hexsha,
                'message': last_commit.message,
                'timestamp': last_commit.committed_datetime.timestamp()
            }
    except:
        pass

    return result, report


common.argparser.add_argument("--report-path", dest="report_path")
args = common.argparser.parse_args()
env = common.load_env(args)


def main():
    summary = []
    start_time = time.time()

    full_report = {}
    for project_name, project_branch in common.parse_projects(args.project):
        print(f"processing project {project_name} (branch: {project_branch})...", flush=True)

        try:
            result, report = process_project(project_name, common.projects[project_name], project_branch)
        except Exception as e:
            error_info = traceback.format_exc()
            print(error_info)

            result = f"exception: {e}"
            report = {
                'error': {
                    'exception': str(e),
                    'error_info': error_info
                }
            }

        report_key = f"{project_name}:{project_branch}" if project_branch else project_name
        full_report[report_key] = report

        if result:
            summary.append(project_name + ": " + result)

        print('-------------------------------------------------------', flush=True)

    # Dump report if needed
    report_path = args.report_path
    if report_path:
        common.create_parents(report_path)
        with open(report_path, 'w') as f_report:
            json.dump(full_report, f_report, indent=4)

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
