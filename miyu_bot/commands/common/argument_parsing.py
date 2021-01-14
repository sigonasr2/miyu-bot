import re

# https://stackoverflow.com/questions/249791/regex-for-quoted-string-with-escaping-quotes
# https://stackoverflow.com/questions/21105360/regex-find-comma-not-inside-quotes
from collections import namedtuple
from typing import Dict, List, Optional, Container, Any, Union, Callable

_param_re = re.compile(
    r'(([a-zA-Z]+)(!=|>=|<=|>|<|==|=)(("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,\s]+)(,("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,\s]+))*))')
_param_operator_re = re.compile(r'!=|==|=|>|<|>=|<=')
_param_argument_re = re.compile(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,\s]+)')
_param_string_re = re.compile(r'("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\')')
_param_re_with_post_space = re.compile(
    r'([a-zA-Z]+)(!=|==|=|>|<|>=|<=)(("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,\s]+)(,("(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'|[^,\s]+))*) ?')

NamedArgument = namedtuple('NamedArgument', 'name operator value')
ArgumentValue = namedtuple('ArgumentValue', 'value operator')


def _parse_named_argument(arg):
    groups = _param_re.fullmatch(arg).groups()
    name = groups[1]
    operator = groups[2]
    values = [value[1:-1] if _param_string_re.fullmatch(value) else value for value in
              _param_argument_re.findall(groups[3])]
    return NamedArgument(name, operator, values)


def parse_arguments(arg):
    named_arguments_parsed = [_parse_named_argument(na[0]) for na in _param_re.findall(arg)]
    text_argument = _param_re_with_post_space.sub('', arg)
    named_arguments = {}
    for na in named_arguments_parsed:
        if na.name not in named_arguments:
            named_arguments[na.name] = []
        named_arguments[na.name].append(ArgumentValue(na.value, na.operator))
    return ParsedArguments(text_argument.strip(), named_arguments)


class ArgumentError(Exception):
    pass


class ParsedArguments:
    text_argument: str
    named_arguments: Dict[str, List[ArgumentValue]]

    def __init__(self, text, named_arguments):
        self.text_argument = text
        self.named_arguments = named_arguments
        self.used = set()

    def single(self, name: str, default: Any = None, allowed_operators: Optional[Container] = None,
               is_list=False, numeric=False, converter: Union[dict, Callable] = lambda n: n):
        if allowed_operators is None:
            allowed_operators = {'>', '<', '>=', '<=', '!=', '==', '='}
        if not isinstance(default, tuple):
            default = ArgumentValue(default, '=')
        self.used.add(name)
        value = self.named_arguments.get(name)
        if value is None:
            return default
        if len(value) != 1:
            raise ArgumentError(f'Expected only one value for parameter "{name}".')
        value = value[0]
        if value.operator not in allowed_operators:
            raise ArgumentError(
                f'Allowed operators for parameter "{name}" are {", ".join(str(o) for o in allowed_operators)}.')
        if numeric:
            try:
                value = ArgumentValue([float(v) for v in value.value], value.operator)
            except ValueError:
                raise ArgumentError(f'Expected numerical arguments for parameter "{name}".')
        try:
            if isinstance(converter, dict):
                value = ArgumentValue([converter[v] for v in value.value], value.operator)
            else:
                value = ArgumentValue([converter(v) for v in value.value], value.operator)
        except Exception:
            raise ArgumentError(f'Invalid value for parameter "{name}".')
        if not is_list:
            if len(value.value) != 1:
                raise ArgumentError(f'List not allowed for parameter "{name}".')
            value = ArgumentValue(value.value[0], value.operator)
        return value

    def has_unused(self):
        return any(name not in self.used for name in self.named_arguments.keys())

    def require_all_arguments_used(self):
        def quote(s):
            return f'"{s}"'
        if self.has_unused():
            raise ArgumentError(
                f'Unkown arguments with names {", ".join(quote(v) for v in self.named_arguments.keys() if v not in self.used)}.')


if __name__ == '__main__':
    a = (parse_arguments(r'sort=default rating>=13.5 a name="a",b," asf,ds ",\'sdf\',dsf'))
    print(a)