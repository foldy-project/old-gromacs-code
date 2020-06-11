import os

def cleanup(startswith: str):
    for file in os.listdir('.'):
        if file.startswith(startswith):
            os.unlink(file)