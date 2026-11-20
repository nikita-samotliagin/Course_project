import hashlib
import json
import platform
import sys
import sysconfig
import zipfile
from pathlib import Path

def main():
    root=Path(__file__).resolve().parent
    if sys.prefix==sys.base_prefix:
        raise SystemExit('Запустите этот файл Python из виртуального окружения .venv.')
    if sys.version_info[:2]!=(3,12) or sys.platform!='win32' or platform.machine().lower() not in ('amd64','x86_64'):
        raise SystemExit('Офлайн-набор предназначен для Python 3.12 на Windows x64.')
    wheels=root/'vendor/wheels'
    hashes=json.loads((wheels/'hashes.json').read_text(encoding='utf-8'))
    target=Path(sysconfig.get_path('purelib')).resolve()
    if not target.is_relative_to(Path(sys.prefix).resolve()):
        raise SystemExit('Некорректный каталог окружения.')
    for name,expected in hashes.items():
        path=wheels/name
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:
            raise SystemExit('Повреждён пакет: '+name)
        with zipfile.ZipFile(path) as archive:
            for member in archive.infolist():
                destination=(target/member.filename).resolve()
                if not destination.is_relative_to(target):
                    raise SystemExit('Недопустимый путь в пакете.')
            archive.extractall(target)
        print('Установлен '+name)
    print('Офлайн-установка завершена.')

if __name__=='__main__':main()
