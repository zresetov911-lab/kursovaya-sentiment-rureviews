# Курсовая работа: анализ тональности отзывов клиентов

**Студент:** Решетов Евгений Владиславович, гр. 25ИСТ(м)ИИП  
**Руководитель:** канд. техн. наук, доцент С. Т. Дусакаева  
**Дисциплина:** Машинное обучение  
**Тема:** Применение методов машинного обучения для автоматической классификации и анализа тональности отзывов клиентов  
**Год:** 2026

## Датасет

Открытый корпус **RuReviews** — русскоязычные отзывы о товарах категории «женская одежда и аксессуары», 3 класса тональности:

- https://github.com/sismetanin/rureviews
- локально: `data/ru_reviews.csv`

## Запуск эксперимента

```powershell
pip install -r requirements.txt
python src\run_experiment.py
python scripts\rebuild_deliverables.py
```

## Результаты

Лучшая модель на отложенном тесте: **LogisticRegression**  
Accuracy ≈ **0,749**, macro-F1 ≈ **0,750**, ROC-AUC ≈ **0,898**.

Сравнивались: Dummy, MultinomialNB, LogisticRegression, LinearSVC, RandomForest, MLP.

## Отчётные материалы

| Файл | Назначение |
|------|------------|
| `report/Kursovaya_Reshetov_Sentiment_Analysis.docx` | Отчёт (межстрочный интервал 1, одно приложение А с кодом) |
| `presentation/Prezentatsia_Reshetov_Sentiment_Analysis.pptx` | Презентация к защите |
| `research.ipynb` | Jupyter-ноутбук с сохранёнными результатами |
| `requirements.txt` | Окружение |
| `figures/` | Рисунки для отчёта |
| `results/` | Метрики и таблицы |
