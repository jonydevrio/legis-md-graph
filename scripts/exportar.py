#!/usr/bin/env python3
"""
Gera os arquivos de exportação do grafo, para versionar ou distribuir.

Produz dois arquivos:
  export/legis-graph.cypher       grafo completo em Cypher (qualquer versão)
  export/legis-graph-neo4j5.dump  dump binário nativo (exige Neo4j 5.x)

Uso:
  python3 exportar.py --uri bolt://localhost:7687 --user neo4j --pass SENHA

Observação: o dump binário exige que o Neo4j esteja PARADO. O script avisa e
oferece os comandos, mas não para o servidor por você.
"""
import argparse
import os
import subprocess
import sys

from neo4j import GraphDatabase

AQUI = os.path.dirname(os.path.abspath(__file__))
EXPORT = os.path.join(AQUI, '..', 'export')


def gerar_cypher(uri, user, senha):
    """Exporta o grafo inteiro em Cypher via APOC."""
    os.makedirs(EXPORT, exist_ok=True)
    driver = GraphDatabase.driver(uri, auth=(user, senha))
    try:
        with driver.session() as s:
            r = s.run("""
                CALL apoc.export.cypher.all('legis-graph.cypher', {
                  format: 'cypher-shell',
                  useOptimizations: {type: 'UNWIND_BATCH', unwindBatchSize: 500},
                  batchSize: 1000
                })
                YIELD file, nodes, relationships, time
                RETURN file, nodes, relationships, time
            """).single()
            print(f"  nós: {r['nodes']}  relações: {r['relationships']}  "
                  f"tempo: {r['time']} ms")
    finally:
        driver.close()

    # o APOC grava sempre em <NEO4J_HOME>/import/
    origem = os.environ.get('NEO4J_IMPORT', 'import/legis-graph.cypher')
    if os.path.exists(origem):
        destino = os.path.join(EXPORT, 'legis-graph.cypher')
        os.replace(origem, destino)
        print(f'  -> {destino} ({os.path.getsize(destino) / 1e6:.1f} MB)')
    else:
        print(f'  aviso: não encontrei {origem}. O APOC grava em <NEO4J_HOME>/import/.\n'
              f'         Ajuste NEO4J_IMPORT ou mova o arquivo manualmente para export/.')


def instrucoes_dump():
    print()
    print('Para gerar o dump binário (exige Neo4j parado):')
    print()
    print('  neo4j stop')
    print('  neo4j-admin database dump neo4j --to-path=/caminho/export')
    print('  mv /caminho/export/neo4j.dump /caminho/export/legis-graph-neo4j5.dump')
    print('  neo4j start')
    print()
    print('O nome tem de voltar a ser neo4j.dump antes de restaurar — está')
    print('explicado em docs/IMPORTAR.md.')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--uri', default='bolt://localhost:7687')
    ap.add_argument('--user', default='neo4j')
    ap.add_argument('--pass', dest='senha', required=True)
    args = ap.parse_args()

    print('Exportando grafo para Cypher...')
    try:
        gerar_cypher(args.uri, args.user, args.senha)
    except Exception as e:
        print('  erro:', str(e)[:200])
        if 'apoc' in str(e).lower():
            print('  dica: instale o APOC e habilite apoc.export.file.enabled=true')
        return 1

    instrucoes_dump()
    return 0


if __name__ == '__main__':
    sys.exit(main())
