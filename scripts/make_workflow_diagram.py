#!/usr/bin/env python3
"""Generate the Getting Started example-workflow diagrams, one SVG per language.

Knut's diagram (2026-08-12) is authored in yEd and handed over as a PDF —
the PDF, not yEd's own SVG export, because the PDF carries every label as a
real text string while the SVG export outlines most of them. This script:

  1. converts ``assets/help/example-workflow.pdf`` to SVG with the text kept
     as text (PyMuPDF — a dev-time dependency only, nothing here ships);
  2. verifies every label it knows against the PDF, **by position in the
     document**, so a re-exported PDF with changed wording fails loudly here
     instead of silently shipping a half-translated picture;
  3. replaces the labels for each of the twelve catalogue languages —
     folder names (runs/, run1/, verifications/, reports/), dates and the
     example project/description names stay in English on purpose: they are
     the literal names on the user's disk;
  4. repairs the one defect the PDF carries (the legend title is truncated
     to "Lege…" in the export — every language, English included, gets the
     full word);
  5. writes ``assets/help/workflow/<code>.svg`` for en + the twelve
     languages, cropped to the drawing.

Label translations: the box/tab names come from the app's own i18n
catalogues at generation time (single source, no drift); the diagram-only
phrases were translated in one reviewed batch (Opus draft, human-checked —
Norwegian "sti" not "bane", Russian paucal "1944 патча").

Run:  .venv/bin/python scripts/make_workflow_diagram.py
"""
from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

PDF = ROOT / "assets" / "help" / "example-workflow.pdf"
OUT_DIR = ROOT / "assets" / "help" / "workflow"
LANGS = ["de", "es", "fr", "it", "ja", "nl", "no", "pl", "pt", "ru", "sv",
         "zh_CN"]

# ---------------------------------------------------------------------------
# The diagram-only phrases (not in the app catalogues). One reviewed batch.
# ---------------------------------------------------------------------------
T = {
 "title": {"de": ["Beispiel-Workflow und Bezug zu den Ordner-Speicherorten"], "es": ["Flujo de trabajo de ejemplo y su relación con las carpetas"], "fr": ["Exemple de flux de travail et lien avec les dossiers"], "it": ["Flusso di lavoro di esempio e relazione con le cartelle"], "ja": ["ワークフロー例とフォルダ構成の関係"], "nl": ["Voorbeeldworkflow en relatie tot de maplocaties"], "no": ["Eksempel på arbeidsflyt og forholdet til mappene"], "pl": ["Przykładowy przebieg pracy i powiązanie z folderami"], "pt": ["Fluxo de trabalho de exemplo e relação com as pastas"], "ru": ["Пример рабочего процесса и связь с папками"], "sv": ["Exempel på arbetsflöde och koppling till mapparna"], "zh_CN": ["示例工作流程与文件夹位置的关系"]},
 "path_note": {"de": ["Pfad in Bezug auf", "den ChromIQ-", "Standardordner."], "es": ["Ruta relativa a la", "carpeta predeterminada", "de ChromIQ."], "fr": ["Chemin par rapport au", "dossier par défaut", "de ChromIQ."], "it": ["Percorso rispetto alla", "cartella predefinita", "di ChromIQ."], "ja": ["ChromIQ の既定フォルダ", "を基準とした", "パス。"], "nl": ["Pad ten opzichte van", "de standaardmap", "van ChromIQ."], "no": ["Sti i forhold til", "standardmappen", "til ChromIQ."], "pl": ["Ścieżka względem", "domyślnego folderu", "ChromIQ."], "pt": ["Caminho em relação à", "pasta predefinida", "do ChromIQ."], "ru": ["Путь относительно", "папки ChromIQ по", "умолчанию."], "sv": ["Sökväg i förhållande", "till ChromIQs", "standardmapp."], "zh_CN": ["相对于 ChromIQ", "默认文件夹", "的路径。"]},
 "legend": {"de": ["Legende:"], "es": ["Leyenda:"], "fr": ["Légende :"], "it": ["Legenda:"], "ja": ["凡例:"], "nl": ["Legenda:"], "no": ["Forklaring:"], "pl": ["Legenda:"], "pt": ["Legenda:"], "ru": ["Легенда:"], "sv": ["Förklaring:"], "zh_CN": ["图例:"]},
 "folder_path_sample": {"de": ["ordner_pfad/"], "es": ["ruta_carpeta/"], "fr": ["chemin_dossier/"], "it": ["path_cartella/"], "ja": ["フォルダ_パス/"], "nl": ["map_pad/"], "no": ["mappe_sti/"], "pl": ["ścieżka_folderu/"], "pt": ["caminho_pasta/"], "ru": ["путь_папки/"], "sv": ["mapp_sökväg/"], "zh_CN": ["文件夹_路径/"]},
 "action": {"de": ["Aktion"], "es": ["Acción"], "fr": ["Action"], "it": ["Azione"], "ja": ["アクション"], "nl": ["Actie"], "no": ["Handling"], "pl": ["Działanie"], "pt": ["Ação"], "ru": ["Действие"], "sv": ["Åtgärd"], "zh_CN": ["操作"]},
 "normal_workflow": {"de": ["Normaler", "Workflow"], "es": ["Flujo normal", "de trabajo"], "fr": ["Flux normal", "de travail"], "it": ["Flusso", "normale"], "ja": ["通常の", "ワークフロー"], "nl": ["Normale", "workflow"], "no": ["Normal", "arbeidsflyt"], "pl": ["Normalny", "przebieg"], "pt": ["Fluxo normal", "de trabalho"], "ru": ["Обычный", "процесс"], "sv": ["Normalt", "arbetsflöde"], "zh_CN": ["正常", "工作流程"]},
 "run_description": {"de": ["Beschreibung Lauf {n}:"], "es": ["Descripción ejec. {n}:"], "fr": ["Description exéc. {n} :"], "it": ["Descrizione esec. {n}:"], "ja": ["実行 {n} の説明:"], "nl": ["Beschrijving run {n}:"], "no": ["Beskrivelse kjøring {n}:"], "pl": ["Opis przebiegu {n}:"], "pt": ["Descrição da exec. {n}:"], "ru": ["Описание запуска {n}:"], "sv": ["Beskrivning körning {n}:"], "zh_CN": ["运行 {n} 说明:"]},
 "dated_check": {"de": ["Datierte Prüfung"], "es": ["Control fechado"], "fr": ["Contrôle daté"], "it": ["Verifica datata"], "ja": ["日付付きチェック"], "nl": ["Controle met datum"], "no": ["Datert kontroll"], "pl": ["Datowana kontrola"], "pt": ["Verificação datada"], "ru": ["Проверка с датой"], "sv": ["Daterad kontroll"], "zh_CN": ["按日期存档的检查"]},
 "repeated_checks": {"de": ["Wiederholte", "Prüfungen", "mit der Zeit"], "es": ["Controles", "repetidos", "en el tiempo"], "fr": ["Contrôles", "répétés", "sur la durée"], "it": ["Verifiche", "ripetute", "nel tempo"], "ja": ["繰り返し", "チェック", "（時系列）"], "nl": ["Herhaalde", "controles", "in de tijd"], "no": ["Gjentatte", "kontroller", "over tid"], "pl": ["Powtarzane", "kontrole", "w czasie"], "pt": ["Verificações", "repetidas", "com o tempo"], "ru": ["Повторные", "проверки", "со временем"], "sv": ["Upprepade", "kontroller", "över tid"], "zh_CN": ["定期重复", "检查", "（随时间）"]},
 "with_trends": {"de": ["(mit Trends)"], "es": ["(con tendencias)"], "fr": ["(avec tendances)"], "it": ["(con tendenze)"], "ja": ["（傾向つき）"], "nl": ["(met trends)"], "no": ["(med trender)"], "pl": ["(z trendami)"], "pt": ["(com tendências)"], "ru": ["(с трендами)"], "sv": ["(med trender)"], "zh_CN": ["（含趋势）"]},
 "as_in": {"de": ["Wie in", "run 1"], "es": ["Como en", "run 1"], "fr": ["Comme", "run 1"], "it": ["Come in", "run 1"], "ja": ["run 1 と", "同じ"], "nl": ["Zoals in", "run 1"], "no": ["Som i", "run 1"], "pl": ["Jak w", "run 1"], "pt": ["Como em", "run 1"], "ru": ["Как в", "run 1"], "sv": ["Som i", "run 1"], "zh_CN": ["与 run 1", "相同"]},
 "as_above": {"de": ["Wie oben"], "es": ["Como arriba"], "fr": ["Idem"], "it": ["Come sopra"], "ja": ["同上"], "nl": ["Zoals boven"], "no": ["Som over"], "pl": ["Jak wyżej"], "pt": ["Como acima"], "ru": ["Как выше"], "sv": ["Som ovan"], "zh_CN": ["同上"]},
 "raw_no_profile": {"de": ["\"roh, ohne", "Profil\""], "es": ["\"en bruto,", "sin perfil\""], "fr": ["\"brut, sans", "profil\""], "it": ["\"raw, senza", "profilo\""], "ja": ["「プロファイ", "ルなし」"], "nl": ["\"raw, geen", "profiel\""], "no": ["\"rå, uten", "profil\""], "pl": ["\"raw, bez", "profilu\""], "pt": ["\"em bruto,", "sem perfil\""], "ru": ["\"без", "профиля\""], "sv": ["\"rått, utan", "profil\""], "zh_CN": ["“原样，无", "配置文件”"]},
 "date_placeholder": {"de": ["<datum>/"], "es": ["<fecha>/"], "fr": ["<date>/"], "it": ["<data>/"], "ja": ["<日付>/"], "nl": ["<datum>/"], "no": ["<dato>/"], "pl": ["<data>/"], "pt": ["<data>/"], "ru": ["<дата>/"], "sv": ["<datum>/"], "zh_CN": ["<日期>/"]},
 "n_patches_3pages": {"de": ["1944", "Messfelder", "3 Seiten"], "es": ["1944", "parches", "3 páginas"], "fr": ["1944", "plages", "3 pages"], "it": ["1944", "tasselli", "3 pagine"], "ja": ["1944", "パッチ", "3 ページ"], "nl": ["1944", "meetvelden", "3 pagina's"], "no": ["1944", "felt", "3 sider"], "pl": ["1944", "pola", "3 strony"], "pt": ["1944", "amostras", "3 páginas"], "ru": ["1944", "патча", "3 страницы"], "sv": ["1944", "fält", "3 sidor"], "zh_CN": ["1944", "色块", "3 页"]},
 "n_patches_1page_484": {"de": ["484 Messfelder", "1 Seite"], "es": ["484 parches", "1 página"], "fr": ["484 plages", "1 page"], "it": ["484 tasselli", "1 pagina"], "ja": ["484 パッチ", "1 ページ"], "nl": ["484 meetvelden", "1 pagina"], "no": ["484 felt", "1 side"], "pl": ["484 pola", "1 strona"], "pt": ["484 amostras", "1 página"], "ru": ["484 патча", "1 страница"], "sv": ["484 fält", "1 sida"], "zh_CN": ["484 色块", "1 页"]},
 "n_patches_1page_240": {"de": ["240 Messfelder", "1 Seite"], "es": ["240 parches", "1 página"], "fr": ["240 plages", "1 page"], "it": ["240 tasselli", "1 pagina"], "ja": ["240 パッチ", "1 ページ"], "nl": ["240 meetvelden", "1 pagina"], "no": ["240 felt", "1 side"], "pl": ["240 pól", "1 strona"], "pt": ["240 amostras", "1 página"], "ru": ["240 патчей", "1 страница"], "sv": ["240 fält", "1 sida"], "zh_CN": ["240 色块", "1 页"]},
 "measure": {"de": ["Messen"], "es": ["Medir"], "fr": ["Mesurer"], "it": ["Misura"], "ja": ["測定"], "nl": ["Meten"], "no": ["Mål"], "pl": ["Pomiar"], "pt": ["Medir"], "ru": ["Измерение"], "sv": ["Mät"], "zh_CN": ["测量"]},
 "measurement_report_2l": {"de": ["Messbericht", ""], "es": ["Informe de", "medición"], "fr": ["Rapport de", "mesure"], "it": ["Rapporto di", "misura"], "ja": ["測定", "レポート"], "nl": ["Meetrapport", ""], "no": ["Målerapport", ""], "pl": ["Raport", "pomiaru"], "pt": ["Relatório de", "medição"], "ru": ["Отчёт об", "измерении"], "sv": ["Mätrapport", ""], "zh_CN": ["测量", "报告"]},
 "refine": {"de": ["Verfeinern"], "es": ["Refinar"], "fr": ["Affiner"], "it": ["Affina"], "ja": ["改良"], "nl": ["Verfijnen"], "no": ["Forbedre"], "pl": ["Dopracuj"], "pt": ["Refinar"], "ru": ["Уточнить"], "sv": ["Förfina"], "zh_CN": ["精修"]},
 "create_chart_2l": {"de": ["Chart", "erstellen"], "es": ["Crear", "carta"], "fr": ["Créer la", "mire"], "it": ["Crea", "grafico"], "ja": ["チャート", "作成"], "nl": ["Kaart", "maken"], "no": ["Lag", "kart"], "pl": ["Utwórz", "wzorzec"], "pt": ["Criar", "carta"], "ru": ["Создать", "шкалу"], "sv": ["Skapa", "diagram"], "zh_CN": ["创建", "色卡"]},
 "print_chart_2l": {"de": ["Chart", "drucken"], "es": ["Imprimir", "carta"], "fr": ["Imprimer", "la mire"], "it": ["Stampa", "grafico"], "ja": ["チャート", "印刷"], "nl": ["Kaart", "afdrukken"], "no": ["Skriv ut", "kart"], "pl": ["Drukuj", "wzorzec"], "pt": ["Imprimir", "carta"], "ru": ["Печать", "шкалы"], "sv": ["Skriv ut", "diagram"], "zh_CN": ["打印", "色卡"]},
 "build_profile_2l": {"de": ["Profil", "erstellen"], "es": ["Crear", "perfil"], "fr": ["Créer le", "profil"], "it": ["Crea", "profilo"], "ja": ["プロファイル", "作成"], "nl": ["Profiel", "maken"], "no": ["Bygg", "profil"], "pl": ["Zbuduj", "profil"], "pt": ["Criar", "perfil"], "ru": ["Собрать", "профиль"], "sv": ["Bygg", "profil"], "zh_CN": ["生成", "配置文件"]},
 "check_refine_2l": {"de": ["Prüfen &", "Verfeinern"], "es": ["Comprobar y", "refinar"], "fr": ["Vérifier et", "affiner"], "it": ["Verifica e", "affina"], "ja": ["検証と", "改良"], "nl": ["Controleren", "& verfijnen"], "no": ["Sjekk &", "forbedre"], "pl": ["Sprawdź i", "dopracuj"], "pt": ["Verificar e", "refinar"], "ru": ["Проверить и", "уточнить"], "sv": ["Kontrollera", "och förfina"], "zh_CN": ["检查与", "精修"]},
 "create_from_gamut_3l": {"de": ["Chart aus dem", "Profil-Gamut", "erstellen"], "es": ["Crear carta", "desde el gamut", "del perfil"], "fr": ["Créer la mire", "depuis le gamut", "du profil"], "it": ["Crea grafico", "dal gamut del", "profilo"], "ja": ["プロファイルの", "色域から", "チャート作成"], "nl": ["Kaart maken", "uit het", "profielgamut"], "no": ["Lag kart fra", "profilens", "gamut"], "pl": ["Utwórz wzorzec", "z gamutu", "profilu"], "pt": ["Criar carta", "do gamut", "do perfil"], "ru": ["Создать шкалу", "из охвата", "профиля"], "sv": ["Skapa diagram", "från profilens", "gamut"], "zh_CN": ["从配置文件", "色域创建", "色卡"]},
 "profile_run_n": {"de": ["Profillauf: run {n}"], "es": ["Ejec. del perfil: run {n}"], "fr": ["Exéc. du profil : run {n}"], "it": ["Esec. profilo: run {n}"], "ja": ["プロファイル実行: run {n}"], "nl": ["Profielrun: run {n}"], "no": ["Profilkjøring: run {n}"], "pl": ["Przebieg profilu: run {n}"], "pt": ["Exec. do perfil: run {n}"], "ru": ["Запуск профиля: run {n}"], "sv": ["Profilkörning: run {n}"], "zh_CN": ["配置文件运行: run {n}"]},
 "run_type_profiling": {"de": ["Lauftyp: Profilierung"], "es": ["Tipo de ejec.: Perfilado"], "fr": ["Type d'exéc. : Profilage"], "it": ["Tipo esec.: Profilazione"], "ja": ["実行タイプ: プロファイリング"], "nl": ["Runtype: Profilering"], "no": ["Kjøringstype: Profilering"], "pl": ["Typ przebiegu: Profilowanie"], "pt": ["Tipo de exec.: Perfilagem"], "ru": ["Тип запуска: Профилирование"], "sv": ["Körningstyp: Profilering"], "zh_CN": ["运行类型: 特性化"]},
 "run_type_verification": {"de": ["Lauftyp: Verifizierung"], "es": ["Tipo de ejec.: Verificación"], "fr": ["Type d'exéc. : Vérification"], "it": ["Tipo esec.: Verifica"], "ja": ["実行タイプ: 検証"], "nl": ["Runtype: Verificatie"], "no": ["Kjøringstype: Verifisering"], "pl": ["Typ przebiegu: Weryfikacja"], "pt": ["Tipo de exec.: Verificação"], "ru": ["Тип запуска: Проверка"], "sv": ["Körningstyp: Verifiering"], "zh_CN": ["运行类型: 验证"]},
 # The dated check's Report box — the short act of saving that check's
 # report (the Measurement-report family word, one line).
 "report_box": {"de": ["Bericht"], "es": ["Informe"], "fr": ["Rapport"], "it": ["Rapporto"], "ja": ["レポート"], "nl": ["Rapport"], "no": ["Rapport"], "pl": ["Raport"], "pt": ["Relatório"], "ru": ["Отчёт"], "sv": ["Rapport"], "zh_CN": ["报告"]},
}

#: Labels sourced from the app's own catalogues at generation time:
#: key here → (catalogue key, suffix appended after the translation).
FROM_CATALOGUE = {
    "printer_profile_project_name": ("Printer profile project name:", ""),
    "folder_label": ("Folder", ":"),
    "duplicate": ("Duplicate", ""),
}

#: English text expected at each mapped <text> index (in document order),
#: with its label key, line number and anchor: 'c' centres the replacement
#: on the original run's centre (box labels), 'l' keeps its left edge
#: (annotations). Unlisted indices are left byte-identical — the folder
#: names, dates and example file names, which never translate.
TABLE = [
    (0,   "Printer Profile Project Name:", "printer_profile_project_name", 0, "l", None),
    (3,   "Profile run: run 1",   "profile_run_n",        0, "r", 1),
    (4,   "Run type: Profiling",  "run_type_profiling",   0, "r", None),
    (5,   "Create ",              "create_chart_2l",      0, "c", None),
    (6,   "Chart",                "create_chart_2l",      1, "c", None),
    (7,   "Print ",               "print_chart_2l",       0, "c", None),
    (8,   "Chart",                "print_chart_2l",       1, "c", None),
    (9,   "Measure",              "measure",              0, "c", None),
    (10,  "Build ",               "build_profile_2l",     0, "c", None),
    (11,  "Profile",              "build_profile_2l",     1, "c", None),
    (12,  "Check &#x0026; ",      "check_refine_2l",      0, "c", None),
    (13,  "Refine",               "check_refine_2l",      1, "c", None),
    (14,  "1944 ",                "n_patches_3pages",     0, "r", None),
    (15,  "patches ",             "n_patches_3pages",     1, "r", None),
    (16,  "3-pages",              "n_patches_3pages",     2, "r", None),
    (17,  "\"raw, no ",           "raw_no_profile",       0, "l", None),
    (18,  "profile\"",            "raw_no_profile",       1, "l", None),
    (20,  "Refine",               "refine",               0, "c", None),
    (21,  "Profile run: run 1",   "profile_run_n",        0, "r", 1),
    (22,  "Run type: Verification", "run_type_verification", 0, "r", None),
    (23,  "Create Chart ",        "create_from_gamut_3l", 0, "c", None),
    (24,  "From Profile ",        "create_from_gamut_3l", 1, "c", None),
    (25,  "Gamut",                "create_from_gamut_3l", 2, "c", None),
    (26,  "Dated Check",          "dated_check",          0, "r", None),
    (28,  "Print ",               "print_chart_2l",       0, "c", None),
    (29,  "Chart",                "print_chart_2l",       1, "c", None),
    (30,  "Measure",              "measure",              0, "c", None),
    (31,  "Report",               "report_box",           0, "c", None),
    (32,  "Folder:",              "folder_label",         0, "l", None),
    (33,  "&#x003c;date&#x003e;/", "date_placeholder",    0, "l", None),
    (34,  "Folder:",              "folder_label",         0, "l", None),
    (35,  "&#x003c;date&#x003e;/", "date_placeholder",    0, "l", None),
    (37,  "\"raw, no ",           "raw_no_profile",       0, "l", None),
    (38,  "profile\"",            "raw_no_profile",       1, "l", None),
    (39,  "Measurement",          "measurement_report_2l", 0, "c", None),
    (40,  "Report",               "measurement_report_2l", 1, "c", None),
    (41,  "(With Trends)",        "with_trends",          0, "c", None),
    (42,  "484 patches ",         "n_patches_1page_484",  0, "l", None),
    (43,  "1-page",               "n_patches_1page_484",  1, "l", None),
    (44,  "Dated Check",          "dated_check",          0, "r", None),
    (46,  "Print ",               "print_chart_2l",       0, "c", None),
    (47,  "Chart",                "print_chart_2l",       1, "c", None),
    (48,  "Measure",              "measure",              0, "c", None),
    (49,  "Report",               "report_box",           0, "c", None),
    (50,  "Folder:",              "folder_label",         0, "l", None),
    (51,  "&#x003c;date&#x003e;/", "date_placeholder",    0, "l", None),
    (52,  "Folder:",              "folder_label",         0, "l", None),
    (53,  "&#x003c;date&#x003e;/", "date_placeholder",    0, "l", None),
    (55,  "\"raw, no ",           "raw_no_profile",       0, "l", None),
    (56,  "profile\"",            "raw_no_profile",       1, "l", None),
    (57,  "Repeated ",            "repeated_checks",      0, "c", None),
    (58,  "Checks ",              "repeated_checks",      1, "c", None),
    (59,  "over time",            "repeated_checks",      2, "c", None),
    (60,  "Folder:",              "folder_label",         0, "l", None),
    (62,  "Run 1 Description: ",  "run_description",      0, "l", 1),
    (65,  "Example Workflow and Relationship to Folder Locations", "title", 0, "c", None),
    (67,  "Profile run: run 2",   "profile_run_n",        0, "r", 2),
    (68,  "Run type: Profiling",  "run_type_profiling",   0, "r", None),
    (69,  "Create ",              "create_chart_2l",      0, "c", None),
    (70,  "Chart",                "create_chart_2l",      1, "c", None),
    (71,  "Print ",               "print_chart_2l",       0, "c", None),
    (72,  "Chart",                "print_chart_2l",       1, "c", None),
    (73,  "Measure",              "measure",              0, "c", None),
    (74,  "Build ",               "build_profile_2l",     0, "c", None),
    (75,  "Profile",              "build_profile_2l",     1, "c", None),
    (76,  "1944 ",                "n_patches_3pages",     0, "r", None),
    (77,  "patches ",             "n_patches_3pages",     1, "r", None),
    (78,  "3-pages",              "n_patches_3pages",     2, "r", None),
    (79,  "\"raw, no ",           "raw_no_profile",       0, "l", None),
    (80,  "profile\"",            "raw_no_profile",       1, "l", None),
    (81,  "Duplicate",            "duplicate",            0, "c", None),
    (82,  "Profile run: run 2",   "profile_run_n",        0, "r", 2),
    (83,  "Run type: Verification", "run_type_verification", 0, "r", None),
    (84,  "Create Chart ",        "create_from_gamut_3l", 0, "c", None),
    (85,  "From Profile ",        "create_from_gamut_3l", 1, "c", None),
    (86,  "Gamut",                "create_from_gamut_3l", 2, "c", None),
    (87,  "Dated Check",          "dated_check",          0, "r", None),
    (89,  "As in",                "as_in",                0, "c", None),
    (90,  "run 1",                "as_in",                1, "c", None),
    (91,  "Dated Check",          "dated_check",          0, "r", None),
    (93,  "As in",                "as_in",                0, "c", None),
    (94,  "run 1",                "as_in",                1, "c", None),
    (95,  "240 patches ",         "n_patches_1page_240",  0, "l", None),
    (96,  "1-page",               "n_patches_1page_240",  1, "l", None),
    (97,  "Repeated ",            "repeated_checks",      0, "c", None),
    (98,  "Checks ",              "repeated_checks",      1, "c", None),
    (99,  "over time",            "repeated_checks",      2, "c", None),
    (100, "Folder:",              "folder_label",         0, "l", None),
    (102, "Measurement",          "measurement_report_2l", 0, "c", None),
    (103, "Report",               "measurement_report_2l", 1, "c", None),
    (104, "(With Trends)",        "with_trends",          0, "c", None),
    (105, "Run 2 Description: ",  "run_description",      0, "l", 2),
    (108, "Profile run: run 3",   "profile_run_n",        0, "r", 3),
    (109, "Run type: Profiling",  "run_type_profiling",   0, "r", None),
    (110, "As Above",             "as_above",             0, "c", None),
    (111, "Profile run: run 3",   "profile_run_n",        0, "r", 3),
    (112, "Run type: Verification", "run_type_verification", 0, "r", None),
    (113, "As Above",             "as_above",             0, "c", None),
    (114, "Run 3 Description: ",  "run_description",      0, "l", 3),
    (118, "Lege",                 "legend",               0, "r", None),
    (119, "&#x2026;",             "__drop__",             0, "l", None),
    (120, "folder_path/",         "folder_path_sample",   0, "c", None),
    (121, "Action",               "action",               0, "c", None),
    (122, "Normal ",              "normal_workflow",      0, "c", None),
    (123, "Workflow",             "normal_workflow",      1, "c", None),
    (124, "Path in relation ",    "path_note",            0, "l", None),
    (125, "to ChromIQ ",          "path_note",            1, "l", None),
    (126, "default folder.",      "path_note",            2, "l", None),
]

#: English also goes through the pipeline — the legend repair applies to it
#: too — with every label mapped to itself.
EN_SELF = {"legend": ["Legend:"], "__drop__": [""]}

_TEXT_RE = re.compile(
    r'(<text[^>]*font-family="(?P<font>[^"]+)"[^>]*>)'
    r'<tspan(?P<attrs>[^>]*)>(?P<content>[^<]*)</tspan></text>')


def _cataloguish(lang: str) -> dict:
    if lang == "en":
        return {"printer_profile_project_name": ["Printer Profile Project Name:"],
                "folder_label": ["Folder:"], "duplicate": ["Duplicate"]}
    cat = json.loads((ROOT / "data" / "i18n" / f"{lang}.json").read_text(encoding="utf-8"))
    out = {}
    for key, (cat_key, suffix) in FROM_CATALOGUE.items():
        out[key] = [str(cat.get(cat_key, cat_key)) + suffix]
    return out


def _labels_for(lang: str) -> dict:
    if lang == "en":
        base = {k: None for k in T}
        base.update(EN_SELF)
        base.update(_cataloguish("en"))
        return base
    out = {k: v[lang] for k, v in T.items()}
    out["__drop__"] = [""]
    out.update(_cataloguish(lang))
    return out


def _run_center(attrs: str) -> "tuple[float, float]":
    """(left x, centre x) of the tspan's per-glyph run, in text units."""
    m = re.search(r'x="([^"]+)"', attrs)
    xs = [float(v) for v in m.group(1).split()] if m else [0.0]
    left = xs[0]
    right = xs[-1] + 0.6          # ~ the last glyph's advance
    return left, (left + right) / 2.0


def generate() -> int:
    import pymupdf
    doc = pymupdf.open(PDF)
    page = doc[0]
    svg = page.get_svg_image(text_as_path=False)

    # Crop to the drawing: the PDF page carries generous margins.
    bbox = page.rect
    items = page.get_bboxlog()
    xs0, ys0, xs1, ys1 = [], [], [], []
    for _kind, r in items:
        xs0.append(r[0]); ys0.append(r[1]); xs1.append(r[2]); ys1.append(r[3])
    pad = 6
    vb = (max(0, min(xs0) - pad), max(0, min(ys0) - pad),
          min(bbox.width, max(xs1) + pad) - max(0, min(xs0) - pad),
          min(bbox.height, max(ys1) + pad) - max(0, min(ys0) - pad))

    # Collect the text elements in document order once, to verify the table.
    found = _TEXT_RE.findall(svg)
    texts = [m[3] for m in found]
    problems = []
    for idx, expect, _k, _ln, _a, _n in TABLE:
        if idx >= len(texts) or texts[idx] != expect:
            got = texts[idx] if idx < len(texts) else "<missing>"
            problems.append(f"index {idx}: expected {expect!r}, got {got!r}")
    if problems:
        print("The PDF no longer matches the label table — re-derive it:")
        for p in problems:
            print("  ✗", p)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    by_index = {row[0]: row for row in TABLE}

    def _geom(i: int) -> "tuple[float, float, float, float]":
        """(scale, page-x origin, local left, local right) of text run *i*."""
        head_i, _f, attrs_i, _c = found[i]
        mm = re.search(r'matrix\(([\d.\-]+) [\d.\-]+ -?[\d.]+ [\d.\-]+ '
                       r'([\d.\-]+) [\d.\-]+\)', head_i)
        scale, e = float(mm.group(1)), float(mm.group(2))
        left, cxx = _run_center(attrs_i)
        right = cxx + (cxx - left)
        return scale, e, left, right

    # Multi-line annotations read best centred on ONE common axis per
    # block (Sebastian, reviewing language by language: the patch counts
    # were ragged, the Italian raw note kissed the box border, "Gjentatte
    # kontroller over tid" and "Målerapport (med trender)" sat uneven) —
    # computed in page coordinates because every line is its own <text>
    # with its own origin.
    block_cx: "dict[int, float]" = {}
    for group in ((14, 15, 16, 17, 18), (76, 77, 78, 79, 80),
                  (37, 38), (55, 56),          # dated checks' raw notes
                  (57, 58, 59), (97, 98, 99),  # repeated checks over time
                  (39, 40, 41), (102, 103, 104)):  # measurement report box
        lo = min(_geom(i)[1] + _geom(i)[2] * _geom(i)[0] for i in group)
        hi = max(_geom(i)[1] + _geom(i)[3] * _geom(i)[0] for i in group)
        page_c = (lo + hi) / 2
        for i in group:
            scale, e, _l, _r = _geom(i)
            block_cx[i] = (page_c - e) / scale

    # Label-centre nudges in PAGE units, converted per run: the two legend
    # boxes are widened to the right below, so their labels move with them.
    dx_page = {"action": 6.0, "folder_path_sample": 5.0}

    #: The profiling column's left slot ends at the Create/Print BOX edge —
    #: page x ≈ 215.3 for run 1 (measured off the drawn border, not the
    #: text clip inside it, which sits 8 units deeper and fooled the first
    #: cut). Centred lines whose estimated width would reach the edge are
    #: pushed left so they always keep clear air — pixels lie when text and
    #: box merge into one dark run, so the guarantee lives in the geometry
    #: ("raw, senza profilo" touched the box, Sebastian, twice).
    right_limit_page = {i: 213.3 for i in (14, 15, 16, 17, 18)}
    right_limit_page.update({i: 211.4 for i in (76, 77, 78, 79, 80)})

    def _est_width_em(text: str) -> float:
        """Generous per-character advance estimate (Inter ≈0.55 em average;
        CJK a full em) — overshooting only pushes text a little further
        from the box, never into it."""
        return sum(1.05 if ord(c) > 0x2E80 else 0.62 for c in text)

    for lang in ["en"] + LANGS:
        labels = _labels_for(lang)

        # Clamp whole LABELS, not single lines: every line of a label
        # shifts by the worst line's overshoot, so the pair stays visually
        # one block instead of going ragged.
        clamp_shift: "dict[int, float]" = {}
        for inst in ((14, 15, 16), (17, 18), (76, 77, 78), (79, 80)):
            shifts = [0.0]
            for i in inst:
                if i not in right_limit_page or i not in block_cx:
                    continue
                _idx, _exp, key_i, ln_i, _a, _n = by_index[i]
                lines_i = labels.get(key_i)
                if not lines_i:
                    continue
                txt_i = lines_i[ln_i] if ln_i < len(lines_i) else ""
                scale_i, e_i, _l, _r = _geom(i)
                limit_i = (right_limit_page[i] - e_i) / scale_i
                shifts.append(max(0.0, (block_cx[i]
                                        + _est_width_em(txt_i) / 2)
                                  - limit_i))
            for i in inst:
                clamp_shift[i] = max(shifts)

        counter = {"i": -1}

        def _sub(m) -> str:
            counter["i"] += 1
            idx = counter["i"]
            head, font, attrs, content = (m.group(1), m.group("font"),
                                          m.group("attrs"), m.group("content"))
            # Normalise the PDF's subset fonts to the app's own Inter.
            head = re.sub(r'font-family="[^"]+"',
                          'font-family="Inter"', head)
            if "Bold" in font and "font-weight" not in head:
                head = head[:-1] + ' font-weight="bold">'

            row = by_index.get(idx)
            if row is None:
                return head + f"<tspan{attrs}>{content}</tspan></text>"
            _i, expect, key, line_no, anchor, n = row
            lines = labels[key]
            if lang == "en" and lines is None:
                return head + f"<tspan{attrs}>{content}</tspan></text>"
            text = lines[line_no] if line_no < len(lines) else ""
            if n is not None:
                text = text.replace("{n}", str(n))
            if not text:
                return head + "</text>"
            left, cx = _run_center(attrs)
            if idx in block_cx:
                cx = block_cx[idx] - clamp_shift.get(idx, 0.0)
                anchor = "c"
            if key in dx_page:
                scale = _geom(idx)[0]
                cx += dx_page[key] / scale
            y = re.search(r'y="([^"]+)"', attrs)
            y_attr = f' y="{y.group(1)}"' if y else ""
            esc = html.escape(text, quote=False)
            # QtSvg quirks, learned the hard way: text-anchor on a tspan
            # is ignored outright, and with the anchor inherited from the
            # text element a SINGLE x on the tspan is ignored too (each
            # cut looked fine in the file and wrong on screen). So a
            # replaced run drops the tspan entirely: position and anchor
            # both live on the text element.
            y_val = y.group(1) if y else "0"
            if anchor == "c":
                pos = f' x="{cx:.3f}" y="{y_val}" text-anchor="middle">'
            elif anchor == "r":
                # yEd right-aligns the panel headers to the panel edge;
                # anchoring the translation to the original run's RIGHT
                # edge keeps longer strings growing inward instead of
                # spilling over the panel border (seen in ja and ru). The
                # raw-print note originally ends flush at its box border,
                # so it gets a little air pulled off its right edge.
                right = cx + (cx - left)
                if key == "raw_no_profile":
                    right -= 0.6
                pos = f' x="{right:.3f}" y="{y_val}" text-anchor="end">'
            else:
                pos = f' x="{left:.3f}" y="{y_val}">'
            return head[:-1] + pos + esc + "</text>"

        counter["i"] = -1
        out = _TEXT_RE.sub(_sub, svg)
        # Widen the two legend boxes to the right (Knut offered a new
        # export for exactly this — not needed, the boxes are plain paths
        # here): "Action" grows 23 → 35 page units for "Handling"/
        # "Действие"/"Działanie", the folder tag 46 → 56 for
        # "ścieżka_folderu/". Their grey fills and text clips are rects in
        # page space; their outlines live in the drawing's second
        # coordinate space (scale 0.5227705), where the same widening is
        # applied to every x past the box's fixed left part — safe because
        # both paths are all-absolute and their y values sit far below the
        # threshold.
        out = out.replace("M478.1375 768.0551H501.1375V776.0551H478.1375Z",
                          "M478.1375 768.0551H513.1375V776.0551H478.1375Z")
        out = out.replace("M478.1375 785.0551H524.1375V793.0551H478.1375Z",
                          "M478.1375 785.0551H534.1375V793.0551H478.1375Z")

        def _widen(match: "re.Match", threshold: float, dx: float) -> str:
            def rep(nm: "re.Match") -> str:
                v = float(nm.group(0))
                return f"{v + dx:.4f}" if v >= threshold else nm.group(0)
            return 'd="' + re.sub(r'-?\d+\.?\d*', rep, match.group(1)) + '"'

        out = re.sub(r'd="(M911\.9727 206\.5H[^"]+)"',
                     lambda m: _widen(m, 990.0, 10.0 / 0.5227705), out)
        out = re.sub(r'd="(M911\.9727 246\.1836V[^"]+)"',
                     lambda m: _widen(m, 950.0, 12.0 / 0.5227705), out)
        out = re.sub(
            r'width="[\d.]+" height="[\d.]+" viewBox="[\d. ]+"',
            f'width="{vb[2]:.0f}" height="{vb[3]:.0f}" '
            f'viewBox="{vb[0]:.0f} {vb[1]:.0f} {vb[2]:.0f} {vb[3]:.0f}"',
            out, count=1)
        (OUT_DIR / f"{lang}.svg").write_text(out, encoding="utf-8")
        print(f"  {lang}.svg written")
    print(f"\n{len(TABLE)} labels verified against the PDF; "
          f"{1 + len(LANGS)} SVGs in {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(generate())
