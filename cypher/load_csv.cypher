// ============================================================================
// Carga do grafo da legislação brasileira no Neo4j via LOAD CSV
//
// Ordem de execução: 1) constraints  2) nós  3) relações  4) conferência
// Coloque normas.csv, correlacoes.csv e amostra_normas.csv em <NEO4J_HOME>/import/
// ============================================================================

// ----------------------------------------------------------------------------
// 1. CONSTRAINTS E ÍNDICES
// O constraint em id garante que a carga possa ser repetida sem duplicar nós.
// ----------------------------------------------------------------------------
CREATE CONSTRAINT norma_id IF NOT EXISTS
FOR (n:Norma) REQUIRE n.id IS UNIQUE;

CREATE INDEX norma_tipo   IF NOT EXISTS FOR (n:Norma) ON (n.tipo);
CREATE INDEX norma_ano    IF NOT EXISTS FOR (n:Norma) ON (n.ano);
CREATE INDEX norma_esfera IF NOT EXISTS FOR (n:Norma) ON (n.esfera);
CREATE INDEX norma_numero IF NOT EXISTS FOR (n:Norma) ON (n.numero);

// ----------------------------------------------------------------------------
// 2. NÓS
// Usamos um único label :Norma mais a propriedade `tipo`, em vez de criar um
// label por tipo de norma. Motivo: as consultas quase sempre atravessam tipos
// ("o que alterou o Código Civil?" cruza Lei, LC e Decreto), e um label por
// tipo obrigaria a repetir a query uma vez por label.
// ----------------------------------------------------------------------------
LOAD CSV WITH HEADERS FROM 'file:///normas.csv' AS linha
MERGE (n:Norma {id: linha.norma_id})
SET n.titulo         = linha.titulo,
    n.tipo           = linha.tipo,
    n.numero         = linha.numero,
    n.ano            = toInteger(linha.ano),
    n.data           = linha.data,
    n.esfera         = linha.esfera,
    n.uf             = CASE WHEN linha.uf = '' THEN null ELSE linha.uf END,
    n.ementa         = linha.ementa,
    n.situacao       = CASE WHEN linha.situacao = '' THEN null ELSE linha.situacao END,
    n.vigente        = (linha.vigente = 'true'),
    n.vigencia_origem = linha.vigencia_origem,
    n.versao_texto   = linha.versao_texto,
    n.urn            = CASE WHEN linha.urn = '' THEN null ELSE linha.urn END,
    n.fonte          = CASE WHEN linha.fonte = '' THEN null ELSE linha.fonte END,
    n.arquivo        = linha.arquivo;

// ----------------------------------------------------------------------------
// 3. RELAÇÕES
// A correlação é criada por *número + esfera + ano*, não por texto do título.
// Isso resolve o problema de a mesma norma aparecer como "Lei nº 10.406",
// "Lei 10.406/2002" ou "Lei no 10.406" no corpo dos textos.
// O type() da relação vem do marcador que o Planalto usa na anotação:
//   Revogado pela...        -> REVOGA
//   Redação dada pela...    -> ALTERA
//   Incluído pela...        -> INCLUI
//   Vide...                 -> REFERENCIA
// ----------------------------------------------------------------------------
LOAD CSV WITH HEADERS FROM 'file:///correlacoes.csv' AS linha
MATCH (origem:Norma {id: linha.origem_id})
MATCH (destino:Norma)
  WHERE destino.numero = linha.destino_numero
    AND destino.esfera = origem.esfera
    AND (destino.uf = origem.uf OR (destino.uf IS NULL AND origem.uf IS NULL))
    AND (linha.destino_ano = '' OR toString(destino.ano) = linha.destino_ano)
    AND destino <> origem
CALL apoc.merge.relationship(origem, linha.tipo_relacao, {}, {}, destino)
  YIELD rel
SET rel.trecho = linha.trecho
RETURN count(rel) AS relacoes_criadas;

// Versão sem APOC (Neo4j puro). Escolha UM dos caminhos: use o bloco acima ou
// os quatro abaixo. Sem APOC, o tipo da relação tem de ser fixo por query.
//
// LOAD CSV WITH HEADERS FROM 'file:///correlacoes.csv' AS linha
// MATCH (o:Norma {id: linha.origem_id}), (d:Norma)
//   WHERE linha.tipo_relacao = 'REVOGA'
//     AND d.numero = linha.destino_numero AND d.esfera = o.esfera
//     AND (linha.destino_ano = '' OR toString(d.ano) = linha.destino_ano)
//     AND d <> o
// MERGE (o)-[r:REVOGA]->(d)
// SET r.trecho = linha.trecho;

// ----------------------------------------------------------------------------
// 4. CONFERÊNCIA
// ----------------------------------------------------------------------------
MATCH (n:Norma) RETURN count(n) AS normas;
MATCH ()-[r]->() RETURN type(r) AS tipo, count(r) AS quantidade ORDER BY quantidade DESC;
CALL db.schema.visualization();
