import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
import tkinter as tk
from tkinter import ttk, messagebox
from concurrent.futures import ThreadPoolExecutor
import multiprocessing
import platform


# ================== АВТОПУТИ ==================
BASE_DIR = Path(__file__).resolve().parent

SOURCE_DIR = BASE_DIR
TARGET_DIR = BASE_DIR / "sorted"

IMAGE_EXT = {".jpg", ".jpeg", ".tiff", ".heic"}
VIDEO_EXT = {".mp4", ".mov", ".avi", ".mkv"}


# ================== ПОТОКИ ==================
def is_ssd(path):
    if platform.system() != "Windows":
        return True
    return True  # упрощённо


def get_optimal_threads(source_dir):
    cores = multiprocessing.cpu_count()
    return max(2, min(8, cores * 2))


THREADS = get_optimal_threads(str(SOURCE_DIR))


# ================== EXIF ==================
def get_exif_date(path):
    try:
        img = Image.open(path)
        exif = img._getexif()

        if exif:
            data = {
                ExifTags.TAGS.get(k): v
                for k, v in exif.items()
                if k in ExifTags.TAGS
            }

            date_str = data.get("DateTimeOriginal") or data.get("DateTime")

            if date_str:
                return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")

    except Exception:
        pass

    return datetime.fromtimestamp(os.path.getmtime(path))


# ================== ФАЙЛЫ ==================
def safe_move(src, dst):
    os.makedirs(dst, exist_ok=True)
    shutil.move(src, os.path.join(dst, os.path.basename(src)))


def process_file(file):
    try:
        dt = get_exif_date(file)
        return file, dt.strftime("%Y"), dt.strftime("%y.%m.%d")
    except Exception:
        return file, None, None


# ================== GUI ==================
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Фото сортировщик (recursive + EXIF)")

        self.label = tk.Label(root, text=f"Готов. Потоков: {THREADS}")
        self.label.pack(pady=10)

        self.progress = ttk.Progressbar(root, length=400)
        self.progress.pack(pady=10)

        self.btn = tk.Button(root, text="Старт", command=self.run)
        self.btn.pack(pady=10)

    def run(self):
        try:
            files = []

            # ===== РЕКУРСИВНЫЙ ПОИСК =====
            for f in SOURCE_DIR.rglob("*"):
                if not f.is_file():
                    continue

                # не трогаем результат
                if TARGET_DIR in f.parents:
                    continue

                # не трогаем сам скрипт
                if str(f.resolve()) == str(Path(__file__).resolve()):
                    continue

                if f.suffix.lower() in IMAGE_EXT or f.suffix.lower() in VIDEO_EXT:
                    files.append(str(f))

            total = len(files)

            if total == 0:
                messagebox.showinfo("Инфо", "Файлы не найдены")
                return

            results = []

            # ===== EXIF ПАРАЛЛЕЛЬНО =====
            with ThreadPoolExecutor(max_workers=THREADS) as executor:
                for i, res in enumerate(executor.map(process_file, files)):
                    results.append(res)

                    percent = int((i + 1) / total * 100)
                    self.progress["value"] = percent
                    self.label.config(text=f"Чтение: {os.path.basename(res[0])}")
                    self.root.update_idletasks()

            # ===== ГРУППИРОВКА (фото + видео вместе) =====
            grouped = {}

            for file, year, date_key in results:
                if year is None:
                    continue

                grouped.setdefault((year, date_key), []).append(file)

            # ===== ПЕРЕНОС =====
            all_items = sum(len(v) for v in grouped.values())
            done = 0

            for (year, date_key), items in grouped.items():
                year_folder = TARGET_DIR / year

                if len(items) > 10:
                    folder = year_folder / date_key
                else:
                    folder = year_folder / "misc_small"

                for file in items:
                    safe_move(file, str(folder))

                    done += 1
                    percent = int(done / all_items * 100)
                    self.progress["value"] = percent
                    self.label.config(text=f"Перенос: {os.path.basename(file)}")
                    self.root.update_idletasks()

            self.label.config(text="Готово")
            messagebox.showinfo("Успех", "Сортировка завершена")

        except Exception:
            messagebox.showerror("Ошибка", traceback.format_exc())


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()