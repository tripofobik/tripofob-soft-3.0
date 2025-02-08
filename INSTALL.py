import subprocess
import sys
import os

def check_system_requirements():
    """Проверка системных требований"""
    print("Проверка системных требований...")
    
    python_version = sys.version_info
    if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 7):
        print("Ошибка: Требуется Python 3.7 или выше")
        return False
    
    try:
        import psutil
        memory = psutil.virtual_memory()
        if memory.available < 1 * 1024 * 1024 * 1024:  # 1 GB
            print("Предупреждение: Рекомендуется минимум 1 GB свободной памяти")
    except ImportError:
        print("Предупреждение: Невозможно проверить доступную память")
    
    return True

def install_requirements():
    if not check_system_requirements():
        input("\nНажмите Enter для выхода...")
        return

    requirements_file = os.path.join(os.path.dirname(__file__), 'requirements.txt')

    console_message = """
    ████████╗██████╗░██╗██████╗░░█████╗░███████╗░█████╗░██████╗░
    ╚══██╔══╝██╔══██╗██║██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗
    ░░░██║░░░██████╔╝██║██████╔╝██║░░██║█████╗░░██║░░██║██████╦╝
    ░░░██║░░░██╔══██╗██║██╔═══╝░██║░░██║██╔══╝░░██║░░██║██╔══██╗
    ░░░██║░░░██║░░██║██║██║░░░░░╚█████╔╝██║░░░░░╚█████╔╝██████╦╝
    ░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═╝░░░░░░╚════╝░╚═╝░░░░░░╚════╝░╚═════╝░
    
    Установка необходимых зависимостей...
    """
    print(console_message)

    try:
        subprocess.check_call([sys.executable, '-m', 'pip', '--version'])
    except subprocess.CalledProcessError:
        print("Ошибка: pip не установлен. Пожалуйста, установите pip сначала.")
        return

    try:
        print("Установка зависимостей из requirements.txt...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-r', requirements_file])
        print("Все зависимости успешно установлены!")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при установке зависимостей: {e}")
        return

    input("\nНажмите Enter для выхода...")

if __name__ == "__main__":
    install_requirements()