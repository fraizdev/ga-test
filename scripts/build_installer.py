import argparse
import json
import os
from collections.abc import Iterator
from pathlib import Path

from attrs import Factory, define
from cattrs import Converter
from helper import Project, run_command
from jinja2 import Environment, FileSystemLoader

INSTALLER_VERSION = '1.0.0'


@define
class FormatVariant:
    mime: str | None = None
    extensions: list[str] | None = None


@define
class Format(FormatVariant):
    label: str = ''
    variants: list[FormatVariant] | None = None


@define
class Category:
    name: str
    formats: list[Format]


@define
class Config:
    media: str = ''
    shells: list[str] = Factory(list)
    categories: list[Category] = Factory(list)


def load_config(json_path: Path) -> Config:
    if not json_path.exists():
        return Config()
    data = json.loads(json_path.read_text(encoding='utf-8'))
    converter = Converter()
    return converter.structure(data, Config)


def verb_type(format_type: Format | FormatVariant) -> Iterator[tuple[str, str]]:
    if not format_type.extensions:
        return
    for extension in format_type.extensions:
        yield (extension, format_type.mime or '')


def collect_extensions(categories: list[Category]) -> list[tuple[str, str]] | None:
    extensions: list[tuple[str, str]] = []
    for category in categories:
        for format_type in category.formats:
            variants = format_type.variants
            if variants:
                for variant in variants:
                    extensions.extend(verb_type(variant))
            else:
                extensions.extend(verb_type(format_type))
    return extensions


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('directory')
    parser.add_argument('--binary', required=True)
    parser.add_argument('--arch', required=True)

    args = parser.parse_args()
    directory = Path(args.directory).absolute()
    staged_binary = Path(args.binary).absolute()

    project = Project()

    build_path = project.root / 'build'
    resources_path = project.root / 'resources'
    icon_path = resources_path / f'{project.name}.ico'

    filedir_list = [
        (Path(root).relative_to(staged_binary), filenames)
        for root, _, filenames in os.walk(staged_binary)
    ]

    installer_config = load_config(resources_path / 'config.json')

    config = {
        # Project metadata
        'name': project.name,
        'version': project.version,
        'description': project.description,
        'company': project.company_name,
        'copyright': project.copyright,
        'comment': '',
        'license': project.root / 'LICENSE',
        'url': project.homepage,
        # Paths
        'icon': icon_path,
        'directory': directory,
        # Build info
        'installer_version': INSTALLER_VERSION,
        # Files
        'staged_binary': staged_binary,
        'filedir_list': filedir_list,
        # Installer Config (MIME types / extensions)
        'media': installer_config.media,
        'shells': installer_config.shells,
        'extensions': collect_extensions(installer_config.categories),
    }

    env = Environment(loader=FileSystemLoader(project.root / 'template'), autoescape=True)
    template = env.get_template('installer.nsi.j2')

    nsi_content = template.render(config)

    nsi_path = build_path / 'installer.nsi'
    with nsi_path.open('w', encoding='locale') as f:
        f.write(nsi_content)

    directory.mkdir(exist_ok=True)
    run_command(['makensis', f'-Darch={args.arch}', str(nsi_path)])


if __name__ == '__main__':
    main()
