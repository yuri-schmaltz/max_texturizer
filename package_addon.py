"""Build a Blender ZIP that can locate this checkout's backend."""
import json
from pathlib import Path
import zipfile


def package_addon(project):
    project = Path(project).resolve()
    target = project / "max_texturizer.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for source in sorted((project / "blender_addon").glob("*.py")):
            archive.write(source, "blender_addon/" + source.name)
        archive.writestr("blender_addon/backend_location.json", json.dumps({"directory": str(project)}))
    return target


if __name__ == "__main__":
    print(package_addon(Path(__file__).resolve().parent))
