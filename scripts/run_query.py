#!/usr/bin/env python3
"""Roda as queries de negócio e imprime tabelas em texto (para virar print/README)."""
import os
import re
import sys

from neo4j import GraphDatabase

AQUI = os.path.dirname(os.path.abspath(__file__))
ARQ = os.path.join(AQUI, '..', 'cypher', 'queries_negocio.cypher')
URI = os.environ.get('NEO4J_URI', 'bolt://localhost:7687')
USER = os.environ.get('NEO4J_USER', 'neo4j')
PWD = os.environ.get('NEO4J_PASSWORD', 'legis-graph')


def blocos(caminho):
    """Divide o arquivo .cypher em (titulo, cypher) por comentário de seção."""
    texto = open(caminho, encoding='utf-8').read()
    partes = re.split(r'\n// -+\n// (Q\d+\.[^\n]+)\n', texto)
    saida = []
    for i in range(1, len(partes), 2):
        titulo = partes[i].strip()
        corpo = partes[i + 1]
        # remove comentários de linha e pega só o primeiro statement
        linhas = [l for l in corpo.split('\n')
                  if not l.strip().startswith('//') and l.strip()]
        consulta = '\n'.join(linhas).strip()
        saida.append((titulo, consulta))
    return saida


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    driver = GraphDatabase.driver(URI, auth=(USER, PWD))
    with driver.session() as s:
        for titulo, consulta in blocos(ARQ):
            print('=' * 78)
            print(titulo)
            print('=' * 78)
            try:
                res = s.run(consulta)
                registros = res.data()
                if not registros:
                    print('  (sem resultados)')
                else:
                    cols = list(registros[0].keys())
                    larg = {c: max(len(str(c)), *(len(str(r[c])) for r in registros)) for c in cols}
                    print(' | '.join(str(c).ljust(larg[c]) for c in cols))
                    print('-+-'.join('-' * larg[c] for c in cols))
                    for r in registros[:limite]:
                        print(' | '.join(str(r[c]).ljust(larg[c]) for c in cols))
            except Exception as e:
                print('  erro:', str(e)[:150])
            print()
    driver.close()


if __name__ == '__main__':
    main()
