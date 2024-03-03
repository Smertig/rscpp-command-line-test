import os
import shutil
import subprocess

import utils

IRRLICHTMT_PATH = 'lib/irrlichtmt'

with open("misc/irrlichtmt_tag.txt") as f:
    irrlicht_tag = f.read().strip()

if os.path.exists(IRRLICHTMT_PATH):
    shutil.rmtree(IRRLICHTMT_PATH)

subprocess.check_call([
    "git",
    "clone",
    "--depth", "1",
    "--branch", irrlicht_tag,
    "https://github.com/minetest/irrlicht.git",
    IRRLICHTMT_PATH
])

# WAT?
utils.update_file('lib/gmp/mini-gmp.c', lambda content: content.replace(b'\x0C', b''))
