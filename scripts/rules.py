import json
import platform
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from collections.abc import Iterator
from functools import cached_property
from pathlib import Path
from typing import Union, cast

from attrs import define, field
from cattrs import Converter

TOMLPrimitive = str | int | float | bool | None
TOMLValue = TOMLPrimitive | list['TOMLValue'] | dict[str, Union['TOMLValue', 'TOMLDict']]
TOMLDict = dict[str, Union[TOMLValue, 'TOMLDict']]

IGNORE_LINTER_PATTERNS = [
    'AIR',  # Airflow
    'ERA',  # eradicate
    'FAST',  # FastAPI
    'ASYNC',  # flake8-async
    'CPY',  # flake8-copyright
    'DTZ',  # flake8-datetimez
    'DJ',  # flake8-django
    'FIX',  # flake8-fixme
    'FA',  # flake8-future-annotations
    'TD',  # flake8-todos
    'NPY',  # NumPy-specific rules
    'PD',  # pandas-vet
    'DOC',  # pydoclint
    'D',  # pydocstyle
]
IGNORE_RULE_PATTERNS = [
    'S404',  # suspicious-subprocess-import
    'S603',  # subprocess-without-shell-equals-true
    'COM812',  # missing-trailing-comma
    'ISC001',  # single-line-implicit-string-concatenation
    'PLC0415',  # import-outside-top-level
    'Q000',  # bad-quotes-inline-string
    'Q003',  # avoidable-escaped-quote
    'TC006',  # runtime-cast-value
]

DEFAULT_CONFIG: TOMLDict = {
    'fix': True,
    'unsafe-fixes': True,
    'line-length': 100,
    'output-format': 'grouped',
    'target-version': f'py{"".join(platform.python_version().split(".")[:2])}',
    'exclude': [
        '.git',
        '.mypy_cache',
        '.pytest_cache',
        '.ruff_cache',
        '.venv',
        '.tox',
        'build',
        'dist',
        'node_modules',
    ],
    'format': {
        'preview': True,
        'quote-style': 'single',
        'docstring-code-format': True,
        'docstring-code-line-length': 80,
    },
    'lint': {
        'preview': True,
        'flake8-tidy-imports': {'ban-relative-imports': 'all'},
        'flake8-pytest-style': {
            'fixture-parentheses': False,
            'mark-parentheses': False,
        },
        'isort': {'known-first-party': ['tests']},
        'per-file-ignores': {
            '**/scripts/*': [
                'INP001',  # implicit-namespace-package
            ],
            '**/tests/**/*': [
                'SLF001',  # private-member-access
                'S101',  # assert
            ],
        },
    },
}


@define
class RuffCategories:
    prefix: str
    name: str


@define
class RuffLinter(RuffCategories):
    categories: list[RuffCategories] | None = None


@define
class RuffRule:
    name: str
    code: str
    linter: str


def run_ruff_command(*args: str) -> TOMLValue:
    process = subprocess.run(
        [sys.executable, '-m', 'ruff', *args, '--output-format', 'json'],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding='utf-8',
        check=False,
    )
    if process.returncode:
        raise OSError(process.stdout)

    return cast(TOMLValue, json.loads(process.stdout))


def unique_merge(l1: list[TOMLValue], l2: list[TOMLValue]) -> TOMLValue:
    seen: set[str] = set()
    result: list[TOMLValue] = []
    for item in l1 + l2:
        if (key := str(item)) not in seen:
            seen.add(key)
            result.append(item)
    return result


def deep_merge(d1: TOMLDict, d2: TOMLDict) -> TOMLDict:
    result = d1.copy()
    for k, v in d2.items():
        if k in result:
            match (result[k], v):
                case (dict() as dict1, dict() as dict2):
                    result[k] = deep_merge(dict1, dict2)
                case (list() as list1, list() as list2):
                    result[k] = unique_merge(list1, list2)
                case _:
                    result[k] = v
        else:
            result[k] = v
    return result


@define
class Ruff:
    root: Path
    _converter: Converter = field(factory=Converter, init=False)

    @cached_property
    def config_file(self) -> Path:
        return self.root / 'ruff.toml'

    def get_config(self, section: str, default: TOMLValue | TOMLDict = None) -> TOMLValue:
        if self._config_file is None:
            return default

        sections = section.split('.')
        if len(sections) > 1:
            config = cast(TOMLDict, self.get_config(sections[0], {}))
            for part in sections[1:]:
                config = cast(TOMLDict, config.get(part, default))
            return config

        return self.user_config.get(section, default)

    @cached_property
    def is_preview(self) -> bool:
        return cast(bool, self.get_config('lint.preview', default=False))

    @cached_property
    def user_config(self) -> TOMLDict:
        if self._config_file is None:
            return {}

        user_config = tomllib.loads(self._config_file.read_text())

        if self._config_file.name == 'pyproject.toml':
            if 'tool' in user_config:
                return deep_merge(DEFAULT_CONFIG, user_config['tool'].get('ruff', {}))
            return DEFAULT_CONFIG
        return deep_merge(DEFAULT_CONFIG, user_config)

    @cached_property
    def linter(self) -> dict[str, str]:
        raw_linter_data = cast(list[TOMLDict], run_ruff_command('linter'))
        linter_dict: dict[str, str] = {}
        for linter in raw_linter_data:
            ruff_linter = self._converter.structure(linter, RuffLinter)
            if ruff_linter.categories:
                for category in ruff_linter.categories:
                    code = f'{ruff_linter.prefix}{category.prefix}'
                    name = f'{ruff_linter.name}({category.name})'
                    linter_dict[code] = name
            else:
                linter_dict[ruff_linter.prefix] = ruff_linter.name

        return linter_dict

    def get_linter(self, code: str) -> str | None:
        for rules in self._rules.values():
            for rule in rules:
                if code == rule.code:
                    return self._get_linter(rule)
        return None

    @cached_property
    def rules(self) -> dict[str, str]:
        rule_dict: dict[str, str] = {}
        for rules in self._rules.values():
            for rule in rules:
                rule_dict[rule.code] = rule.name
        return rule_dict

    def get_rules(self, code_linter: str) -> Iterator[str]:
        for rule in self._rules[code_linter]:
            yield rule.code

    @cached_property
    def _config_file(self) -> Path | None:
        for possible_config in ('.ruff.toml', 'ruff.toml', 'pyproject.toml'):
            if (config_file := (self.root / possible_config)).is_file():
                return config_file

        return None

    def _get_linter(self, rule: RuffRule) -> str | None:
        for code, name in self.linter.items():
            if rule.linter in name and code in rule.code:
                return code
        return None

    @cached_property
    def _rules(self) -> dict[str, list[RuffRule]]:
        removed_pattern = re.compile(
            r'^\s*#+\s+(removed|removal)', flags=re.IGNORECASE | re.MULTILINE
        )
        raw_rule_data = cast(list[TOMLDict], run_ruff_command('rule', '--all'))
        rule_dict: dict[str, list[RuffRule]] = defaultdict(list)
        for rule in raw_rule_data:
            if removed_pattern.search(cast(str, rule.get('explanation'))):
                continue
            if not self.is_preview and cast(bool, rule.get('preview', False)):
                continue
            ruff_rule = self._converter.structure(rule, RuffRule)
            linter = self._get_linter(ruff_rule)
            if linter:
                rule_dict[linter].append(ruff_rule)
        return rule_dict

    @cached_property
    def config(self) -> dict[str, TOMLDict]:
        return cast(dict[str, TOMLDict], run_ruff_command('config'))

    def _scan_config(
        self, toml_data: TOMLDict, prefix: str = ''
    ) -> Iterator[tuple[str, str, TOMLValue]]:
        for key, data in toml_data.items():
            config = f'{prefix}{key}'
            config_info = self.config.get(config)
            if config_info and not config_info.get('deprecated'):
                if isinstance(data, dict):
                    for dict_key, dict_data in data.items():
                        yield config, dict_key, dict_data
                else:
                    yield prefix.strip('.'), key, data
            elif isinstance(data, dict):
                yield from self._scan_config(data, f'{config}.')

    def write(self) -> None:
        user_config: dict[str, list[tuple[str, TOMLValue]]] = defaultdict(list)
        for key, part, value in self._scan_config(self.user_config):
            user_config[key].append((part, value))

        lines: list[str] = []
        for key, config in user_config.items():
            if key:
                lines.extend(('', f'[{key}]'))

            for part, value in config:
                formatted_value: TOMLValue
                formatted_part = f'"{part}"' if '*' in part else part
                match value:
                    case str():
                        formatted_value = f'"{value}"'
                    case bool():
                        formatted_value = str(value).lower()
                    case list():
                        if not value:
                            continue
                        lines.append(f'{formatted_part} = [')
                        for idx, code in enumerate(cast(list[str], value)):
                            comment = self.linter.get(code) or self.rules.get(code)
                            comma = ',' if idx < len(value) - 1 else ''
                            comment_str = f'  # {comment}' if comment else ''
                            lines.append(f'  "{code}"{comma}{comment_str}')

                        lines.append(']')
                        continue
                    case _:
                        formatted_value = value
                lines.append(f'{formatted_part} = {formatted_value}')

        lines.append('')

        self.config_file.write_text('\n'.join(lines))


def build_linter_regex(ignore_linter: list[str], lint_select: list[str]) -> re.Pattern[str]:
    linter_pattern = [
        linter for linter in IGNORE_LINTER_PATTERNS + ignore_linter if linter not in lint_select
    ]
    return re.compile(f'^({"|".join(linter_pattern)})$')


def filter_rules(
    ruff: Ruff,
    linter_rules: list[str],
    select_rules: list[str],
    rule_regex: re.Pattern[str],
    linter_regex: re.Pattern[str],
) -> tuple[list[TOMLValue], list[TOMLValue]]:
    selected_rules: list[TOMLValue] = [code for code in select_rules if not rule_regex.match(code)]
    ignored_rules: list[TOMLValue] = []

    for code in linter_rules:
        if linter_regex.match(code):
            continue

        rules = list(ruff.get_rules(code))
        filtered = [rule for rule in rules if rule_regex.match(rule)]

        len_rules = len(rules)
        len_filtered = len(filtered)
        if len_filtered == len_rules:
            continue

        if filtered:
            if (len_rules - len_filtered) == 1:
                selected_rules.extend([rule for rule in rules if rule not in filtered])
                continue
            ignored_rules.extend(filtered)

        selected_rules.append(code)

    return selected_rules, ignored_rules


def main() -> None:
    root_path = Path().absolute()
    ruff = Ruff(root_path)

    lint_select = cast(list[str], ruff.get_config('lint.select', []))
    lint_ignore = cast(list[str], ruff.get_config('lint.ignore', []))
    linter_rules = list(ruff.linter.keys())

    rule_regex = re.compile(f'^({"|".join(IGNORE_RULE_PATTERNS + lint_ignore)})$')
    select_rules = [rule for rule in lint_select if rule not in linter_rules]
    ignore_linter = [linter for rule in select_rules if (linter := ruff.get_linter(rule))]

    linter_regex = build_linter_regex(ignore_linter, lint_select)

    selected_rules, ignored_rules = filter_rules(
        ruff, linter_rules, select_rules, rule_regex, linter_regex
    )

    ruff_lint = cast(TOMLDict, ruff.user_config['lint'])
    ruff_lint['select'] = selected_rules
    ruff_lint['ignore'] = ignored_rules

    rules = list(ruff.rules.keys())

    per_file_ignores = cast(dict[str, list[str]], ruff_lint['per-file-ignores'])
    for file, rules in per_file_ignores.items():
        per_file_ignores[file] = [
            rule
            for rule in rules
            if rule not in ignored_rules
            if ruff.get_linter(rule) in selected_rules
        ]

    ruff.write()


if __name__ == '__main__':
    main()
