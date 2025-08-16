import argparse
import hashlib
import platform
import shutil
import tarfile
import zipfile
from pathlib import Path

from client.scan.files import rscan_files
from client.system import windows_check
from helper import Project, run_command


def hash_file(filepath: Path) -> str:
    hasher = hashlib.sha256()
    with filepath.open('rb') as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def archive(packaging_path: Path, files: list[tuple[Path, Path]]) -> None:
    system = platform.system()
    archive_path = packaging_path.with_suffix('.zip' if system != 'Windows' else '.tar.gz')
    archive_path.parent.mkdir(parents=True, exist_ok=True)

    if system == 'Windows':
        with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, file in files:
                zipf.write(file, arcname=file.relative_to(root))
    else:
        with tarfile.open(archive_path, 'w:gz') as tar:
            for root, file in files:
                tar.add(file, arcname=file.relative_to(root))


def collect(collect_path: Path, files: list[tuple[Path, Path]]) -> None:
    collect_files = [file.name for _, file in files]
    collect_path.mkdir(parents=True, exist_ok=True)

    for file in rscan_files(collect_path):
        if file.name in collect_files:
            continue
        file.unlink()

    for root, file in files:
        collect_file = collect_path / file.relative_to(root)
        if collect_file.exists() and hash_file(collect_file) == hash_file(file):
            continue
        collect_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(file, collect_file.parent)


def build(project: Project, build_path: Path, default_args: list[str]) -> list[tuple[Path, Path]]:
    files: list[tuple[Path, Path]] = []
    for script in project.scripts:
        out_dir = build_path / script.name
        out_dir.mkdir(parents=True, exist_ok=True)

        args = [
            f'--output-dir={out_dir}',
            f'--output-filename={script.name}',
            str(script.path),
        ]

        if 'gtk4' in str(script.path):
            args.append('--include-module=gi._enum')
        if not script.console:
            args.append('--windows-console-mode=disable')

        run_command(default_args + args)

        dist_dir = out_dir / f'{script.path.stem}.dist'
        system = platform.system()
        if system != 'Windows':
            app_path = dist_dir / script.name
            app_path.chmod(app_path.stat().st_mode | 0o111)

        existing_names = {f.name for _, f in files}
        for file in rscan_files(dist_dir):
            if file.name in existing_names:
                continue
            if file.parent.name == '__pycache__':
                continue
            files.append((dist_dir, file))

    return files


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('--archive', action='store_true')
    parser.add_argument('--suffix')

    args = parser.parse_args()
    directory = Path(args.directory).absolute()

    if args.suffix and not args.archive:
        parser.error('--suffix can only be used with --archive')

    project = Project()

    build_path = project.root / 'build'
    resources_path = project.root / 'resources'
    icon_path = resources_path / f'{project.name}.ico'

    is_dev = 'dev' in project.version
    version = '.'.join(map(str, project.version_tuple))
    product_version = '.'.join(map(str, project.version_tuple[:2]))

    default_args = [
        f'nuitka{".cmd" if windows_check() else ""}',
        '--standalone',
        '--assume-yes-for-downloads',
        f'--windows-icon-from-ico={icon_path}',
        f'--company-name={project.company_name}',
        f'--product-name={project.name}',
        f'--file-version={version}',
        f'--product-version={product_version}',
        f'--file-description={project.description}',
        f'--copyright={project.copyright}',
    ]
    if not is_dev:
        default_args.append('--enable-plugins=upx')

    files = build(project, build_path, default_args)

    if args.archive:
        name = project.name + f'-{args.suffix}' * bool(args.suffix)
        packaging_path = directory / name
        archive(packaging_path, files)
    else:
        collect(directory, files)


if __name__ == '__main__':
    main()
