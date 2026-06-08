import pandas as pd

# Список названий классов, соответствующих меткам от 0 до 4
CLASS_NAMES = [
    "Не инцидент",
    "Низкая тяжесть",
    "Средняя тяжесть",
    "Высокая тяжесть",
    "Критическая / ЧС",
]

def format_input_text(row: pd.Series) -> str:
    """
    Преобразует строку (row) из Excel в единый текст, 
    который понимает модель.
    """
    # Извлекаем значения и удаляем лишние пробелы
    group = str(row.get("Группа тем", "")).strip()
    theme = str(row.get("Тема", "")).strip()
    text = str(row.get("Текст инцидента", "")).strip()
    
    # Защита от пустых значений pandas (NaN)
    if group.lower() == 'nan': group = ""
    if theme.lower() == 'nan': theme = ""
    if text.lower() == 'nan': text = ""
    
    # Собираем текст в единую строку
    parts = []
    if group:
        parts.append(f"Группа: {group}")
    if theme:
        parts.append(f"Тема: {theme}")
    if text:
        parts.append(f"Текст: {text}")
        
    return " | ".join(parts)
