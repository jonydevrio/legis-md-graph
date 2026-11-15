#!/usr/bin/env python3
"""
Carrega normas.csv e correlacoes.csv no Neo4j e cria o schema.

Uso:
  python3 load.py [--uri bolt://localhost:7687] [--user neo4j] [--pass senha]

Os CSVs precisam estar em ./data (normas.csv, correlacoes.csv).
"""
import argparse
import csv
import os
import sys
import time

from neo4j import GraphDatabase

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA_DADOS = os.path.join(AQUI, '..', 'data')

SCHEMA = [
    'CREATE CONSTRAINT norma_id IF NOT EXISTS FOR (n:Norma) REQUIRE n.id IS UNIQUE',
    "CREATE INDEX norma_tipo IF NOT EXISTS FOR (n:Norma) ON (n.tipo)",
    "CREATE INDEX norma_ano IF NOT EXISTS FOR (n:Norma) ON (n.ano)",
    "CREATE INDEX norma_uf IF NOT EXISTS FOR (n:Norma) ON (n.uf)",
    "CREATE INDEX norma_esfera IF NOT EXISTS FOR (n:Norma) ON (n.esfera)",
]


def carregar_normas(sessao, caminho, lote=2000):
    consulta = """
    UNWIND $linhas AS l
    MERGE (n:Norma {id: l.norma_id})
    SET n.titulo      = l.titulo,
        n.tipo        = l.tipo,
        n.numero      = l.numero,
        n.ano         = toInteger(l.ano),
        n.data        = l.data,
        n.esfera      = l.esfera,
        n.uf          = CASE WHEN l.uf = '' THEN null ELSE l.uf END,
        n.ementa      = l.ementa,
        n.situacao    = CASE WHEN l.situacao = '' THEN null ELSE l.situacao END,
        n.vigente     = (l.vigente = 'true'),
        n.vigencia_origem = l.vigencia_origem,
        n.versao_texto = l.versao_texto,
        n.urn         = CASE WHEN l.urn = '' THEN null ELSE l.urn END,
        n.fonte       = CASE WHEN l.fonte = '' THEN null ELSE l.fonte END,
        n.arquivo     = l.arquivo
    WITH n, l
    CALL apoc.create.addLabels(n, [l.label]) YIELD node
    RETURN count(node) AS total
    """
    total = 0
    lote_atual = []
    with open(caminho, encoding='utf-8') as f:
        for linha in csv.DictReader(f):
            lote_atual.append(linha)
            if len(lote_atual) >= lote:
                r = sessao.run(consulta, linhas=lote_atual).single()
                total += r['total'] if r else 0
                lote_atual = []
                print(f'  {total} normas', end='\r')
    if lote_atual:
        r = sessao.run(consulta, linhas=lote_atual).single()
        total += r['total'] if r else 0
    print(f'  {total} normas carregadas        ')
    return total


def carregar_correlacoes(sessao, caminho, lote=2000):
    """Cria as relações só quando a norma de destino existe no grafo."""
    consulta = """
    UNWIND $linhas AS l
    MATCH (o:Norma {id: l.origem_id})
    MATCH (d:Norma)
      WHERE d.numero = l.destino_numero
        AND d.esfera = o.esfera
        AND (d.uf = o.uf OR (d.uf IS NULL AND o.uf IS NULL))
        AND (l.destino_ano = '' OR toString(d.ano) = l.destino_ano)
    WITH o, d, l
    WHERE o <> d
    CALL apoc.merge.relationship(o, l.tipo_relacao, {}, {}, d) YIELD rel
    SET rel.trecho = l.trecho
    RETURN count(rel) AS total
    """
    total = 0
    pendentes = 0
    lote_atual = []
    linhas = list(csv.DictReader(open(caminho, encoding='utf-8')))
    print(f'  {len(linhas)} correlações a processar')
    for linha in linhas:
        lote_atual.append(linha)
        if len(lote_atual) >= lote:
            r = sessao.run(consulta, linhas=lote_atual).single()
            n = r['total'] if r else 0
            total += n
            pendentes += len(lote_atual) - n
            lote_atual = []
            print(f'  {total} relações criadas', end='\r')
    if lote_atual:
        r = sessao.run(consulta, linhas=lote_atual).single()
        n = r['total'] if r else 0
        total += n
        pendentes += len(lote_atual) - n
    print(f'  {total} relações criadas ({pendentes} sem destino no grafo)')
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--uri', default='bolt://localhost:7687')
    ap.add_argument('--user', default='neo4j')
    ap.add_argument('--pass', dest='senha', default='legis-graph')
    args = ap.parse_args()

    driver = GraphDatabase.driver(args.uri, auth=(args.user, args.senha))
    inicio = time.time()
    with driver.session(database='neo4j') as sessao:
        print('Criando schema...')
        for c in SCHEMA:
            try:
                sessao.run(c).consume()
            except Exception as e:
                print('  aviso:', str(e)[:90])

        print('Carregando normas...')
        carregar_normas(sessao, os.path.join(PASTA_DADOS, 'normas.csv'))

        print('Carregando correlações...')
        carregar_correlacoes(sessao, os.path.join(PASTA_DADOS, 'correlacoes.csv'))

        print('Contagens finais:')
        r = sessao.run('MATCH (n:Norma) RETURN count(n) AS nos').single()
        print(f"  nós Norma: {r['nos']}")
        r = sessao.run('MATCH ()-[r]->() RETURN count(r) AS rels').single()
        print(f"  relações: {r['rels']}")
    driver.close()
    print(f'tempo: {time.time() - inicio:.1f}s')
    return 0


if __name__ == '__main__':
    sys.exit(main())
