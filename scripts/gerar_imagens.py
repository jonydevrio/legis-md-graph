#!/usr/bin/env python3
"""Gera as evidências visuais do projeto com Pillow (sem matplotlib).

Saída em docs/:
  modelo_grafo.png     esquema de labels, propriedades e relações
  normas_por_decada.png  volume legislativo por década
  top_revogadoras.png    normas que mais revogaram outras
"""
import os

from neo4j import GraphDatabase
from PIL import Image, ImageDraw, ImageFont

AQUI = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(AQUI, '..', 'docs')
PRETO = (24, 24, 27)
CINZA = (110, 110, 118)
AZUL = (37, 99, 235)
VERDE = (16, 122, 87)
VERM = (185, 28, 28)
ROXO = (109, 40, 217)
FUNDO = (255, 255, 255)


def fonte(tam, negrito=False):
    caminhos = [
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf' if negrito
        else '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
    ]
    for c in caminhos:
        if os.path.exists(c):
            return ImageFont.truetype(c, tam)
    return ImageFont.load_default()


def caixa(d, x, y, larg, alt, titulo, linhas, cor, f_t, f_c):
    d.rounded_rectangle([x, y, x + larg, y + alt], 10, fill=FUNDO, outline=cor, width=3)
    d.rectangle([x, y, x + larg, y + 34], fill=cor)
    d.text((x + 12, y + 9), titulo, font=f_t, fill=FUNDO)
    yy = y + 44
    for ln in linhas:
        d.text((x + 14, yy), ln, font=f_c, fill=PRETO)
        yy += 20


def seta(d, p1, p2, cor, rotulo, f):
    d.line([p1, p2], fill=cor, width=3)
    # ponta
    x1, y1 = p1
    x2, y2 = p2
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    tam = 12
    for s in (0.4, -0.4):
        d.line([(x2, y2), (x2 - tam * math.cos(ang - s), y2 - tam * math.sin(ang - s))],
               fill=cor, width=3)
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    tb = d.textbbox((0, 0), rotulo, font=f)
    d.rectangle([mx - (tb[2] - tb[0]) / 2 - 4, my - 20, mx + (tb[2] - tb[0]) / 2 + 4, my - 2], fill=FUNDO)
    d.text((mx - (tb[2] - tb[0]) / 2, my - 18), rotulo, font=f, fill=cor)


def modelo(imagem_path):
    W, H = 1100, 760
    img = Image.new('RGB', (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    f_t = fonte(15, True)
    f_c = fonte(13)
    f_r = fonte(12, True)
    f_b = fonte(20, True)

    d.text((30, 22), 'Modelo do grafo — Legislação Brasileira', font=f_b, fill=PRETO)
    d.text((30, 50), 'Label único :Norma + propriedade tipo, relações nomeadas pelo efeito jurídico',
           font=f_c, fill=CINZA)

    caixa(d, 40, 100, 330, 300, ':Norma', [
        'id           "federal:BR:L:10406/2002"',
        'titulo       "Lei nº 10.406 de 10/01/2002"',
        'tipo         "Lei Ordinária"',
        'numero       "10406"',
        'ano          2002  (int)',
        'esfera       "federal"',
        'uf           null  (só estadual/municipal)',
        'ementa       "Institui o Código Civil."',
        'situacao     "Não consta revogação..."',
        'vigente      true',
        'versao_texto "compilada (vigente)"',
        'urn / fonte / arquivo',
    ], AZUL, f_t, f_c)

    caixa(d, 720, 100, 340, 190, 'Constraint e índices', [
        'UNIQUE  (:Norma).id',
        'INDEX   :Norma(tipo)',
        'INDEX   :Norma(ano)',
        'INDEX   :Norma(esfera)',
        'INDEX   :Norma(numero)',
        '',
        'A carga é idempotente: MERGE por id',
    ], CINZA, f_t, f_c)

    # relações à volta do nó central
    
    alvos = [
        (60, 520, 'REVOGA', VERM, 'revogou'),
        (330, 520, 'ALTERA', ROXO, 'deu nova redação'),
        (60, 570, 'INCLUI', VERDE, 'incluiu dispositivo'),
        (330, 570, 'REFERENCIA', AZUL, 'remissão "Vide"'),
    ]
    for x, y, nome, cor, desc in alvos:
        d.rounded_rectangle([x, y - 16, x + 210, y + 8], 6, fill=cor)
        d.text((x + 10, y - 13), nome, font=f_r, fill=FUNDO)
        d.text((x + 10, y + 12), desc, font=f_c, fill=CINZA)

    d.text((620, 340), 'Todas as relações carregam', font=f_c, fill=PRETO)
    d.text((620, 360), 'a propriedade trecho, com o texto', font=f_c, fill=PRETO)
    d.text((620, 380), 'que originou a aresta — auditoria.', font=f_c, fill=PRETO)
    d.text((620, 420), 'Direção: quem produz o efeito →', font=f_c, fill=AZUL)
    d.text((620, 440), 'quem o recebe.', font=f_c, fill=AZUL)

    d.text((620, 500), 'Grafo carregado neste projeto:', font=f_t, fill=PRETO)
    d.text((620, 522), '16.321 nós :Norma', font=f_c, fill=PRETO)
    d.text((620, 542), '3.974 relações', font=f_c, fill=PRETO)
    d.text((620, 562), 'fonte: acervo legis-md (federal)', font=f_c, fill=CINZA)

    img.save(imagem_path)
    print('->', imagem_path)


def barra(d, x, y, larg, alt, rotulo, valor, maximo, cor, f, fv):
    h = int(alt * valor / maximo) if maximo else 0
    d.rectangle([x, y + alt - h, x + larg, y + alt], fill=cor)
    d.text((x, y + alt + 4), rotulo, font=f, fill=CINZA)
    d.text((x, y + alt - h - 16), str(valor), font=fv, fill=PRETO)


def grafico_decadas(sessao, caminho):
    dados = sessao.run("""
        MATCH (n:Norma) WHERE n.ano IS NOT NULL AND n.ano >= 1820
        RETURN (n.ano/10)*10 AS decada, count(*) AS total
        ORDER BY decada
    """).data()
    W, H = 1100, 460
    img = Image.new('RGB', (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    f_b = fonte(19, True)
    f = fonte(10)
    fv = fonte(9)
    d.text((30, 20), 'Normas vigentes por década', font=f_b, fill=PRETO)
    d.text((30, 46), 'Base: acervo federal vigente — mostra a explosão legislativa do século XX',
           font=fonte(12), fill=CINZA)
    maximo = max(r['total'] for r in dados) if dados else 1
    base_y, alt = 370, 270
    larg = max(6, int(1020 / max(1, len(dados))) - 3)
    for i, r in enumerate(dados):
        x = 40 + i * (larg + 3)
        cor = AZUL if r['decada'] < 1980 else (ROXO if r['decada'] < 2000 else VERDE)
        barra(d, x, base_y - alt, larg, alt, str(r['decada'])[2:] + 's', r['total'], maximo, cor, f, fv)
    d.line([35, base_y, 1075, base_y], fill=CINZA, width=2)
    img.save(caminho)
    print('->', caminho)


def grafico_revogadoras(sessao, caminho):
    dados = sessao.run("""
        MATCH (n:Norma)-[r:REVOGA]->()
        RETURN n.titulo AS titulo, count(r) AS total
        ORDER BY total DESC LIMIT 10
    """).data()
    W, H = 1100, 460
    img = Image.new('RGB', (W, H), FUNDO)
    d = ImageDraw.Draw(img)
    f_b = fonte(19, True)
    d.text((30, 20), 'Normas que mais revogaram outras', font=f_b, fill=PRETO)
    d.text((30, 46), 'Relação :REVOGA — quem mais retirou normas do ordenamento',
           font=fonte(12), fill=CINZA)
    maximo = max(r['total'] for r in dados) if dados else 1
    y = 80
    for i, r in enumerate(dados):
        largura = int(700 * r['total'] / maximo)
        d.rectangle([420, y, 420 + largura, y + 24], fill=VERDE)
        d.text((30, y + 4), r['titulo'][:52], font=fonte(12), fill=PRETO)
        d.text((430 + largura, y + 4), str(r['total']), font=fonte(12, True), fill=PRETO)
        y += 34
    img.save(caminho)
    print('->', caminho)


def main():
    os.makedirs(DOCS, exist_ok=True)
    modelo(os.path.join(DOCS, 'modelo_grafo.png'))
    d = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'legis-graph'))
    with d.session() as s:
        grafico_decadas(s, os.path.join(DOCS, 'normas_por_decada.png'))
        grafico_revogadoras(s, os.path.join(DOCS, 'top_revogadoras.png'))
    d.close()


if __name__ == '__main__':
    main()
