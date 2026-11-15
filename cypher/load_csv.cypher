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
//
// A correlação é criada por *número + esfera + ano*, não por texto do título.
// Isso resolve o problema de a mesma norma aparecer como "Lei nº 10.406",
// "Lei 10.406/2002" ou "Lei no 10.406" no corpo dos textos.
//
// DIREÇÃO DO EFEITO — o ponto que mais erra neste tipo de extração:
//   `contem_id` é a norma cujo TEXTO traz a anotação.
//   `citada_*`  é a norma NOMEADA na anotação.
//
//   REVOGA / ALTERA / INCLUI  ->  (citada)-[efeito]->(contem)
//     "*(Revogado pela Lei nº 9.120/1995)*" está dentro da Lei 3.820/1960:
//     foi a 9.120 que revogou a 3.820. A seta sai da citada.
//
//   REFERENCIA                ->  (contem)-[cita]->(citada)
//     "*(Vide Lei nº 8.130/1990)*" dentro da Lei 3.792/1960: quem remete
//     é a 3.792. A seta sai de quem traz o "Vide".
//
// Auto-referência (contem == citada) é descartada.
// ----------------------------------------------------------------------------

// 3.a Efeito: citada -> contem
LOAD CSV WITH HEADERS FROM 'file:///correlacoes.csv' AS linha
WITH linha WHERE linha.tipo_relacao <> 'REFERENCIA'
MATCH (contem:Norma {id: linha.contem_id})
MATCH (citada:Norma)
  WHERE citada.numero = linha.citada_numero
    AND citada.esfera = contem.esfera
    AND (citada.uf = contem.uf OR (citada.uf IS NULL AND contem.uf IS NULL))
    AND (linha.citada_ano = '' OR toString(citada.ano) = linha.citada_ano)
WITH citada, contem, linha
WHERE citada <> contem
CALL apoc.merge.relationship(citada, linha.tipo_relacao, {}, {}, contem)
  YIELD rel
SET rel.trecho = linha.trecho
RETURN count(rel) AS relacoes_de_efeito;

// 3.b Referência: contem -> citada
LOAD CSV WITH HEADERS FROM 'file:///correlacoes.csv' AS linha
WITH linha WHERE linha.tipo_relacao = 'REFERENCIA'
MATCH (contem:Norma {id: linha.contem_id})
MATCH (citada:Norma)
  WHERE citada.numero = linha.citada_numero
    AND citada.esfera = contem.esfera
    AND (citada.uf = contem.uf OR (citada.uf IS NULL AND contem.uf IS NULL))
    AND (linha.citada_ano = '' OR toString(citada.ano) = linha.citada_ano)
WITH contem, citada, linha
WHERE contem <> citada
CALL apoc.merge.relationship(contem, 'REFERENCIA', {}, {}, citada)
  YIELD rel
SET rel.trecho = linha.trecho
RETURN count(rel) AS relacoes_de_referencia;

// Versão sem APOC (Neo4j puro). Escolha UM dos caminhos: use os blocos acima
// ou os blocos abaixo. Sem APOC, o tipo da relação tem de ser fixo por query.
//
// LOAD CSV WITH HEADERS FROM 'file:///correlacoes.csv' AS linha
// WITH linha WHERE linha.tipo_relacao = 'REVOGA'
// MATCH (contem:Norma {id: linha.contem_id}), (citada:Norma)
//   WHERE citada.numero = linha.citada_numero
//     AND citada.esfera = contem.esfera
//     AND (linha.citada_ano = '' OR toString(citada.ano) = linha.citada_ano)
//     AND citada <> contem
// MERGE (citada)-[r:REVOGA]->(contem)
// SET r.trecho = linha.trecho;

// ----------------------------------------------------------------------------
// 4. CONFERÊNCIA
// ----------------------------------------------------------------------------
MATCH (n:Norma) RETURN count(n) AS normas;
MATCH ()-[r]->() RETURN type(r) AS tipo, count(r) AS quantidade ORDER BY quantidade DESC;
CALL db.schema.visualization();
