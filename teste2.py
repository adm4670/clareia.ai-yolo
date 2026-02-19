#!/usr/bin/env python3
"""
ENEM PDF → Markdown Extractor
================================
Extrai questões de provas do ENEM (e similares) para Markdown estruturado.

Uso:
    python enem_extractor.py <arquivo.pdf> [saida.md]
    python enem_extractor.py prova.pdf               # salva como prova.md
    python enem_extractor.py prova.pdf questoes.md   # salva como questoes.md
    python enem_extractor.py prova.pdf -v            # modo verbose (diagnóstico)

Dependências:
    pip install pdfplumber

Características:
  ✓ Detecta automaticamente layout de 1 ou 2 colunas por página
  ✓ Reconstrói a ordem de leitura correta (coluna esquerda → coluna direita)
  ✓ Separa enunciados, citações/referências e alternativas A–E
  ✓ Agrupa questões por área de conhecimento quando disponível
  ✓ Remove ruídos: rodapés, marcas de página, headers repetidos
  ✓ Funciona com variações de formatação entre anos/cadernos do ENEM
"""

import re
import sys
from pathlib import Path

try:
    import pdfplumber
except ImportError:
    print("Erro: pdfplumber não encontrado. Execute: pip install pdfplumber")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# CONSTANTES E PADRÕES
# ─────────────────────────────────────────────────────────────────────────────

# Distância mínima entre colunas (pts) para classificar como layout 2 colunas
COLUMN_GAP_MIN = 20

# Tolerância vertical para agrupar palavras na mesma linha (pts)
LINE_Y_TOLERANCE = 4

# Padrões de linhas que devem ser descartadas (ruído)
NOISE_PATTERNS = [
    r"^\*[A-Z0-9]{4,}\*$",                                   # marcas tipo *AZUL75SAB2*
    r"^(CH|CN|LC|MT)\s*[-–]\s*\d[ºo°]\s*dia.*página\s*\d+", # rodapés de caderno
    r"^\d{4}$",                                               # anos isolados (ex: 2013)
    r"^enem\s*\d*$",                                          # logo ENEM
    r"^\d[ºo°]\s*DIA\s*$",                                    # "1º DIA" isolado
    r"^CADERNO\s*$",                                          # "CADERNO" isolado
    r"^\d+\s*$",                                              # números isolados
    r"^(AZUL|AMARELO|BRANCO|ROSA|CINZA|VERDE|LARANJA)\s*$",  # cor isolada
]
NOISE_RE = [re.compile(p, re.IGNORECASE) for p in NOISE_PATTERNS]

# Padrão de marcador de questão
QUESTAO_RE = re.compile(r"^QUES[TÃ][ÃA]O\s+(\d{1,3})\s*$", re.IGNORECASE)
QUESTAO_SEARCH_RE = re.compile(r"\bQUES[TÃ][ÃA]O\s+(\d{1,3})\b", re.IGNORECASE)

# Alternativas: letra A–E isolada ou seguida de texto
ALTERNATIVA_FULL_RE = re.compile(r"^([A-E])\s{1,6}(.+)$")
ALTERNATIVA_LETTER_RE = re.compile(r"^([A-E])\s*$")

# Cabeçalhos de área de conhecimento
AREA_HEADER_RE = re.compile(
    r"CI[EÊ]NCIAS\s+(HUMANAS|DA\s+NATUREZA|EXATAS|SOCIAIS)|"
    r"LINGUAGENS|MATEM[AÁ]TICA|REDAÇÃO",
    re.IGNORECASE,
)
QUESTOES_RANGE_RE = re.compile(r"Questões?\s+de\s+\d+\s+a\s+\d+", re.IGNORECASE)


# ─────────────────────────────────────────────────────────────────────────────
# EXTRAÇÃO DE TEXTO COM LAYOUT
# ─────────────────────────────────────────────────────────────────────────────

def detect_column_boundary(words: list, page_width: float) -> float | None:
    """
    Detecta se a página tem duas colunas e retorna a coordenada x de separação.
    Retorna None para páginas de coluna única.

    Estratégia: analisa a distribuição de posições x0 das palavras na zona central
    da página e detecta o vale entre dois grupos densos (as duas colunas).
    Usa max(x0_coluna_esquerda) e min(x0_coluna_direita) para encontrar o gap real.
    """
    if not words:
        return None

    mid = page_width / 2
    # Foco nas palavras próximas ao centro (±40% da largura)
    search_window = mid * 0.4
    center_words_x0 = [
        w["x0"] for w in words if abs(w["x0"] - mid) < search_window
    ]

    if not center_words_x0:
        return None

    left_xs = [x for x in center_words_x0 if x < mid]
    right_xs = [x for x in center_words_x0 if x >= mid]

    # Ambas as colunas precisam ter conteúdo substancial
    if len(left_xs) < 5 or len(right_xs) < 5:
        return None

    # A fronteira está entre o maior x0 da coluna esquerda e o menor da direita
    left_max = max(left_xs)
    right_min = min(right_xs)

    if right_min <= left_max:
        return None  # Sem separação clara

    # Valida: deve haver ao menos 5pts de espaço entre as colunas
    if right_min - left_max < 5:
        return None

    return (left_max + right_min) / 2


def words_to_lines(words: list, y_tolerance: int = LINE_Y_TOLERANCE) -> list[str]:
    """
    Agrupa palavras em linhas de texto pela posição vertical (top).
    """
    if not words:
        return []

    buckets: dict[int, list] = {}
    for w in words:
        key = round(w["top"] / y_tolerance) * y_tolerance
        buckets.setdefault(key, []).append(w)

    lines = []
    for top in sorted(buckets.keys()):
        line_words = sorted(buckets[top], key=lambda x: x["x0"])
        lines.append(" ".join(w["text"] for w in line_words))

    return lines


def extract_page_lines(page) -> list[str]:
    """
    Extrai linhas de texto de uma página respeitando layout de 2 colunas.
    Para 2 colunas: lê coluna esquerda completamente, depois coluna direita.
    """
    words = page.extract_words(
        keep_blank_chars=False,
        x_tolerance=3,
        y_tolerance=3,
    )
    if not words:
        return []

    col_boundary = detect_column_boundary(words, page.width)

    if col_boundary is None:
        return words_to_lines(words)

    # Usa x0 para classificar: palavra pertence à coluna onde seu INÍCIO está
    left_words = [w for w in words if w["x0"] < col_boundary]
    right_words = [w for w in words if w["x0"] >= col_boundary]

    return words_to_lines(left_words) + words_to_lines(right_words)


# ─────────────────────────────────────────────────────────────────────────────
# LIMPEZA DE LINHAS
# ─────────────────────────────────────────────────────────────────────────────

def fix_ocr_duplicates(text: str) -> str:
    """Corrige duplicação de caracteres de OCR (ex: PPRRIINNCC → PRINC)."""
    return re.sub(r"(.)\1{2,}", lambda m: m.group(1), text)


def is_noise(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    for pattern in NOISE_RE:
        if pattern.match(stripped):
            return True
    return False


def clean_lines(lines: list[str]) -> list[str]:
    result = []
    for line in lines:
        line = fix_ocr_duplicates(line.strip())
        if not is_noise(line):
            result.append(line)
    return result


# ─────────────────────────────────────────────────────────────────────────────
# NORMALIZAÇÃO DE ALTERNATIVAS
# ─────────────────────────────────────────────────────────────────────────────

def merge_alternativas(lines: list[str]) -> list[str]:
    """
    Junta alternativas quebradas em linhas separadas.
    Caso 1: letra "A" isolada + próxima linha = texto da alternativa
    Caso 2: alternativa + próxima linha sem letra = continuação
    """
    # Passagem 1: junta letra isolada com linha seguinte
    result: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if ALTERNATIVA_LETTER_RE.match(line):
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                # Só junta se a próxima linha não é outra estrutura
                if (next_line
                        and not QUESTAO_SEARCH_RE.search(next_line)
                        and not ALTERNATIVA_LETTER_RE.match(next_line)
                        and not ALTERNATIVA_FULL_RE.match(next_line)):
                    result.append(f"{line} {next_line}")
                    i += 2
                    continue
        result.append(lines[i])
        i += 1

    # Passagem 2: junta continuações de alternativas (linhas que sobram)
    merged: list[str] = []
    i = 0
    while i < len(result):
        line = result[i]
        stripped = line.strip()
        m = ALTERNATIVA_FULL_RE.match(stripped)
        if m:
            j = i + 1
            while j < len(result):
                nxt = result[j].strip()
                if (nxt
                        and not ALTERNATIVA_FULL_RE.match(nxt)
                        and not ALTERNATIVA_LETTER_RE.match(nxt)
                        and not QUESTAO_SEARCH_RE.search(nxt)
                        and not AREA_HEADER_RE.search(nxt)
                        and not nxt[0].isupper()):  # continuação começa minúscula
                    line = line.rstrip() + " " + nxt
                    j += 1
                else:
                    break
            merged.append(line)
            i = j
        else:
            merged.append(line)
            i += 1

    return merged


# ─────────────────────────────────────────────────────────────────────────────
# SEGMENTAÇÃO EM QUESTÕES
# ─────────────────────────────────────────────────────────────────────────────

def split_into_questions(lines: list[str]) -> list[tuple[int, list[str]]]:
    """
    Divide lista de linhas em blocos por questão.
    Retorna lista ordenada de (numero_questao, [linhas]).
    """
    questions: list[tuple[int, list[str]]] = []
    current_num: int | None = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        # Detecta início de questão: linha que É exclusivamente um header de questão
        m = QUESTAO_RE.match(stripped)
        if not m:
            # Tenta match mais amplo, mas exige que a linha comece com QUESTÃO
            m2 = QUESTAO_SEARCH_RE.match(stripped)
            if m2 and stripped.startswith(("QUESTÃO", "QUESTAO", "QUESTÃ")):
                m = m2

        if m:
            if current_num is not None:
                questions.append((current_num, current_lines))
            current_num = int(m.group(1))
            current_lines = []
        elif current_num is not None:
            current_lines.append(line)

    if current_num is not None and current_lines:
        questions.append((current_num, current_lines))

    questions.sort(key=lambda x: x[0])
    return questions


# ─────────────────────────────────────────────────────────────────────────────
# FORMATAÇÃO MARKDOWN POR QUESTÃO
# ─────────────────────────────────────────────────────────────────────────────

def is_reference_line(line: str) -> bool:
    """Heurística para identificar referências bibliográficas."""
    s = line.strip()
    if re.match(r"^[A-ZÁÀÃÉÊÍÓÕÚ]{2,}[,.]", s):
        return True
    if re.search(r"(Disponível em:|Acesso em:|São Paulo:|Rio de Janeiro:|\.?\s*In:\s|Apud:)", s):
        return True
    return False


def format_question_to_markdown(num: int, raw_lines: list[str]) -> str:
    """
    Converte as linhas brutas de uma questão em Markdown estruturado.
    """
    lines = merge_alternativas(raw_lines)

    md: list[str] = [f"## QUESTÃO {num:02d}", ""]

    paragraph: list[str] = []
    reference: list[str] = []
    in_alts = False

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            text = " ".join(paragraph).strip()
            if text:
                md.append(text)
                md.append("")
            paragraph = []

    def flush_reference():
        nonlocal reference
        if reference:
            ref = re.sub(r"\s+", " ", " ".join(reference).strip())
            md.append(f"> *{ref}*")
            md.append("")
            reference = []

    for line in lines:
        s = line.strip()
        if not s:
            continue

        # Sub-cabeçalho dentro de questão (TEXTO I, TEXTO II, QUADRO, etc.)
        if re.match(r"^(TEXTO\s+[IVX]+|QUADRO|TABELA|FIGURA|GRÁFICO)\s*$", s, re.IGNORECASE):
            flush_paragraph()
            flush_reference()
            md.append(f"**{s}**")
            md.append("")
            in_alts = False
            continue

        # Ignorar cabeçalhos de área dentro de bloco de questão
        if AREA_HEADER_RE.search(s) or QUESTOES_RANGE_RE.search(s):
            continue

        # Alternativa completa: "A texto..." ou "A  texto..."
        m = ALTERNATIVA_FULL_RE.match(s)
        if m:
            flush_paragraph()
            flush_reference()
            if not in_alts:
                in_alts = True
                if md and md[-1] != "":
                    md.append("")
            md.append(f"- **{m.group(1)}** {m.group(2).strip()}")
            continue

        # Referência bibliográfica
        if is_reference_line(s) and not in_alts:
            flush_paragraph()
            reference.append(s)
            continue

        # Linha de texto comum
        if reference:
            if is_reference_line(s) or re.match(r"^[a-záàãéêíóõú(]", s):
                reference.append(s)
                continue
            else:
                flush_reference()
                in_alts = False

        paragraph.append(s)

    flush_paragraph()
    flush_reference()

    # Remove linhas em branco consecutivas
    deduped: list[str] = []
    prev_blank = False
    for line in md:
        blank = (line == "")
        if blank and prev_blank:
            continue
        deduped.append(line)
        prev_blank = blank

    return "\n".join(deduped) + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# METADADOS E ÁREAS
# ─────────────────────────────────────────────────────────────────────────────

def extract_metadata(lines: list[str]) -> dict:
    meta = {"ano": "", "dia": "", "cor": "", "titulo": "EXAME NACIONAL DO ENSINO MÉDIO"}
    for line in lines[:60]:
        s = line.strip()
        if re.match(r"^(19|20)\d{2}$", s) and not meta["ano"]:
            meta["ano"] = s
        m_dia = re.search(r"\d[ºo°]\s*DIA", s, re.IGNORECASE)
        if m_dia and not meta["dia"]:
            meta["dia"] = m_dia.group(0)
        if "EXAME NACIONAL" in s.upper() and len(s) > 10 and not meta["titulo"]:
            meta["titulo"] = s
    for cor in ["AZUL", "AMARELO", "BRANCO", "ROSA", "CINZA", "VERDE", "LARANJA"]:
        if any(cor in l.upper() for l in lines[:12]):
            meta["cor"] = cor.capitalize()
            break
    return meta


def find_area_boundaries(all_lines: list[str]) -> list[tuple[str, int, int]]:
    """Localiza os índices de início/fim de cada área de conhecimento."""
    areas: list[tuple[str, int]] = []
    for i, line in enumerate(all_lines):
        if AREA_HEADER_RE.search(line.strip()):
            areas.append((line.strip(), i))

    if not areas:
        return [("Questões", 0, len(all_lines))]

    result = []
    for j, (name, start) in enumerate(areas):
        end = areas[j + 1][1] if j + 1 < len(areas) else len(all_lines)
        result.append((name, start, end))
    return result


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE PRINCIPAL
# ─────────────────────────────────────────────────────────────────────────────

def extract_exam(pdf_path: str, verbose: bool = False) -> str:
    """Pipeline completo: PDF → Markdown."""
    all_lines: list[str] = []

    print(f"📄 Lendo: {Path(pdf_path).name}")
    with pdfplumber.open(pdf_path) as pdf:
        n_pages = len(pdf.pages)
        print(f"   Páginas: {n_pages}")
        for page in pdf.pages:
            page_lines = extract_page_lines(page)
            all_lines.extend(clean_lines(page_lines))

    print(f"   Linhas úteis: {len(all_lines)}")

    if verbose:
        print("\n── LINHAS BRUTAS (primeiras 100) ──")
        for i, l in enumerate(all_lines[:100]):
            print(f"  [{i:03d}] {l}")
        print()

    meta = extract_metadata(all_lines)
    area_boundaries = find_area_boundaries(all_lines)
    all_questions = {num: lines for num, lines in split_into_questions(all_lines)}
    print(f"   Questões encontradas: {len(all_questions)}")

    # ── Monta o Markdown ──────────────────────────────────────────────────────
    parts: list[str] = []

    # Cabeçalho do documento
    parts.append(f"# {meta['titulo']}")
    parts.append("")
    items = []
    if meta["ano"]:
        items.append(f"**Ano:** {meta['ano']}")
    if meta["dia"]:
        items.append(f"**{meta['dia']}**")
    if meta["cor"]:
        items.append(f"**Caderno {meta['cor']}**")
    if items:
        parts.append(" | ".join(items))
        parts.append("")
    parts.append(f"*Fonte: `{Path(pdf_path).name}`*")
    parts.append("")
    parts.append("---")
    parts.append("")

    used: set[int] = set()

    for area_name, a_start, a_end in area_boundaries:
        area_lines = all_lines[a_start:a_end]
        area_qs = split_into_questions(area_lines)
        if not area_qs:
            continue

        parts.append(f"# {area_name}")
        parts.append("")

        range_line = next((l for l in area_lines[:6] if QUESTOES_RANGE_RE.search(l)), None)
        if range_line:
            parts.append(f"*{range_line.strip()}*")
            parts.append("")

        parts.append("---")
        parts.append("")

        for num, q_lines in area_qs:
            parts.append(format_question_to_markdown(num, q_lines))
            used.add(num)

    # Questões órfãs (não cobertas por nenhuma área)
    orphans = sorted(set(all_questions.keys()) - used)
    if orphans:
        parts.append("# Questões")
        parts.append("")
        parts.append("---")
        parts.append("")
        for num in orphans:
            parts.append(format_question_to_markdown(num, all_questions[num]))

    return "\n".join(parts)


# ─────────────────────────────────────────────────────────────────────────────
# PONTO DE ENTRADA
# ─────────────────────────────────────────────────────────────────────────────

def main():
    # ─── Configure aqui os caminhos ───────────────────────────────────────────
    PDF_PATH = "./provas/2013/Caderno1_Azul_Sab.pdf"   # caminho para o PDF a ser processado
    OUTPUT_PATH = "./output/"                    # None = mesmo nome do PDF com extensão .md
                                          # ou defina: "saida.md"
    VERBOSE = False                       # True = exibe linhas brutas extraídas
    # ──────────────────────────────────────────────────────────────────────────

    pdf_path = Path(PDF_PATH)
    if not pdf_path.exists():
        print(f"❌ Arquivo não encontrado: {pdf_path}")
        sys.exit(1)

    output_path = Path(OUTPUT_PATH) if OUTPUT_PATH else pdf_path.with_suffix(".md")

    try:
        markdown = extract_exam(str(pdf_path), verbose=VERBOSE)
    except Exception as e:
        print(f"❌ Erro durante extração: {e}")
        raise

    output_path.write_text(markdown, encoding="utf-8")
    print(f"\n✅ Arquivo salvo: {output_path}")
    print(f"   {len(markdown):,} caracteres  |  {markdown.count(chr(10)):,} linhas")


if __name__ == "__main__":
    main()