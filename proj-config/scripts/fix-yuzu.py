import os.path
import subprocess


def update_file(path, callback):
    with open(path, 'rb') as f:
        content = f.read()
    content = callback(content)
    with open(path, 'wb') as f:
        f.write(content)


# Build required tool
GLS_LANG_DIR = "tools/glslang"
GLS_LANG_BUILD_DIR = f"{GLS_LANG_DIR}/build"
GLS_VALIDATOR_PATH = f"{GLS_LANG_BUILD_DIR}/StandAlone/Debug/glslangValidator.exe"

subprocess.run(["cmake", "-S", GLS_LANG_DIR, "-B", GLS_LANG_BUILD_DIR], check=True)
subprocess.run(["cmake", "--build", GLS_LANG_BUILD_DIR], check=True)


def fix_gls_validator_path(content: bytes) -> bytes:
    gls_validator_path = os.path.realpath(GLS_VALIDATOR_PATH).replace("\\", "/")
    return content \
        .replace(b'find_program(GLSLANGVALIDATOR "glslangValidator")', f'set(GLSLANGVALIDATOR "{gls_validator_path}")'.encode('utf8'))


update_file("src/video_core/host_shaders/CMakeLists.txt", fix_gls_validator_path)
