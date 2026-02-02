import os
import shutil
import datetime
from pathlib import Path

def create_backup():
    # 1. Настройка путей и времени
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    project_root = Path.cwd()
    backup_dir = project_root / "backup" / timestamp
    text_backup_dir = project_root / "text_backup" / timestamp
    text_backup_file = text_backup_dir / f"backup_{timestamp}.txt"
    
    # Список папок, которые мы игнорируем
    ignore_dirs = {'.git', '__pycache__', 'venv', 'env', 'build', 'dist', '.idea', '.vscode', 'backup', 'text_backup'}
    
    # Создаем папки для бэкапа
    backup_dir.mkdir(parents=True, exist_ok=True)
    text_backup_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"🚀 Запуск бэкапа в папку: {timestamp}")
    
    py_files = []
    
    # 2. Поиск всех .py файлов
    for root, dirs, files in os.walk(project_root):
        # Удаляем игнорируемые папки из обхода
        dirs[:] = [d for d in dirs if d not in ignore_dirs]
        
        for file in files:
            if file.endswith('.py') and file != 'make_backup.py':
                full_path = Path(root) / file
                rel_path = full_path.relative_to(project_root)
                py_files.append((full_path, rel_path))

    # 3. Копирование файлов и сборка текста
    with open(text_backup_file, "w", encoding="utf-8") as combined_file:
        # Красивый заголовок для всего файла
        combined_file.write("="*80 + "\n")
        combined_file.write(f" NEORECORDER PROJECT SOURCE BACKUP\n")
        combined_file.write(f" Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        combined_file.write(f" Total files: {len(py_files)}\n")
        combined_file.write("="*80 + "\n\n")

        for full_path, rel_path in py_files:
            # Путь в бэкапе (сохраняем структуру папок)
            target_path = backup_dir / rel_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Копируем файл
            shutil.copy2(full_path, target_path)
            
            # Пишем в текстовый бэкап
            print(f"  + Обработка: {rel_path}")
            
            combined_file.write("\n" + "#"*80 + "\n")
            combined_file.write(f"### FILE: {rel_path}\n")
            combined_file.write("#"*80 + "\n\n")
            
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    combined_file.write(content)
            except Exception as e:
                combined_file.write(f"ERROR READING FILE: {e}")
            
            combined_file.write("\n\n")

    print(f"\n✅ Бэкап успешно завершен!")
    print(f"📂 Файлы скопированы в: {backup_dir}")
    print(f"📄 Весь текст собран в: {text_backup_file}")

if __name__ == "__main__":
    create_backup()
