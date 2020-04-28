import json
from pathlib import Path
from typing import Any, Dict, FrozenSet, Optional


class StubFile:

    def __init__(self, path: Path) -> None:
        self.path = path
        self._content = dict()  # type: Dict[str, Dict[str, Any]]

    def load(self) -> None:
        with self.path.open(encoding='utf8') as stream:
            self._content = json.load(stream)

    def dump(self) -> None:
        with self.path.open(mode='w', encoding='utf8') as stream:
            self._content = json.dump(stream)

    def add(self, func: str, contract: str, value: str) -> None:
        if contract != 'raises':
            raise ValueError('only raises contract is supported yet')

        contracts = self._content.setdefault(func, dict())
        values = contracts.setdefault(contract, [])
        if value not in values:
            values.append(value)

    def get(self, func: str, contract: str) -> FrozenSet[str, ...]:
        values = self._content.get(func, {}).get(contract, [])
        return frozenset(values)


class StubsManager:
    root = Path(__file__).parent / 'stubs'

    def __init__(self):
        self._modules = dict()

    def read(self, path: Path) -> StubFile:
        if path.suffix != '.json':
            raise ValueError('invalid stub file extension: *{}'.format(path.suffix))
        module_name = self._get_module_name(path=path)
        if module_name not in self._modules:
            stub = StubFile(path=path)
            stub.load()
            self._modules[module_name] = stub
        return self._modules[module_name]

    def _get_module_name(self, path: Path) -> str:
        # built-in stubs
        if path.parent == self.root:
            return path.stem
        # name is a full path to a module
        if '.' in path.stem:
            return path.stem
        # walk up by the tree as pytest does
        if not (path.parent / '__init__.py').exists():
            return path.stem
        for parent in path.parents:
            if not (parent / '__init__.py').exists():
                parts = path.relative_to(parent).with_suffix('').parts
                return '.'.join(parts)
        return path.stem

    def get(self, module_name: str) -> Optional[StubFile]:
        stub = self._modules.get(module_name)
        if stub is not None:
            return stub
        path = self.root / (module_name + '.json')
        if path.exists():
            self.read(path)
        return None

    def create(self, path: Path) -> StubFile:
        if path.suffix == '.py':
            path = path.with_suffix('.json')
        module_name = self._get_module_name(path=path)
        if module_name not in self._modules:
            stub = StubFile(path=path)
            self._modules[module_name] = stub
        return self._modules[module_name]


def generate_stub(path: Path) -> Path:
    from ._extractors import get_exceptions
    from ._func import Func

    if path.suffix != '.py':
        raise ValueError('invalid Python file extension: *{}'.format(path.suffix))

    manager = StubsManager()
    stub = manager.create(path=path)
    funcs = Func.from_path(path=path)
    for func in funcs:
        if func.name is None:
            continue
        for token in get_exceptions(body=func.body):
            value = token.value
            if isinstance(value, type):
                value = value.__name__
            stub.add(func=func.name, contract='raises', value=str(value))
    stub.dump()
    return stub.path
