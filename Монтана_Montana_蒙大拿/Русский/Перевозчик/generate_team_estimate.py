#!/usr/bin/env python3
"""
Генератор PDF: Детальная оценка найма команды для Montana Protocol + Перевозчик
"""

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os

# Путь к PDF
OUTPUT_PATH = os.path.dirname(os.path.abspath(__file__))
PDF_FILE = os.path.join(OUTPUT_PATH, "ОЦЕНКА_НАЙМА_КОМАНДЫ.pdf")

# Регистрация шрифта с поддержкой кириллицы
try:
    pdfmetrics.registerFont(TTFont('DejaVu', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
    FONT_NAME = 'DejaVu'
except:
    try:
        pdfmetrics.registerFont(TTFont('DejaVu', '/Library/Fonts/Arial Unicode.ttf'))
        FONT_NAME = 'DejaVu'
    except:
        FONT_NAME = 'Helvetica'

def create_pdf():
    doc = SimpleDocTemplate(
        PDF_FILE,
        pagesize=A4,
        rightMargin=15*mm,
        leftMargin=15*mm,
        topMargin=15*mm,
        bottomMargin=15*mm
    )

    elements = []
    styles = getSampleStyleSheet()

    # Стили
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Title'],
        fontName=FONT_NAME,
        fontSize=18,
        spaceAfter=10
    )

    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontName=FONT_NAME,
        fontSize=14,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#1a5f7a')
    )

    normal_style = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10,
        spaceAfter=6
    )

    # Заголовок
    elements.append(Paragraph("MONTANA PROTOCOL + ПЕРЕВОЗЧИК", title_style))
    elements.append(Paragraph("Детальная оценка найма команды разработки", normal_style))
    elements.append(Paragraph("Дата: Январь 2026", normal_style))
    elements.append(Spacer(1, 10*mm))

    # Статус проекта
    elements.append(Paragraph("1. ТЕКУЩИЙ СТАТУС ПРОЕКТА", heading_style))

    status_data = [
        ['Компонент', 'Готовность', 'Оставшаяся работа'],
        ['Montana Core (криптография, бот, сеть)', '95%', 'Поддержка, баги'],
        ['Перевозчик (iOS + backend)', '40%', 'Frontend, интеграция'],
        ['iOS приложения (4 app)', '50%', 'Swift код, UI, публикация'],
        ['Сайт Montana', '40%', 'React frontend, деплой'],
    ]

    status_table = Table(status_data, colWidths=[70*mm, 30*mm, 70*mm])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a5f7a')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    elements.append(status_table)
    elements.append(Spacer(1, 8*mm))

    # Необходимые роли
    elements.append(Paragraph("2. НЕОБХОДИМЫЕ РОЛИ И ЗАРПЛАТЫ", heading_style))

    roles_data = [
        ['Роль', 'Уровень', 'США/EU', 'СНГ (РФ/KZ)', 'Задачи'],
        ['iOS Developer', 'Senior', '$6,000-12,000', '$3,000-5,000', 'Перевозчик, Wallet'],
        ['Python Backend', 'Senior', '$5,000-10,000', '$2,500-4,500', 'API, интеграции'],
        ['React Frontend', 'Middle+', '$4,000-8,000', '$2,000-3,500', 'Сайт, MiniApp'],
        ['DevOps', 'Middle', '$4,000-7,000', '$2,000-3,500', '5 узлов, CI/CD'],
        ['QA Engineer', 'Middle', '$3,000-5,000', '$1,500-2,500', 'Тестирование'],
    ]

    roles_table = Table(roles_data, colWidths=[35*mm, 25*mm, 35*mm, 35*mm, 40*mm])
    roles_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2d6a4f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (2, 0), (3, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f5f5f5')]),
    ]))
    elements.append(roles_table)
    elements.append(Spacer(1, 10*mm))

    # ВАРИАНТ A
    elements.append(Paragraph("3. ВАРИАНТ A: КОМАНДА В СНГ (РОССИЯ/КАЗАХСТАН)", heading_style))
    elements.append(Paragraph("Полная команда для быстрого завершения проекта", normal_style))

    variant_a_data = [
        ['Роль', 'Кол-во', 'Ставка/мес', 'Итого'],
        ['iOS Senior', '1', '$4,000', '$4,000'],
        ['Python Senior', '1', '$3,500', '$3,500'],
        ['React Middle', '1', '$2,500', '$2,500'],
        ['DevOps (part-time)', '0.5', '$2,500', '$1,250'],
        ['QA (part-time)', '0.5', '$2,000', '$1,000'],
        ['', '', 'Подитог:', '$12,250'],
        ['', '', 'Накладные (+20%):', '$2,450'],
        ['', '', 'ИТОГО:', '$14,700/мес'],
    ]

    variant_a_table = Table(variant_a_data, colWidths=[50*mm, 25*mm, 45*mm, 45*mm])
    variant_a_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#d4a373')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#faedcd')),
        ('FONTNAME', (2, -1), (-1, -1), FONT_NAME),
        ('TEXTCOLOR', (3, -1), (3, -1), colors.HexColor('#bc4749')),
    ]))
    elements.append(variant_a_table)
    elements.append(Paragraph("Срок: 1.5-2 месяца | Общая стоимость: $22,000-29,000", normal_style))
    elements.append(Spacer(1, 8*mm))

    # ВАРИАНТ B
    elements.append(Paragraph("4. ВАРИАНТ B: УДАЛЁННАЯ КОМАНДА (СМЕШАННАЯ)", heading_style))
    elements.append(Paragraph("Оптимизация по соотношению цена/качество", normal_style))

    variant_b_data = [
        ['Роль', 'Локация', 'Ставка/мес', 'Итого'],
        ['iOS Senior', 'Сербия/Польша', '$5,500', '$5,500'],
        ['Python Senior', 'Украина/Грузия', '$4,000', '$4,000'],
        ['React Middle', 'Россия', '$2,500', '$2,500'],
        ['DevOps', 'Казахстан', '$2,500', '$2,500'],
        ['', '', 'ИТОГО:', '$14,500/мес'],
    ]

    variant_b_table = Table(variant_b_data, colWidths=[45*mm, 50*mm, 35*mm, 35*mm])
    variant_b_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#457b9d')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#a8dadc')),
        ('TEXTCOLOR', (3, -1), (3, -1), colors.HexColor('#1d3557')),
    ]))
    elements.append(variant_b_table)
    elements.append(Paragraph("Срок: 1.5-2 месяца | Общая стоимость: $21,000-29,000", normal_style))
    elements.append(Spacer(1, 8*mm))

    # ВАРИАНТ C
    elements.append(Paragraph("5. ВАРИАНТ C: ЗАПАДНЫЙ РЫНОК (США/EU)", heading_style))
    elements.append(Paragraph("Максимальное качество, максимальная цена", normal_style))

    variant_c_data = [
        ['Роль', 'Ставка/мес', 'Итого'],
        ['iOS Senior', '$12,000', '$12,000'],
        ['Python Senior', '$10,000', '$10,000'],
        ['React Middle', '$7,000', '$7,000'],
        ['DevOps', '$6,000', '$6,000'],
        ['', 'ИТОГО:', '$35,000/мес'],
    ]

    variant_c_table = Table(variant_c_data, colWidths=[60*mm, 50*mm, 50*mm])
    variant_c_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9d4edd')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#e0aaff')),
        ('TEXTCOLOR', (2, -1), (2, -1), colors.HexColor('#7b2cbf')),
    ]))
    elements.append(variant_c_table)
    elements.append(Paragraph("Срок: 1-1.5 месяца | Общая стоимость: $35,000-52,000", normal_style))
    elements.append(Spacer(1, 8*mm))

    # ВАРИАНТ D - Минимальный
    elements.append(Paragraph("6. ВАРИАНТ D: МИНИМАЛЬНАЯ КОМАНДА (MVP)", heading_style))
    elements.append(Paragraph("Только Перевозчик + MontanaWallet", normal_style))

    variant_d_data = [
        ['Роль', 'Кол-во', 'Ставка (СНГ)', 'Срок'],
        ['iOS Full-stack', '1', '$4,500/мес', '2 мес'],
        ['Python/DevOps', '1', '$3,500/мес', '2 мес'],
        ['', '', 'ИТОГО:', '$8,000/мес'],
    ]

    variant_d_table = Table(variant_d_data, colWidths=[50*mm, 30*mm, 40*mm, 40*mm])
    variant_d_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#40916c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#b7e4c7')),
        ('TEXTCOLOR', (2, -1), (2, -1), colors.HexColor('#1b4332')),
    ]))
    elements.append(variant_d_table)
    elements.append(Paragraph("Срок: 2 месяца | Общая стоимость: $16,000", normal_style))
    elements.append(Spacer(1, 8*mm))

    # ВАРИАНТ E - Solo + AI
    elements.append(Paragraph("7. ВАРИАНТ E: SOLO + AI TOOLS (РЕАЛЬНЫЕ РАСХОДЫ)", heading_style))
    elements.append(Paragraph("Актуальная стоимость инфраструктуры и AI-инструментов", normal_style))

    variant_e_data = [
        ['Ресурс', 'Стоимость/мес', 'Примечание'],
        ['Серверы (5 узлов)', '$250', '5 × $50 (Timeweb, AMS, etc)'],
        ['Claude Pro', '$200', 'Anthropic subscription'],
        ['ChatGPT Plus', '$20', 'OpenAI subscription'],
        ['Cursor Pro', '$200', 'AI-powered IDE'],
        ['API запросы (доп.)', '$200-400', 'Anthropic/OpenAI API'],
        ['Apple Developer', '$8', '$99/год'],
        ['Домены, SSL, misc', '$50-100', 'Прочие расходы'],
        ['', 'ИТОГО:', '$1,000-1,500/мес'],
    ]

    variant_e_table = Table(variant_e_data, colWidths=[55*mm, 45*mm, 60*mm])
    variant_e_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0077b6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#caf0f8')),
        ('TEXTCOLOR', (1, -1), (1, -1), colors.HexColor('#03045e')),
    ]))
    elements.append(variant_e_table)
    elements.append(Paragraph("Срок: 3-4 месяца | Общая стоимость: $3,000-6,000", normal_style))
    elements.append(Spacer(1, 10*mm))

    # ИТОГОВОЕ СРАВНЕНИЕ
    elements.append(Paragraph("8. ИТОГОВОЕ СРАВНЕНИЕ ВАРИАНТОВ", heading_style))

    comparison_data = [
        ['Вариант', 'Команда', 'Цена/мес', 'Срок', 'Общая стоимость'],
        ['A: СНГ полная', '4 чел', '$14,700', '1.5-2 мес', '$22,000-29,000'],
        ['B: Смешанная', '4 чел', '$14,500', '1.5-2 мес', '$21,000-29,000'],
        ['C: США/EU', '4 чел', '$35,000', '1-1.5 мес', '$35,000-52,000'],
        ['D: MVP минимум', '2 чел', '$8,000', '2 мес', '$16,000'],
        ['E: Solo + AI', '1 чел + AI', '$1,000-1,500', '3-4 мес', '$3,000-6,000'],
    ]

    comparison_table = Table(comparison_data, colWidths=[40*mm, 28*mm, 32*mm, 30*mm, 40*mm])
    comparison_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#212529')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, -1), FONT_NAME),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#d8f3dc')),
        ('TEXTCOLOR', (2, -1), (2, -1), colors.HexColor('#2d6a4f')),
    ]))
    elements.append(comparison_table)
    elements.append(Spacer(1, 10*mm))

    # Рекомендация
    elements.append(Paragraph("9. РЕКОМЕНДАЦИЯ", heading_style))

    rec_style = ParagraphStyle(
        'Recommendation',
        parent=normal_style,
        backColor=colors.HexColor('#fff3cd'),
        borderPadding=8,
        fontSize=9
    )

    elements.append(Paragraph(
        "<b>ОПТИМАЛЬНЫЙ ВЫБОР: Вариант D (MVP) или Вариант E (Solo + AI)</b><br/><br/>"
        "Montana Core готов на 95%. Основная работа - iOS приложения (Перевозчик + Wallet).<br/><br/>"
        "<b>Вариант D:</b> 1 iOS-разработчик на контракт ($4,500/мес, 2 месяца) = $9,000-10,000<br/>"
        "Backend и сайт можно доделать самостоятельно с AI tools.<br/><br/>"
        "<b>Вариант E:</b> Solo + AI инфраструктура: $1,000-1,500/мес (3-4 мес) = $3,000-6,000<br/>"
        "Серверы $250 + Claude $200 + GPT $20 + Cursor $200 + API ~$300 + misc $100<br/><br/>"
        "<b>Экономия vs полная команда:</b> $16,000-46,000",
        rec_style
    ))

    elements.append(Spacer(1, 8*mm))

    # Футер
    footer_style = ParagraphStyle(
        'Footer',
        parent=normal_style,
        fontSize=8,
        textColor=colors.grey
    )
    elements.append(Paragraph(
        "Montana Protocol (Ɉ) | Time is the only real currency | Автор: Alejandro Montana",
        footer_style
    ))

    # Генерация PDF
    doc.build(elements)
    print(f"PDF создан: {PDF_FILE}")
    return PDF_FILE

if __name__ == "__main__":
    create_pdf()
