#!/usr/bin/env python3
"""
Extrai normas e correlações dos arquivos Markdown do acervo legis-md.

Gera dois CSVs prontos para LOAD CSV no Neo4j:
  normas.csv        -- uma linha por norma
  correlacoes.csv   -- uma linha por relação entre normas

Uso:
  python3 extract.py <diretorio-do-acervo> <diretorio-de-saida> [--completo]

Sem --completo, processa apenas normas vigentes (situacao != revogada).
"""
import csv
import os
import re
import sys
from datetime import date

# ---------------------------------------------------------------------------
# Frontmatter YAML mínimo (sem dependência externa)
# ---------------------------------------------------------------------------

CAMPO_RE = re.compile(r'^([a-z_][a-z0-9_]*):\s*(.*)$')


def ler_frontmatter(caminho):
    """Lê o bloco --- ... --- do topo do arquivo e devolve dict + tamanho do corpo."""
    meta = {}
    corpo_linhas = []
    with open(caminho, encoding='utf-8', errors='replace') as f:
        linhas = f.readlines()

    if not linhas or linhas[0].strip() != '---':
        return meta, ''.join(linhas)

    fim = None
    for i, linha in enumerate(linhas[1:], start=1):
        if linha.strip() == '---':
            fim = i
            break
        m = CAMPO_RE.match(linha.rstrip('\n'))
        if m:
            chave, valor = m.group(1), m.group(2).strip()
            if valor.startswith('"') and valor.endswith('"') and len(valor) >= 2:
                valor = valor[1:-1].replace('\\"', '"')
            elif valor in ('null', '~', ''):
                valor = None
            meta[chave] = valor

    if fim is None:
        return meta, ''.join(linhas)
    return meta, ''.join(linhas[fim + 1:])


# ---------------------------------------------------------------------------
# Normalização de tipo e identificação da norma
# ---------------------------------------------------------------------------

# tipo canônico do acervo -> (label do nó, sigla curta)
TIPO_PARA_LABEL = {
    'Lei Ordinária': ('Lei', 'L'),
    'Lei Complementar': ('LeiComplementar', 'LC'),
    'Lei Delegada': ('LeiDelegada', 'LD'),
    'Decreto-Lei': ('DecretoLei', 'DL'),
    'Decreto': ('Decreto', 'D'),
    'Decreto Legislativo': ('DecretoLegislativo', 'DLG'),
    'Medida Provisória': ('MedidaProvisoria', 'MP'),
    'Emenda Constitucional': ('EmendaConstitucional', 'EC'),
    'Resolução': ('Resolucao', 'R'),
    'Constituição Estadual': ('ConstituicaoEstadual', 'CE'),
}


def label_de_tipo(tipo):
    if not tipo:
        return ('Norma', 'N')
    t = tipo.strip()
    if t in TIPO_PARA_LABEL:
        return TIPO_PARA_LABEL[t]
    # tenta casar sem acento/caixa
    alvo = _sem_acento(t).lower()
    for chave, valor in TIPO_PARA_LABEL.items():
        if _sem_acento(chave).lower() == alvo:
            return valor
    return ('Norma', 'N')


def _sem_acento(texto):
    tabela = str.maketrans(
        'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
        'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC',
    )
    return texto.translate(tabela)


def normalizar_numero(numero):
    if not numero:
        return ''
    return re.sub(r'[^0-9]', '', str(numero))


def chave_norma(esfera, uf, tipo_sigla, numero, ano):
    """Identificador estável usado nas relações."""
    if not numero:
        return None
    return f'{esfera}:{uf or "BR"}:{tipo_sigla}:{numero}/{ano or "sd"}'


# ---------------------------------------------------------------------------
# Extração de correlações no corpo do texto
# ---------------------------------------------------------------------------

# Padrões observados no acervo (Planalto / normas.leg.br):
#   *(Revogado pela Lei nº 13.146, de 6/7/2015, ...)*
#   *(Redação dada pela Lei nº 13.874, de 2019)*
#   *(Incluído pela Lei nº 13.777, de 2019)*
#   *(Vide Lei nº 15.040, de 9/12/2024)*
#   *(Vigência ...)*
#
# PRECISÃO: o marcador precisa estar *imediatamente antes* da citação, como em
# "Revogado pela Lei nº 13.146". Se olhássemos a linha inteira, uma linha como
# "b) associação ... nos termos dos arts. 53 a 61 da Lei nº 10.406" seria lida
# como "esta lei altera o Código Civil", o que é falso: ela apenas o invoca.
# Por isso o padrão abaixo amarra marcador + citação.
TIPO_NO_TEXTO = (
    r'(Lei Complementar|Lei Delegada|Lei Ordinária|Lei|Decreto-Lei|Decreto|'
    r'Medida Provisória|Emenda Constitucional|Resolução|Portaria|Instrução Normativa)'
)
CITACAO = (
    r'\s*(?:n[ºo°]\.?|n\.|nº)?\s*([\d][\d\.]{0,15})'
    r'(?:\s*,?\s*(?:de\s*)?(\d{4}))?'
)

MARCADORES = {
    'REVOGA': r'Revogad[oa]s?\s+p(?:el|or)a',
    'ALTERA': r'(?:Reda[çc][ãa]o\s+dada|Alterad[oa]s?)\s+p(?:el|or)a',
    'INCLUI': r'Inclu[íi]d[oa]s?\s+p(?:el|or)a',
    'REFERENCIA': r'\bVide\b',
}

# marcador seguido, de perto, por uma citação
PADROES_PROXIMOS = [
    (nome, re.compile(padrao + r'\s*' + TIPO_NO_TEXTO + CITACAO, re.I))
    for nome, padrao in MARCADORES.items()
]


def extrair_correlacoes(corpo):
    """Devolve lista de (tipo_relacao, tipo_norma, numero, ano, trecho).

    Só conta citação que vem colada ao marcador — ver comentário acima.
    """
    achados = []
    for linha in corpo.split('\n'):
        baixa = linha.lower()
        if not any(p in baixa for p in ('revogad', 'vide', 'redaç', 'redac',
                                        'alterad', 'incluí', 'inclui')):
            continue
        for relacao, padrao in PADROES_PROXIMOS:
            for m in padrao.finditer(linha):
                tipo_txt, numero, ano = m.group(1), m.group(2), m.group(3)
                numero_norm = normalizar_numero(numero)
                if not numero_norm or len(numero_norm) > 8:
                    continue
                if not ano:
                    # o ano costuma vir depois, separado por vírgula
                    cauda = linha[m.end():m.end() + 90]
                    m2 = re.search(r'\b(1[89]\d\d|20\d\d)\b', cauda)
                    if not m2:
                        m2 = re.search(r'\b(1[89]\d\d|20\d\d)\b', linha)
                    ano = m2.group(1) if m2 else None
                # O trecho precisa CONTER o marcador que justifica a aresta.
                # Cortar a linha do início deixava de fora justamente o
                # "*(Redação dada pela Lei nº ...)*" quando ele vem no fim
                # de um dispositivo longo. Guardamos uma janela em torno do
                # marcador: contexto anterior (o dispositivo) + a citação.
                ini = max(0, m.start() - 90)
                fim = min(len(linha), m.end() + 80)
                trecho = linha[ini:fim].strip()
                if ini > 0:
                    trecho = '…' + trecho
                if fim < len(linha):
                    trecho = trecho + '…'
                achados.append((relacao, tipo_txt, numero_norm, ano, trecho))
    # dedup preservando ordem
    vistos = set()
    saida = []
    for a in achados:
        k = (a[0], a[1], a[2], a[3])
        if k in vistos:
            continue
        vistos.add(k)
        saida.append(a)
    return saida


# ---------------------------------------------------------------------------
# Coleta de arquivos
# ---------------------------------------------------------------------------

PASTAS_TIPO = {
    'leis-ordinarias': 'Lei Ordinária',
    'leis-complementares': 'Lei Complementar',
    'leis-delegadas': 'Lei Delegada',
    'decretos-lei': 'Decreto-Lei',
    'decretos': 'Decreto',
    'decretos-legislativos': 'Decreto Legislativo',
    'medidas-provisorias': 'Medida Provisória',
    'emendas-constitucionais': 'Emenda Constitucional',
    'resolucoes-senado': 'Resolução',
    'resolucoes-camara': 'Resolução',
    'constituicao': 'Constituição Estadual',
}


def tipo_por_caminho(rel):
    """Descobre o tipo pela pasta, quando o frontmatter não traz."""
    partes = rel.split(os.sep)
    for parte in reversed(partes):
        if parte in PASTAS_TIPO:
            return PASTAS_TIPO[parte]
    return None


def esfera_por_caminho(rel):
    partes = rel.split(os.sep)
    if partes[0] == 'federal':
        return 'federal', None
    if partes[0] == 'estaduais' and len(partes) > 1:
        return 'estadual', partes[1]
    if partes[0] == 'municipais' and len(partes) > 1:
        return 'municipal', partes[1]
    if partes[0] == 'reguladores':
        return 'regulador', None
    if partes[0] == 'jurisprudencia':
        return 'jurisprudencia', None
    if partes[0] == 'tratados':
        return 'tratado', None
    return 'outra', None


def esta_vigente(meta, corpo):
    """Decide se a norma entra como vigente.

    Regra do acervo: `revogada` é o campo dedicado, mas aparece como null na
    maioria. Tratamos como NÃO vigente apenas quando afirma true, ou quando
    `situacao` declara revogação. Os demais casos ficam vigentes=True, com a
    confiança registrada em `vigencia_origem`.
    """
    revogada = (meta.get('revogada') or '').strip().lower()
    situacao = (meta.get('situacao') or '').strip()

    if revogada == 'true':
        return False, 'revogada=true'
    if situacao:
        s = _sem_acento(situacao).lower()
        if 'revogad' in s and 'nao consta' not in s:
            return False, f'situacao:{situacao}'
        return True, f'situacao:{situacao}'
    if revogada == 'false':
        return True, 'revogada=false'
    return True, 'sem_informacao'


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    raiz = sys.argv[1]
    saida = sys.argv[2]
    completo = '--completo' in sys.argv
    limite = None
    for a in sys.argv[3:]:
        if a.startswith('--limite='):
            limite = int(a.split('=', 1)[1])

    os.makedirs(saida, exist_ok=True)
    normas_path = os.path.join(saida, 'normas.csv')
    corr_path = os.path.join(saida, 'correlacoes.csv')

    total = 0
    vigentes = 0
    sem_numero = 0
    correlacoes = 0
    por_esfera = {}

    with open(normas_path, 'w', newline='', encoding='utf-8') as fn, \
            open(corr_path, 'w', newline='', encoding='utf-8') as fc:
        wn = csv.writer(fn)
        wc = csv.writer(fc)
        wn.writerow([
            'norma_id', 'label', 'titulo', 'tipo', 'numero', 'ano', 'data',
            'esfera', 'uf', 'ementa', 'situacao', 'vigente', 'vigencia_origem',
            'versao_texto', 'urn', 'fonte', 'arquivo', 'revogada_por_txt',
        ])
        # Semântica explícita: `contem_id` é a norma cujo texto traz a
        # anotação; `citada_*` é a norma nomeada na anotação. A DIREÇÃO da
        # aresta depende do tipo (ver scripts/load.py e load_csv.cypher):
        #   REVOGA/ALTERA/INCLUI -> citada -[efeito]-> contem
        #   REFERENCIA           -> contem -[cita]->    citada
        wc.writerow(['contem_id', 'citada_tipo', 'citada_numero',
                     'citada_ano', 'tipo_relacao', 'trecho'])

        for dirpath, _dirnames, filenames in os.walk(raiz):
            if '.git' in dirpath:
                continue
            for nome_arq in filenames:
                if not nome_arq.endswith('.md'):
                    continue
                caminho = os.path.join(dirpath, nome_arq)
                rel = os.path.relpath(caminho, raiz)
                meta, corpo = ler_frontmatter(caminho)

                tipo = meta.get('tipo') or tipo_por_caminho(rel)
                if not tipo:
                    continue
                esfera, uf = esfera_por_caminho(rel)
                label, sigla = label_de_tipo(tipo)
                numero = normalizar_numero(meta.get('numero'))
                data_txt = meta.get('data') or ''
                ano = (data_txt[:4] if data_txt[:4].isdigit()
                       else (meta.get('ano') or ''))

                vigente, origem_vig = esta_vigente(meta, corpo)
                if not completo and not vigente:
                    continue

                norma_id = chave_norma(esfera, uf, sigla, numero, ano)
                if norma_id is None:
                    sem_numero += 1
                    norma_id = f'{esfera}:{uf or "BR"}:{sigla}:s/n/{ano or "sd"}:{total}'

                wn.writerow([
                    norma_id, label, meta.get('titulo') or '', tipo,
                    numero, ano, data_txt, esfera, uf or '',
                    (meta.get('ementa') or '')[:500],
                    meta.get('situacao') or '', 'true' if vigente else 'false',
                    origem_vig, meta.get('versao_texto') or '',
                    meta.get('urn') or '', meta.get('fonte') or '', rel, '',
                ])
                total += 1
                if vigente:
                    vigentes += 1
                por_esfera[esfera] = por_esfera.get(esfera, 0) + 1

                for relacao, tipo_txt, num_dest, ano_dest, trecho in extrair_correlacoes(corpo):
                    # DIREÇÃO DO EFEITO — resolvida no loader, a partir destes
                    # campos neutros:
                    #   "*(Revogado pela Lei nº 9.120/1995)*" dentro da Lei
                    #   3.820/1960  ->  (9120)-[:REVOGA]->(3820)
                    # e não o contrário. Já "*(Vide Lei nº 8.130/1990)*"
                    # dentro da Lei 3.792/1960  ->  (3792)-[:REFERENCIA]->(8130),
                    # porque quem referencia é a norma que traz o "Vide".
                    wc.writerow([norma_id, tipo_txt, num_dest,
                                 ano_dest or '', relacao, trecho])
                    correlacoes += 1

                if limite and total >= limite:
                    break
            if limite and total >= limite:
                break

    print(f'normas gravadas: {total} (vigentes: {vigentes})')
    print(f'sem número no frontmatter: {sem_numero}')
    print(f'correlações: {correlacoes}')
    print('por esfera:', por_esfera)
    print(f'-> {normas_path}')
    print(f'-> {corr_path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
