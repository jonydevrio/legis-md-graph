# Como abrir este grafo no seu próprio Neo4j

Existem três caminhos. Escolha pelo que você tem em mãos:

| Você tem | Use | Tempo |
| --- | --- | --- |
| Neo4j Desktop ou Aura, sem saber a versão | **Caminho A** — arquivo `.cypher` | 2 min |
| Neo4j 5.x instalado (Docker, servidor, Desktop) | **Caminho B** — dump binário | 1 min |
| Nada instalado, quer só explorar | **Caminho C** — Neo4j Aura Free | 10 min |

O caminho A funciona em **qualquer versão** do Neo4j, inclusive 4.x. É o mais seguro se
você não sabe a versão do seu servidor.

---

## Caminho A — Importar o `.cypher` (funciona em qualquer versão)

O arquivo `export/legis-graph.cypher` contém **tudo**: o schema (constraints e índices), os
16.321 nós e as 3.974 relações, já em lotes com `UNWIND`.

### Pelo Neo4j Browser (o mais simples)

1. Abra o Neo4j Browser do seu banco (`http://localhost:7474`).
2. Arraste o arquivo `legis-graph.cypher` para dentro da janela do editor de comandos.
3. O Browser carrega o conteúdo. Clique em **Run**.
4. Vai reclamar do tamanho e perguntar se quer executar mesmo assim. Confirme.

Se o navegador travar por causa do tamanho, divida o arquivo:

```bash
# divide em partes de 100 mil linhas
split -l 100000 export/legis-graph.cypher parte_
# rode parte_aa, parte_ab, ... em ordem
```

### Pelo cypher-shell (mais confiável)

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p SUA_SENHA -f export/legis-graph.cypher
```

É o modo mais rápido e não depende do navegador. Roda em cerca de 30 segundos.

### Docker, se preferir

```bash
docker run --rm -it \
  -v "$PWD/export:/import" \
  neo4j:5.26 cypher-shell \
  -a bolt://SEU_HOST:7687 -u neo4j -p SUA_SENHA \
  -f /import/legis-graph.cypher
```

### Conferindo

```cypher
MATCH (n:Norma) RETURN count(n) AS normas;   // esperado: 16321
MATCH ()-[r]->() RETURN count(r) AS relacoes; // esperado: 3974
```

> **Aviso:** o arquivo `.cypher` usa `CREATE`, não `MERGE`. Se você rodar duas vezes no
> mesmo banco, os nós duplicam. Rode em um banco vazio, ou limpe antes:
> ```cypher
> MATCH (n:Norma) DETACH DELETE n;
> ```

---

## Caminho B — Restaurar o dump binário (Neo4j 5.x)

O arquivo `export/legis-graph-neo4j5.dump` é o banco completo no formato nativo.
É mais rápido que o caminho A, mas **exige Neo4j 5.x** — um dump de versão diferente não
restaura.

### 1. Pare o Neo4j

```bash
# instalação local
neo4j stop

# docker
docker stop neo4j
```

O `neo4j-admin` recusa restaurar com o banco em uso. Esse é o erro número 1 de quem tenta.

### 2. Restaure

```bash
neo4j-admin database load neo4j \
  --from-path=/caminho/para/export \
  --overwrite-destination=true
```

O nome do arquivo precisa ser exatamente `neo4j.dump`, ou você precisa apontar o caminho
completo. Se você renomeou para `legis-graph-neo4j5.dump`, renomeie de volta:

```bash
cp export/legis-graph-neo4j5.dump /tmp/neo4j.dump
neo4j-admin database load neo4j --from-path=/tmp --overwrite-destination=true
```

### 3. Suba de novo

```bash
neo4j start
```

### Com Docker Compose

```yaml
services:
  neo4j:
    image: neo4j:5.26
    ports: ["7474:7474", "7687:7687"]
    environment:
      NEO4J_AUTH: neo4j/sua-senha
    volumes:
      - ./export:/var/lib/neo4j/import:ro
      - neo4j-data:/data
volumes:
  neo4j-data:
```

```bash
docker compose up -d
docker compose exec neo4j neo4j-admin database load neo4j \
  --from-path=/var/lib/neo4j/import --overwrite-destination=true
docker compose restart neo4j
```

> Se o dump foi gerado em Neo4j 5.26 (é o caso) e você usa versão **anterior**, a restauração
> falha. Restaure com a mesma versão ou mais nova — nunca mais antiga.

---

## Caminho C — Neo4j Aura Free (sem instalar nada)

1. Crie uma instância gratuita em [console.neo4j.io](https://console.neo4j.io).
2. Abra o **Query** (o browser web da Aura).
3. Arraste o `legis-graph.cypher` para o editor, ou cole em partes.

A Aura Free tem limite de armazenamento, mas este grafo cabe com folga: são 16 mil nós.

Um detalhe: a Aura **não aceita `LOAD CSV` de arquivo local** — só URL pública. Por isso o
caminho do `.cypher` é o indicado aqui, e o `LOAD CSV` fica para instalação própria.

---

## Depois de importar: por onde começar

### 1. Ver o schema

```cypher
CALL db.schema.visualization();
```

### 2. Achados rápidos

```cypher
// quantas normas e relações
MATCH (n:Norma) RETURN count(n) AS normas;
MATCH ()-[r]->() RETURN type(r) AS tipo, count(r) AS qtd ORDER BY qtd DESC;

// a norma mais citada
MATCH (n:Norma)<-[r]-()
RETURN n.titulo, count(r) AS citacoes ORDER BY citacoes DESC LIMIT 5;
```

### 3. Uma visualização que impressiona

```cypher
// o que alterou o Código Civil
MATCH (cc:Norma {numero: '10406', ano: 2002})
MATCH (alteradora:Norma)-[r:ALTERA]->(cc)
RETURN alteradora, r, cc LIMIT 25;
```

Rode isso no Browser e clique em qualquer nó para expandir. É a imagem que vale colar no
README.

### 4. As 10 queries de negócio

Todas estão em [`cypher/queries_negocio.cypher`](../cypher/queries_negocio.cypher), cada uma
com o comentário explicando a pergunta que ela responde.

---

## Problemas comuns

| Sintoma | Causa | Solução |
| --- | --- | --- |
| `There is no procedure with the name apoc...` | APOC não instalado | só o `load_csv.cypher` usa APOC; o `.cypher` exportado não precisa |
| `The database is in use` no `database load` | Neo4j rodando | `neo4j stop` antes |
| `Dump file version mismatch` | dump mais novo que o servidor | use Neo4j ≥ 5.26 |
| Nós duplicados | rodou o `.cypher` duas vezes | `MATCH (n:Norma) DETACH DELETE n;` e rode de novo |
| Browser congela ao colar 10 MB | limite do editor | use `cypher-shell -f` ou `split` |
| Acentuação quebrada | charset do cliente | `cypher-shell --encryption=false` e terminal em UTF-8 |
