# Como abrir este grafo no seu Neo4j

Quatro caminhos. Escolha pelo que você tem em mãos:

| Você tem | Use | Tempo |
| --- | --- | --- |
| **Neo4j Aura** (nuvem) | **[Caminho Aura](#neo4j-aura-passo-a-passo)** | 5 min |
| Neo4j de qualquer versão, local | Caminho A — arquivo `.cypher` | 2 min |
| Neo4j 5.x local | Caminho B — dump binário | 1 min |
| O acervo e quer gerar do zero | Caminho D — `LOAD CSV` | 10 min |

O caminho do `.cypher` funciona em **qualquer versão** do Neo4j, inclusive 4.x.

---

## Os arquivos já estão no repositório

Não é preciso gerar nada. A pasta [`export/`](../export/) traz o grafo carregado:

| Arquivo | Tamanho | Use no |
| --- | ---: | --- |
| `export/legis-graph.cypher` | 11 MB | qualquer versão do Neo4j |
| `export/legis-graph-neo4j5.dump` | 25 MB | Neo4j 5.x / Aura |

Os arquivos são versionados normalmente (não usam Git LFS) e ficam bem abaixo do limite de
100 MB por arquivo do GitHub. Para conferir que chegaram no seu clone:

```bash
git clone https://github.com/jonydevrio/legis-md-graph.git
ls -lh legis-md-graph/export/
```

### Teste que denuncia direção invertida

Se você importar e as respostas parecerem estranhas, rode este par. Ele é o controle que
confirma que as setas estão no sentido certo:

```cypher
MATCH (cc:Norma {numero:'10406'})<-[r:ALTERA]-() RETURN count(r);  // esperado: 29
MATCH (cc:Norma {numero:'10406'})-[r:ALTERA]->() RETURN count(r);  // esperado: 0
```

O Código Civil foi alterado por 29 normas e não alterou nenhuma. Se os números estiverem
trocados, o arquivo é de uma versão anterior (ou outro grafo).

---

## Neo4j Aura, passo a passo

Validado contra um banco virgem: **16.321 nós, 3.974 relações** e as 29 alterações entrando
no Código Civil.

### 1. Criar a instância

1. Acesse [console.neo4j.io](https://console.neo4j.io) e crie a conta (o tier Free não pede
   cartão).
2. **New Instance** → **AuraDB Free**.
3. Anote a **senha** que aparece — ela não é mostrada de novo. Anote também o **URI**, no
   formato `neo4j+s://xxxxxxxx.databases.neo4j.io`.
4. Espere o status ficar **Running** (1–2 min).

> A AuraDB Free aceita até **200 mil nós** e **400 mil relações**. Este grafo tem 16 mil e
> 4 mil — cabe com folga.

### 2. Restaurar o dump pelo console (recomendado)

O console aceita `.dump` de até 4 GB, e o nosso tem 25 MB.

1. No card da instância, clique no menu **`…`** → **Snapshots**.
2. Abra a aba **Restore from backup file**.
3. Arraste `export/legis-graph-neo4j5.dump` (ou clique em browse).
4. Confirme o aviso de que **todo o conteúdo atual será sobrescrito**.
5. Aguarde o status voltar a **Running**.

Pronto. Abra o **Query** (o browser embutido da Aura) e rode o teste de direção acima.

### 3. Alternativa: `cypher-shell` por pipe

Se preferir a linha de comando — e para o caso de arquivos acima de 4 GB, quando o console
não serve. Este comando foi testado de ponta a ponta:

```bash
curl -sSL https://raw.githubusercontent.com/jonydevrio/legis-md-graph/main/export/legis-graph.cypher \
  | cypher-shell -a neo4j+s://SEU-ID.databases.neo4j.io -u neo4j -p SUA_SENHA
```

O `neo4j+s://` é obrigatório: a Aura só aceita conexão TLS. O `cypher-shell` vem junto com
qualquer instalação do Neo4j (`bin/cypher-shell`) ou isolado no
[Deployment Center](https://neo4j.com/deployment-center/?cypher-shell), e exige Java 21.

### 4. Alternativa: `neo4j-admin database upload` (dump local)

Também serve para arquivos grandes, e é o caminho oficial de migração:

```bash
neo4j-admin database upload neo4j \
  --from-path=export/ \
  --to-uri=neo4j+s://SEU-ID.databases.neo4j.io \
  --to-user=neo4j \
  --to-password=SUA_SENHA \
  --overwrite-destination=true
```

O arquivo precisa se chamar `neo4j.dump` dentro de `--from-path`:

```bash
mkdir -p /tmp/envio && cp export/legis-graph-neo4j5.dump /tmp/envio/neo4j.dump
```

### O que NÃO funciona na Aura

| Tentativa | Por quê |
| --- | --- |
| Colar os 11 MB no editor Query | o editor não aguenta; travará ou truncará |
| `LOAD CSV` de arquivo local | a Aura só lê CSV por URL pública |
| `apoc.export.*` | a Aura não permite escrita em disco |

---

## Caminho A — Importar o `.cypher` (local, qualquer versão)

### Pelo `cypher-shell` (mais confiável)

```bash
cypher-shell -a bolt://localhost:7687 -u neo4j -p SUA_SENHA -f export/legis-graph.cypher
```

Roda em cerca de 30 segundos e não depende do navegador. Também funciona por pipe:

```bash
cat export/legis-graph.cypher | cypher-shell -a bolt://localhost:7687 -u neo4j -p SUA_SENHA
```

### Pelo Neo4j Browser

1. Abra o Browser (`http://localhost:7474`).
2. Arraste `legis-graph.cypher` para o editor.
3. Clique em **Run** e confirme quando ele avisar do tamanho.

Se travar, divida:

```bash
split -l 100000 export/legis-graph.cypher parte_
# rode parte_aa, parte_ab, ... em ordem
```

### Conferindo

```cypher
MATCH (n:Norma) RETURN count(n) AS normas;    // 16321
MATCH ()-[r]->() RETURN count(r) AS relacoes; // 3974
```

> **Aviso:** o arquivo `.cypher` usa `CREATE`, não `MERGE`. Rodar duas vezes no mesmo banco
> duplica os nós. Use um banco vazio, ou limpe antes:
> ```cypher
> MATCH (n:Norma) DETACH DELETE n;
> ```
>
> `IndexAlreadyExists` ao reimportar sobre um schema existente é esperado — significa que o
> schema já estava lá, e o resto do arquivo passa normalmente.

---

## Caminho B — Restaurar o dump binário (local, Neo4j 5.x)

### 1. Pare o Neo4j

```bash
neo4j stop          # instalação local
docker stop neo4j   # docker
```

O `neo4j-admin` recusa restaurar com o banco em uso. É o erro número 1 de quem tenta.

### 2. Restaure

O arquivo precisa se chamar `neo4j.dump`:

```bash
cp export/legis-graph-neo4j5.dump /tmp/neo4j.dump
neo4j-admin database load neo4j --from-path=/tmp --overwrite-destination=true
```

Validado: 39 arquivos, dados íntegros, 16.321 nós e 3.974 relações ao subir.

### 3. Suba de novo

```bash
neo4j start
```

> O dump foi gerado em Neo4j **5.26**. Restaure com a mesma versão ou mais nova — nunca mais
> antiga.

---

## Caminho D — Carregar pelos CSVs (`LOAD CSV`)

Use quando quer gerar o grafo do zero, sem depender de export.

```bash
# 1. clona só o necessário do acervo (são 4,2 GB no total)
git clone --filter=blob:none --no-checkout --depth 1 https://github.com/jonydevrio/legis-md.git
cd legis-md
git sparse-checkout init --cone
git sparse-checkout set federal/leis-ordinarias federal/leis-complementares federal/emendas-constitucionais
git checkout main
cd ..

# 2. extrai os CSVs
python3 scripts/extract.py ./legis-md ./data

# 3. carrega
python3 scripts/load.py --pass SUA_SENHA
```

O `load.py` precisa do **APOC** (usa `apoc.merge.relationship`). Sem APOC, use os blocos
alternativos comentados no fim de `cypher/load_csv.cypher`.

---

## Depois de importar: por onde começar

### 1. Ver o schema

```cypher
CALL db.schema.visualization();
```

### 2. Achados rápidos

```cypher
MATCH (n:Norma) RETURN count(n) AS normas;
MATCH ()-[r]->() RETURN type(r) AS tipo, count(r) AS qtd ORDER BY qtd DESC;

// a norma mais citada
MATCH (n:Norma)<-[r]-()
RETURN n.titulo, count(r) AS citacoes ORDER BY citacoes DESC LIMIT 5;
```

### 3. Uma visualização que impressiona

```cypher
// o que alterou o Código Civil (note o "<-": as alteradoras apontam PARA o CC)
MATCH (cc:Norma {numero: '10406', ano: 2002})
MATCH (alteradora:Norma)-[r:ALTERA]->(cc)
RETURN alteradora, r, cc LIMIT 25;
```

Clique em qualquer nó no Browser para expandir. É a imagem que vale colar no README.

### 4. As 10 queries de negócio

Todas em [`cypher/queries_negocio.cypher`](../cypher/queries_negocio.cypher). Para rodar
todas de uma vez:

```bash
python3 scripts/run_query.py
```

---

## Problemas comuns

| Sintoma | Causa | Solução |
| --- | --- | --- |
| Respostas invertidas ("o CC alterou 29 leis") | grafo de versão anterior | use o arquivo atual; rode o teste de direção |
| `There is no procedure with the name apoc...` | APOC não instalado | só `load.py`/`load_csv.cypher` usam APOC; o `.cypher` exportado não precisa |
| `Export to files not enabled` | config do APOC | `apoc.export.file.enabled=true` em `conf/apoc.conf` |
| APOC grava em `import/`, não onde pedi | comportamento do APOC | caminho é relativo a `<NEO4J_HOME>/import/`; `exportar.py` já move |
| `The database is in use` no `database load` | Neo4j rodando | `neo4j stop` antes |
| `Dump file version mismatch` | dump mais novo que o servidor | use Neo4j ≥ 5.26 |
| Nós duplicados | rodou o `.cypher` duas vezes | `MATCH (n:Norma) DETACH DELETE n;` e rode de novo |
| `IndexAlreadyExists` ao reimportar | schema já existe | esperado, ignore |
| Browser congela ao colar 11 MB | limite do editor | use `cypher-shell -f` ou `split` |
| Aura: editor trava ao colar | limite do editor | use o `.dump` pelo console ou `cypher-shell` |
| Aura: conexão recusada | URI sem TLS | use `neo4j+s://`, não `neo4j://` |
| Aura: instância pausada | 3 dias sem escrita | botão **Resume** no console (após 30 dias pausada, é apagada) |
| `CredentialsExpired` no primeiro acesso | senha inicial | `ALTER CURRENT USER SET PASSWORD FROM 'neo4j' TO '...'` no banco `system` |
| Acentuação quebrada | charset do cliente | `cypher-shell --encryption=false`, terminal em UTF-8 |
