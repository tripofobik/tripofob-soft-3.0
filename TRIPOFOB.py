import os
import re
import zipfile
import xml.etree.ElementTree as ET
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table
from rich.layout import Layout
from datetime import datetime
import threading
import queue
import json
import logging
from rich.box import Box, ROUNDED

console = Console()

class FileSearcher:
    def __init__(self):
        self.results = queue.Queue()
        self.total_files = 0
        self.processed_files = 0
        self.supported_extensions = {
            'Документы': ['.txt', '.doc', '.docx', '.pdf', '.rtf', '.odt'],
            'Таблицы': ['.xls', '.xlsx', '.csv', '.ods'],
            'Базы данных': ['.db', '.sql', '.sqlite', '.sqlite3'],
            'Веб-файлы': ['.html', '.xml', '.json', '.yaml', '.yml'],
            'Исходный код': ['.py', '.js', '.cpp', '.java', '.php', '.cs', '.rb', '.go'],
            'Архивы': ['.zip', '.rar', '.7z', '.tar', '.gz'],
            'Изображения': ['.jpg', '.jpeg', '.png', '.gif', '.bmp'] 
        }
        self.setup_logging()

    def setup_logging(self):
        self.logger = logging.getLogger('TRIPOFOB')
        self.logger.setLevel(logging.INFO)
        handler = logging.FileHandler('tripofob.log', encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def display_search_options(self):
        """Отображение опций поиска"""
        options_table = Table(show_header=False, box=Box.ROUNDED)
        options_table.add_row("[cyan]1.[/cyan]", "Обычный поиск")
        options_table.add_row("[cyan]2.[/cyan]", "Поиск по регулярному выражению")
        options_table.add_row("[cyan]3.[/cyan]", "Расширенный поиск с фильтрами")
        return Panel(options_table, title="Режимы поиска", border_style="cyan")

    def save_results(self, results, pattern):
        """Улучшенное сохранение результатов"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"search_results_{timestamp}.json"
        
        export_data = {
            'metadata': {
                'pattern': pattern,
                'timestamp': timestamp,
                'total_files': len(results),
                'total_matches': sum(len(r['matches']) for r in results)
            },
            'results': results
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=4)
        
        return filename

    def search_in_file(self, file_path, search_pattern):
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
                content = file.read()
                matches = re.finditer(search_pattern, content, re.IGNORECASE)
                results = []
                
                for match in matches:
                    start = max(0, match.start() - 50)
                    end = min(len(content), match.end() + 50)
                    context = content[start:end].replace('\n', ' ').strip()
                    results.append({
                        'match': match.group(),
                        'context': f"...{context}..."
                    })
                
                if results:
                    self.results.put({
                        'file': file_path,
                        'type': 'text',
                        'matches': results
                    })
        except Exception as e:
            console.print(f"[red]Ошибка чтения {file_path}: {e}")

    def search_in_xlsx_file(self, file_path, search_pattern):
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                for name in z.namelist():
                    if name.startswith('xl/worksheets/sheet'):
                        with z.open(name) as sheet:
                            tree = ET.parse(sheet)
                            root = tree.getroot()
                            results = []
                            
                            for row in root.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}row'):
                                for cell in row.iter('{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v'):
                                    if cell.text and re.search(search_pattern, cell.text, re.IGNORECASE):
                                        results.append({
                                            'match': cell.text,
                                            'context': f"Найдено в ячейке"
                                        })
                            
                            if results:
                                self.results.put({
                                    'file': file_path,
                                    'type': 'excel',
                                    'matches': results
                                })
        except Exception as e:
            console.print(f"[red]Ошибка чтения Excel {file_path}: {e}")

    def search_worker(self, files_queue, search_pattern):
        while True:
            try:
                file_path = files_queue.get_nowait()
                if file_path.endswith('.xlsx'):
                    self.search_in_xlsx_file(file_path, search_pattern)
                else:
                    self.search_in_file(file_path, search_pattern)
                self.processed_files += 1
                files_queue.task_done()
            except queue.Empty:
                break

    def search_in_directory(self, directory, search_pattern, file_types=None):
        files_queue = queue.Queue()
        
        for root, _, files in os.walk(directory):
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if file_types is None or ext in file_types:
                    file_path = os.path.join(root, file)
                    files_queue.put(file_path)
                    self.total_files += 1

        threads = []
        for _ in range(min(os.cpu_count() or 1, 4)):
            t = threading.Thread(
                target=self.search_worker,
                args=(files_queue, search_pattern)
            )
            t.start()
            threads.append(t)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})")
        ) as progress:
            task = progress.add_task(
                "[cyan]Поиск...", 
                total=self.total_files
            )
            
            while self.processed_files < self.total_files:
                progress.update(task, completed=self.processed_files)

        for t in threads:
            t.join()

        results = []
        while not self.results.empty():
            results.append(self.results.get())
        
        return results

    def search_with_regex(self, content, pattern):
        try:
            regex = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
            return regex.finditer(content)
        except re.error as e:
            self.logger.error(f"Ошибка в регулярном выражении: {e}")
            return []

def display_menu():
    console.clear()
    banner = """
    [bold blue]
    ████████╗██████╗░██╗██████╗░░█████╗░███████╗░█████╗░██████╗░ 3.0
    ╚══██╔══╝██╔══██╗██║██╔══██╗██╔══██╗██╔════╝██╔══██╗██╔══██╗
    ░░░██║░░░██████╔╝██║██████╔╝██║░░██║█████╗░░██║░░██║██████╦╝
    ░░░██║░░░██╔══██╗██║██╔═══╝░██║░░██║██╔══╝░░██║░░██║██╔══██╗
    ░░░██║░░░██║░░██║██║██║░░░░░╚█████╔╝██║░░░░░╚█████╔╝██████╦╝
    ░░░╚═╝░░░╚═╝░░╚═╝╚═╝╚═╝░░░░░░╚════╝░╚═╝░░░░░░╚════╝░╚═════╝░[/bold blue]
    """
    welcome_text = "\n[cyan]Добро пожаловать в улучшенную систему поиска файлов![/cyan]"
    console.print(Panel(banner + welcome_text, 
                       title="♦ TRIPOFOB 3.0 ♦", 
                       style="bold blue", 
                       border_style="blue",
                       padding=(1, 2)))

def display_file_types_menu(searcher):
    types_table = Table(show_header=True, 
                       box=ROUNDED,
                       title="[bold cyan]Доступные типы файлов[/bold cyan]",
                       title_style="cyan",
                       header_style="bold magenta")
    types_table.add_column("№", style="cyan", justify="center")
    types_table.add_column("Категория", style="green")
    types_table.add_column("Расширения", style="yellow")
    
    for i, (category, extensions) in enumerate(searcher.supported_extensions.items(), 1):
        types_table.add_row(
            str(i),
            category,
            ", ".join(extensions)
        )
    types_table.add_row("0", "[bold cyan]Все типы[/bold cyan]", "[italic]* все доступные расширения *[/italic]")
    
    console.print(Panel(types_table, border_style="cyan", padding=(1, 2)))

def display_search_progress(progress, task):
    """Улучшенное отображение прогресса поиска"""
    return Panel(
        progress,
        title="[bold cyan]Прогресс поиска[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    )

def display_results(results, pattern):
    if not results:
        console.print(Panel("\n[yellow]Результаты не найдены[/yellow]", 
                          title="⚠ Статус поиска ⚠", 
                          border_style="yellow",
                          padding=(1, 2)))
        return

    stats_table = Table(show_header=False, box=ROUNDED)
    stats_table.add_row("[cyan]📁 Всего найдено файлов:[/cyan]", f"[green]{len(results)}[/green]")
    total_matches = sum(len(r['matches']) for r in results)
    stats_table.add_row("[cyan]🔍 Всего совпадений:[/cyan]", f"[green]{total_matches}[/green]")
    
    console.print(Panel(stats_table, 
                       title="[bold cyan]📊 Статистика поиска[/bold cyan]", 
                       border_style="cyan",
                       padding=(1, 2)))

    table = Table(title=f"[bold cyan]🔎 Результаты поиска для: [yellow]{pattern}[/yellow][/bold cyan]", 
                 box=ROUNDED,
                 header_style="bold magenta",
                 show_lines=True)
    
    table.add_column("№", style="cyan", justify="right")
    table.add_column("📄 Файл", style="green", no_wrap=True)
    table.add_column("💡 Совпадение", style="yellow")
    table.add_column("📝 Контекст", style="white", max_width=60)

    for idx, result in enumerate(results, 1):
        file_name = os.path.basename(result['file'])
        for match in result['matches']:
            table.add_row(
                str(idx),
                Text(file_name, style="bold green"),
                Text(match['match'], style="bold yellow"),
                match['context']
            )

    console.print(Panel(table, border_style="cyan", padding=(1, 2)))

def main():
    searcher = FileSearcher()
    
    while True:
        display_menu()
        
        console.print(Panel(
            "[cyan]Выберите режим поиска:[/cyan]\n\n" +
            "1. 🔍 Обычный поиск\n" +
            "2. ⚡ Поиск по регулярному выражению",
            title="[bold cyan]Режимы поиска[/bold cyan]",
            border_style="cyan",
            padding=(1, 2)
        ))

        search_mode = Prompt.ask(
            "\n[yellow]Ваш выбор[/yellow]",
            choices=["1", "2"],
            default="1"
        )

        display_file_types_menu(searcher)
        
        choice = Prompt.ask("\nВыберите типы файлов (введите номера через запятую или 0 для всех)", default="0")
        
        selected_extensions = []
        if choice != "0":
            categories = [int(x.strip()) for x in choice.split(",")]
            for cat_num in categories:
                if 1 <= cat_num <= len(searcher.supported_extensions):
                    category = list(searcher.supported_extensions.keys())[cat_num-1]
                    selected_extensions.extend(searcher.supported_extensions[category])
        
        pattern = Prompt.ask("\n[cyan]Введите данные для поиска[/cyan]")
        if not pattern:
            continue

        directory = Prompt.ask("\n[cyan]Введите путь для поиска[/cyan]", 
                             default=os.path.dirname(os.path.abspath(__file__)))

        if search_mode == "1":
            results = searcher.search_in_directory(
                directory, 
                pattern,
                selected_extensions if selected_extensions else None
            )
        else:
            results = searcher.search_with_regex(pattern, pattern)

        display_results(results, pattern)

        if results:
            if Prompt.ask("\nСохранить результаты в файл? (y/n)", default="n").lower() == 'y':
                filename = searcher.save_results(results, pattern)
                console.print(f"\n[green]Результаты сохранены в: {filename}[/green]")

        if Prompt.ask("\nПродолжить поиск? (y/n)", default="y").lower() != 'y':
            break

    console.print("\n[blue]Спасибо за использование TRIPOFOB 3.0![/blue]")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Программа остановлена пользователем[/red]")
    except Exception as e:
        console.print(f"\n[red]Произошла ошибка: {e}[/red]")
        logging.error(f"Критическая ошибка: {e}", exc_info=True)