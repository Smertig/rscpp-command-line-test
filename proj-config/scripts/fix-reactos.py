import io
import os
import requests
import py7zr

bin_path = os.path.join(os.environ['BUILD_DIR'], 'bin')

response = requests.get('https://svn.reactos.org/storage/vperevertkin/flexbison.7z')
with py7zr.SevenZipFile(io.BytesIO(response.content)) as archive:
    archive.extractall(path=bin_path)
